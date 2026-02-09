"""
Evaluation pipeline orchestrator.

This service runs the full coaching evaluation pipeline:
1. Transcribe video → save transcript to DB
2. (Week 7-8) Analyze transcript with Claude → save report
3. (Week 9-10) Generate PDF reports

Each stage updates the evaluation status so the frontend can show progress:
    queued → transcribing → analyzing → generating_report → completed

Design: This runs as a background task (not in the request handler).
The request handler creates the evaluation record and kicks off the pipeline.
The pipeline runs independently and updates the DB as it progresses.
"""

import asyncio
import traceback
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import Evaluation, Transcript, Video
from app.services.storage import get_storage_service
from app.services.transcription import TranscriptionService


async def run_evaluation_pipeline(evaluation_id: UUID) -> None:
    """Run the full evaluation pipeline for a video.

    This is the main entry point, called from a background task.
    It manages its own database sessions (since it runs outside
    the request lifecycle).

    Args:
        evaluation_id: UUID of the evaluation to process.
    """
    async with AsyncSessionLocal() as db:
        try:
            # Load evaluation + video
            eval_result = await db.execute(
                select(Evaluation).where(Evaluation.id == evaluation_id)
            )
            evaluation = eval_result.scalar_one_or_none()
            if not evaluation:
                print(f"❌ Evaluation {evaluation_id} not found")
                return

            video_result = await db.execute(
                select(Video).where(Video.id == evaluation.video_id)
            )
            video = video_result.scalar_one_or_none()
            if not video:
                await _fail_evaluation(db, evaluation, "Video not found")
                return

            # --- Stage 1: Transcription ---
            evaluation.status = "transcribing"
            evaluation.processing_started_at = datetime.now(timezone.utc)
            await db.commit()

            print(f"📝 Starting transcription for video: {video.filename}")
            transcript = await _run_transcription(db, video, evaluation)
            if not transcript:
                return  # _run_transcription handles failure

            print(f"✅ Transcription complete: {transcript.word_count} words, "
                  f"{transcript.speaker_count} speakers")

            # --- Stage 2: Coaching Analysis (Week 7-8) ---
            # evaluation.status = "analyzing"
            # await db.commit()
            # await _run_analysis(db, transcript, evaluation)

            # --- Stage 3: PDF Generation (Week 9-10) ---
            # evaluation.status = "generating_report"
            # await db.commit()
            # await _generate_reports(db, evaluation)

            # --- Mark complete ---
            evaluation.status = "transcribed"  # Will be "completed" once all stages work
            evaluation.processing_completed_at = datetime.now(timezone.utc)
            await db.commit()

            print(f"🎉 Evaluation {evaluation_id} pipeline complete")

        except Exception as e:
            print(f"❌ Pipeline error: {str(e)}")
            traceback.print_exc()
            try:
                await _fail_evaluation(db, evaluation, str(e))
            except Exception:
                pass  # Don't let error handling crash


async def _run_transcription(
    db: AsyncSession,
    video: Video,
    evaluation: Evaluation,
) -> Transcript | None:
    """Run transcription stage of the pipeline.

    Uses AssemblyAI to transcribe the video. Since AssemblyAI's SDK
    is synchronous (blocking), we run it in a thread pool executor
    so it doesn't block the async event loop.

    Returns:
        Transcript object if successful, None if failed.
    """
    try:
        # Get the local file path
        storage = get_storage_service()
        file_path = await storage.get_file_url(video.s3_key)

        # Run the blocking transcription in a thread pool
        # asyncio.to_thread() wraps a sync function so it doesn't block
        service = TranscriptionService()
        result = await asyncio.to_thread(service.transcribe_local_file, file_path)

        # Save transcript to database
        transcript = Transcript(
            video_id=video.id,
            transcript_text=result.transcript_text,
            word_count=result.word_count,
            speaker_count=result.speaker_count,
            processing_time_seconds=result.processing_time_seconds,
            assemblyai_transcript_id=result.assemblyai_id,
            status="completed",
        )
        db.add(transcript)

        # Update video with duration
        video.duration_seconds = result.duration_seconds
        video.upload_status = "transcribed"

        # Link transcript to evaluation
        evaluation.transcript_id = transcript.id

        await db.commit()
        await db.refresh(transcript)

        return transcript

    except Exception as e:
        print(f"❌ Transcription failed: {str(e)}")
        traceback.print_exc()
        await _fail_evaluation(db, evaluation, f"Transcription failed: {str(e)}")
        return None


async def _fail_evaluation(
    db: AsyncSession,
    evaluation: Evaluation,
    error_message: str,
) -> None:
    """Mark an evaluation as failed with an error message."""
    evaluation.status = "failed"
    evaluation.processing_completed_at = datetime.now(timezone.utc)
    # Store error in metrics JSONB for debugging
    evaluation.metrics = {"error": error_message}
    await db.commit()
    print(f"❌ Evaluation {evaluation.id} marked as failed: {error_message}")

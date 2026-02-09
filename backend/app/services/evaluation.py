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
from app.models import Evaluation, Transcript, User, Video
from app.services.analysis import AnalysisService
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

            # --- Stage 2: Coaching Analysis ---
            evaluation.status = "analyzing"
            await db.commit()

            print(f"🧠 Starting coaching analysis with Claude...")
            analysis_success = await _run_analysis(db, transcript, evaluation)
            if not analysis_success:
                return  # _run_analysis handles failure

            print(f"✅ Coaching analysis complete")

            # --- Stage 3: PDF Generation ---
            # PDFs are generated on-demand via the /report/pdf and
            # /worksheet/pdf endpoints. No need to pre-generate since
            # ReportLab renders in <100ms. This avoids storing PDF files
            # and ensures users always get the latest format.

            # --- Mark complete ---
            evaluation.status = "completed"
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


async def _run_analysis(
    db: AsyncSession,
    transcript: Transcript,
    evaluation: Evaluation,
) -> bool:
    """Run the coaching analysis stage of the pipeline.

    Sends the transcript to Claude for coaching analysis. Like
    transcription, the Anthropic SDK is synchronous, so we run it
    in a thread pool to avoid blocking the event loop.

    Returns:
        True if successful, False if failed.
    """
    try:
        # Look up instructor name for personalized report
        instructor_name = "the instructor"
        if evaluation.instructor_id:
            user_result = await db.execute(
                select(User).where(User.id == evaluation.instructor_id)
            )
            user = user_result.scalar_one_or_none()
            if user:
                instructor_name = user.display_name

        # Run the blocking Claude API call in a thread pool
        service = AnalysisService()
        result = await asyncio.to_thread(
            service.analyze, transcript.transcript_text, instructor_name
        )

        # Save analysis results to the evaluation record
        evaluation.report_markdown = result.report_markdown
        evaluation.strengths = result.strengths
        evaluation.growth_opportunities = result.growth_opportunities

        # Merge extracted coaching metrics with API usage metadata
        evaluation.metrics = {
            **result.metrics,
            "analysis_input_tokens": result.input_tokens,
            "analysis_output_tokens": result.output_tokens,
            "analysis_processing_seconds": result.processing_time_seconds,
            "analysis_model": result.model,
        }

        await db.commit()
        return True

    except Exception as e:
        print(f"❌ Analysis failed: {str(e)}")
        traceback.print_exc()
        await _fail_evaluation(db, evaluation, f"Analysis failed: {str(e)}")
        return False


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

"""
Evaluation API endpoints.

These handle the coaching evaluation lifecycle:
1. POST /evaluations — Start a new evaluation (triggers transcription + analysis)
2. GET /evaluations/{id} — Check status and get results
3. GET /evaluations/{id}/transcript — Get the raw transcript

The evaluation runs asynchronously in the background. The client:
1. POSTs to start it → gets back an evaluation_id immediately
2. Polls GET /{id} to check status → sees: queued → transcribing → completed
3. Once completed, fetches the transcript and (later) the report

This polling pattern is simple and reliable. In production, you'd
add WebSocket support for real-time updates, but polling works fine for MVP.
"""

import asyncio
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Evaluation, Transcript, Video
from app.schemas.evaluations import (
    EvaluationCreateRequest,
    EvaluationResponse,
    TranscriptResponse,
)
from app.services.evaluation import run_evaluation_pipeline

router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluations"])


@router.post("", response_model=EvaluationResponse)
async def create_evaluation(
    request: EvaluationCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Start a new coaching evaluation for a video.

    This immediately returns an evaluation ID. The actual processing
    (transcription + analysis) runs in the background.

    The client should poll GET /evaluations/{id} to track progress.

    Args:
        request: Video ID and instructor ID to evaluate.
        background_tasks: FastAPI's built-in background task runner.
    """
    # Verify video exists
    video_result = await db.execute(
        select(Video).where(Video.id == request.video_id)
    )
    video = video_result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Check for existing evaluation on this video
    existing = await db.execute(
        select(Evaluation).where(
            Evaluation.video_id == request.video_id,
            Evaluation.status.not_in(["failed"]),  # Allow retry after failure
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="An evaluation already exists for this video. "
                   "Delete it first to re-evaluate.",
        )

    # Create evaluation record
    evaluation = Evaluation(
        video_id=request.video_id,
        instructor_id=request.instructor_id,
        status="queued",
    )
    db.add(evaluation)
    await db.commit()
    await db.refresh(evaluation)

    # Kick off the pipeline in the background
    # This returns immediately — the pipeline runs independently
    background_tasks.add_task(run_evaluation_pipeline, evaluation.id)

    return EvaluationResponse(
        id=evaluation.id,
        video_id=evaluation.video_id,
        instructor_id=evaluation.instructor_id,
        status=evaluation.status,
        processing_started_at=evaluation.processing_started_at,
        processing_completed_at=evaluation.processing_completed_at,
        has_transcript=False,
        has_report=False,
        metrics=evaluation.metrics,
        created_at=evaluation.created_at,
    )


@router.get("/{evaluation_id}", response_model=EvaluationResponse)
async def get_evaluation(
    evaluation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get the current status and details of an evaluation.

    Client should poll this endpoint to track progress:
    - queued: Waiting to start
    - transcribing: AssemblyAI is processing the video
    - transcribed: Transcript ready (analysis not yet implemented)
    - analyzing: Claude is generating coaching feedback (Week 7-8)
    - completed: Full report ready
    - failed: Something went wrong (check metrics.error)
    """
    result = await db.execute(
        select(Evaluation).where(Evaluation.id == evaluation_id)
    )
    evaluation = result.scalar_one_or_none()

    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    return EvaluationResponse(
        id=evaluation.id,
        video_id=evaluation.video_id,
        instructor_id=evaluation.instructor_id,
        status=evaluation.status,
        processing_started_at=evaluation.processing_started_at,
        processing_completed_at=evaluation.processing_completed_at,
        has_transcript=(
            evaluation.transcript_id is not None
            or evaluation.status in ("transcribed", "analyzing", "completed")
        ),
        has_report=evaluation.report_markdown is not None,
        metrics=evaluation.metrics,
        created_at=evaluation.created_at,
    )


@router.get("/{evaluation_id}/transcript", response_model=TranscriptResponse)
async def get_transcript(
    evaluation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get the transcript for an evaluation.

    Only available after transcription is complete (status >= 'transcribed').
    """
    eval_result = await db.execute(
        select(Evaluation).where(Evaluation.id == evaluation_id)
    )
    evaluation = eval_result.scalar_one_or_none()

    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    # Look up transcript by transcript_id, or fall back to video_id
    # (the background task may have committed the transcript before
    #  updating the evaluation's transcript_id link)
    transcript = None
    if evaluation.transcript_id:
        result = await db.execute(
            select(Transcript).where(Transcript.id == evaluation.transcript_id)
        )
        transcript = result.scalar_one_or_none()

    if not transcript:
        # Fallback: search by video_id
        result = await db.execute(
            select(Transcript).where(Transcript.video_id == evaluation.video_id)
        )
        transcript = result.scalar_one_or_none()

    if not transcript:
        raise HTTPException(
            status_code=400,
            detail=f"Transcript not ready. Current status: {evaluation.status}",
        )

    return TranscriptResponse.model_validate(transcript)

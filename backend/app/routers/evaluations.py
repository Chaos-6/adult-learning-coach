"""
Evaluation API endpoints.

These handle the coaching evaluation lifecycle:
1. POST /evaluations — Start a new evaluation (triggers transcription + analysis)
2. GET /evaluations/{id} — Check status and get results
3. GET /evaluations/{id}/transcript — Get the raw transcript
4. GET /evaluations/{id}/report — Get the coaching report (JSON)
5. GET /evaluations/{id}/report/pdf — Download coaching report as PDF
6. GET /evaluations/{id}/worksheet/pdf — Download reflection worksheet as PDF

The evaluation runs asynchronously in the background. The client:
1. POSTs to start it → gets back an evaluation_id immediately
2. Polls GET /{id} to check status → sees: queued → transcribing → analyzing → completed
3. Once completed, fetches the report (JSON or PDF) and transcript

This polling pattern is simple and reliable. In production, you'd
add WebSocket support for real-time updates, but polling works fine for MVP.
"""

import asyncio
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Evaluation, Transcript, User, Video
from app.schemas.evaluations import (
    EvaluationCreateRequest,
    EvaluationResponse,
    ReportResponse,
    TranscriptResponse,
)
from app.services.evaluation import run_evaluation_pipeline
from app.services.pdf_report import PDFReportGenerator

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


@router.get("/{evaluation_id}/report", response_model=ReportResponse)
async def get_report(
    evaluation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get the coaching report for an evaluation.

    Only available after analysis is complete (status == 'completed').
    Returns the full markdown report, extracted metrics, strengths,
    and growth opportunities.
    """
    result = await db.execute(
        select(Evaluation).where(Evaluation.id == evaluation_id)
    )
    evaluation = result.scalar_one_or_none()

    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    if not evaluation.report_markdown:
        raise HTTPException(
            status_code=400,
            detail=f"Report not ready. Current status: {evaluation.status}",
        )

    return ReportResponse(
        id=evaluation.id,
        video_id=evaluation.video_id,
        instructor_id=evaluation.instructor_id,
        status=evaluation.status,
        report_markdown=evaluation.report_markdown,
        metrics=evaluation.metrics,
        strengths=evaluation.strengths,
        growth_opportunities=evaluation.growth_opportunities,
        processing_started_at=evaluation.processing_started_at,
        processing_completed_at=evaluation.processing_completed_at,
        created_at=evaluation.created_at,
    )


@router.get("/{evaluation_id}/report/pdf")
async def download_report_pdf(
    evaluation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Download the coaching report as a PDF.

    Generates the PDF on-the-fly from the stored markdown report.
    This is a design choice: we generate PDFs on demand rather than
    storing them. It's simpler (no S3 needed yet), and the generation
    is fast (<100ms). We can cache or pre-generate later if needed.
    """
    evaluation = await _get_completed_evaluation(db, evaluation_id)
    instructor_name = await _get_instructor_name(db, evaluation.instructor_id)

    generator = PDFReportGenerator()
    pdf_bytes = generator.generate_coaching_report(
        report_markdown=evaluation.report_markdown,
        instructor_name=instructor_name,
        metrics=evaluation.metrics,
        strengths=evaluation.strengths,
        growth_opportunities=evaluation.growth_opportunities,
    )

    filename = f"coaching_report_{instructor_name.replace(' ', '_')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{evaluation_id}/worksheet/pdf")
async def download_worksheet_pdf(
    evaluation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Download the reflection worksheet as a PDF.

    The worksheet is a condensed, printable document with lined space
    for the instructor to write reflections and action plans.
    """
    evaluation = await _get_completed_evaluation(db, evaluation_id)
    instructor_name = await _get_instructor_name(db, evaluation.instructor_id)

    generator = PDFReportGenerator()
    pdf_bytes = generator.generate_reflection_worksheet(
        instructor_name=instructor_name,
        strengths=evaluation.strengths,
        growth_opportunities=evaluation.growth_opportunities,
        report_markdown=evaluation.report_markdown or "",
    )

    filename = f"reflection_worksheet_{instructor_name.replace(' ', '_')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- Helper functions for PDF endpoints ---

async def _get_completed_evaluation(
    db: AsyncSession, evaluation_id: UUID,
) -> Evaluation:
    """Load an evaluation that has a completed report. Raises 404/400."""
    result = await db.execute(
        select(Evaluation).where(Evaluation.id == evaluation_id)
    )
    evaluation = result.scalar_one_or_none()

    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    if not evaluation.report_markdown:
        raise HTTPException(
            status_code=400,
            detail=f"Report not ready. Current status: {evaluation.status}",
        )

    return evaluation


async def _get_instructor_name(db: AsyncSession, instructor_id: UUID) -> str:
    """Look up instructor display name, with fallback."""
    if not instructor_id:
        return "Instructor"

    result = await db.execute(
        select(User).where(User.id == instructor_id)
    )
    user = result.scalar_one_or_none()
    return user.display_name if user else "Instructor"

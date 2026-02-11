"""
Comparison API endpoints.

These handle the multi-video comparison lifecycle:
1. POST /comparisons — Create a comparison (optionally start immediately)
2. GET /comparisons — List comparisons (paginated)
3. GET /comparisons/{id} — Get comparison details + linked evaluations
4. POST /comparisons/{id}/start — Start analysis on a draft comparison
5. GET /comparisons/{id}/report — Get the comparison report (JSON)
6. GET /comparisons/{id}/report/pdf — Download comparison report as PDF
7. DELETE /comparisons/{id} — Delete a comparison (not the evaluations)

Same polling pattern as evaluations:
1. Client POSTs to create → gets comparison_id
2. Polls GET /{id} → sees: draft → queued → analyzing → completed
3. Once completed, fetches the report
"""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Comparison, ComparisonEvaluation, Evaluation, User
from app.schemas.comparisons import (
    ComparisonCreateRequest,
    ComparisonListResponse,
    ComparisonReportResponse,
    ComparisonResponse,
    EvaluationSummary,
)
from app.services.comparison_pdf import ComparisonPDFGenerator
from app.services.comparison_pipeline import run_comparison_pipeline

router = APIRouter(prefix="/api/v1/comparisons", tags=["comparisons"])


@router.post("", response_model=ComparisonResponse)
async def create_comparison(
    request: ComparisonCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Create a new multi-video comparison.

    Validates that all referenced evaluations exist and are completed.
    If start_immediately=True (default), kicks off the comparison
    pipeline in the background.
    """
    # Validate all evaluations exist and are completed
    evaluation_ids = request.evaluation_ids
    for eval_id in evaluation_ids:
        result = await db.execute(
            select(Evaluation).where(Evaluation.id == eval_id)
        )
        evaluation = result.scalar_one_or_none()
        if not evaluation:
            raise HTTPException(
                status_code=404,
                detail=f"Evaluation {eval_id} not found",
            )
        if evaluation.status != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Evaluation {eval_id} is not completed "
                       f"(status: {evaluation.status}). "
                       f"All evaluations must be completed before comparison.",
            )
        if not evaluation.report_markdown:
            raise HTTPException(
                status_code=400,
                detail=f"Evaluation {eval_id} has no report. "
                       f"All evaluations must have reports before comparison.",
            )

    # Create comparison record
    comparison = Comparison(
        title=request.title,
        comparison_type=request.comparison_type,
        status="draft" if not request.start_immediately else "queued",
        organization_id=request.organization_id,
        created_by_id=request.created_by_id,
        class_tag=request.class_tag,
        anonymize_instructors=request.anonymize_instructors,
    )
    db.add(comparison)
    await db.commit()
    await db.refresh(comparison)

    # Create join table entries
    for i, eval_id in enumerate(evaluation_ids):
        link = ComparisonEvaluation(
            comparison_id=comparison.id,
            evaluation_id=eval_id,
            display_order=i,
            label=f"Session {i + 1}",
        )
        db.add(link)
    await db.commit()

    # Start pipeline if requested
    if request.start_immediately:
        background_tasks.add_task(run_comparison_pipeline, comparison.id)

    # Build response with evaluation summaries
    eval_summaries = await _get_evaluation_summaries(db, comparison.id)

    return ComparisonResponse(
        id=comparison.id,
        title=comparison.title,
        comparison_type=comparison.comparison_type,
        status=comparison.status,
        organization_id=comparison.organization_id,
        created_by_id=comparison.created_by_id,
        class_tag=comparison.class_tag,
        anonymize_instructors=comparison.anonymize_instructors,
        has_report=False,
        metrics=comparison.metrics,
        evaluations=eval_summaries,
        created_at=comparison.created_at,
        processing_started_at=comparison.processing_started_at,
        processing_completed_at=comparison.processing_completed_at,
    )


@router.get("", response_model=ComparisonListResponse)
async def list_comparisons(
    page: int = 1,
    page_size: int = 20,
    comparison_type: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List comparisons with optional filtering."""
    query = select(Comparison)

    if comparison_type:
        query = query.where(Comparison.comparison_type == comparison_type)
    if status:
        query = query.where(Comparison.status == status)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # Paginate
    query = (
        query.order_by(Comparison.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    comparisons = result.scalars().all()

    items = []
    for comp in comparisons:
        eval_summaries = await _get_evaluation_summaries(db, comp.id)
        items.append(ComparisonResponse(
            id=comp.id,
            title=comp.title,
            comparison_type=comp.comparison_type,
            status=comp.status,
            organization_id=comp.organization_id,
            created_by_id=comp.created_by_id,
            class_tag=comp.class_tag,
            anonymize_instructors=comp.anonymize_instructors,
            has_report=comp.report_markdown is not None,
            metrics=comp.metrics,
            evaluations=eval_summaries,
            created_at=comp.created_at,
            processing_started_at=comp.processing_started_at,
            processing_completed_at=comp.processing_completed_at,
        ))

    return ComparisonListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{comparison_id}", response_model=ComparisonResponse)
async def get_comparison(
    comparison_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get comparison details with linked evaluations.

    Client polls this to track analysis progress.
    """
    result = await db.execute(
        select(Comparison).where(Comparison.id == comparison_id)
    )
    comparison = result.scalar_one_or_none()

    if not comparison:
        raise HTTPException(status_code=404, detail="Comparison not found")

    eval_summaries = await _get_evaluation_summaries(db, comparison.id)

    return ComparisonResponse(
        id=comparison.id,
        title=comparison.title,
        comparison_type=comparison.comparison_type,
        status=comparison.status,
        organization_id=comparison.organization_id,
        created_by_id=comparison.created_by_id,
        class_tag=comparison.class_tag,
        anonymize_instructors=comparison.anonymize_instructors,
        has_report=comparison.report_markdown is not None,
        metrics=comparison.metrics,
        evaluations=eval_summaries,
        created_at=comparison.created_at,
        processing_started_at=comparison.processing_started_at,
        processing_completed_at=comparison.processing_completed_at,
    )


@router.post("/{comparison_id}/start", response_model=ComparisonResponse)
async def start_comparison(
    comparison_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Start analysis on a draft comparison.

    Only works on comparisons with status 'draft'.
    """
    result = await db.execute(
        select(Comparison).where(Comparison.id == comparison_id)
    )
    comparison = result.scalar_one_or_none()

    if not comparison:
        raise HTTPException(status_code=404, detail="Comparison not found")

    if comparison.status != "draft":
        raise HTTPException(
            status_code=400,
            detail=f"Can only start draft comparisons. Current status: {comparison.status}",
        )

    comparison.status = "queued"
    await db.commit()

    background_tasks.add_task(run_comparison_pipeline, comparison.id)

    eval_summaries = await _get_evaluation_summaries(db, comparison.id)

    return ComparisonResponse(
        id=comparison.id,
        title=comparison.title,
        comparison_type=comparison.comparison_type,
        status=comparison.status,
        organization_id=comparison.organization_id,
        created_by_id=comparison.created_by_id,
        class_tag=comparison.class_tag,
        anonymize_instructors=comparison.anonymize_instructors,
        has_report=False,
        metrics=comparison.metrics,
        evaluations=eval_summaries,
        created_at=comparison.created_at,
        processing_started_at=comparison.processing_started_at,
        processing_completed_at=comparison.processing_completed_at,
    )


@router.get("/{comparison_id}/report", response_model=ComparisonReportResponse)
async def get_comparison_report(
    comparison_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get the comparison report with full analysis results."""
    result = await db.execute(
        select(Comparison).where(Comparison.id == comparison_id)
    )
    comparison = result.scalar_one_or_none()

    if not comparison:
        raise HTTPException(status_code=404, detail="Comparison not found")

    if not comparison.report_markdown:
        raise HTTPException(
            status_code=400,
            detail=f"Report not ready. Current status: {comparison.status}",
        )

    eval_summaries = await _get_evaluation_summaries(db, comparison.id)

    return ComparisonReportResponse(
        id=comparison.id,
        title=comparison.title,
        comparison_type=comparison.comparison_type,
        status=comparison.status,
        report_markdown=comparison.report_markdown,
        metrics=comparison.metrics,
        strengths=comparison.strengths,
        growth_opportunities=comparison.growth_opportunities,
        evaluations=eval_summaries,
        created_at=comparison.created_at,
        processing_started_at=comparison.processing_started_at,
        processing_completed_at=comparison.processing_completed_at,
    )


@router.get("/{comparison_id}/report/pdf")
async def download_comparison_report_pdf(
    comparison_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Download the comparison report as a PDF.

    Generates the PDF on-the-fly from the stored markdown report,
    same pattern as the evaluation PDF endpoint. Fast (<100ms),
    no pre-storage needed.
    """
    result = await db.execute(
        select(Comparison).where(Comparison.id == comparison_id)
    )
    comparison = result.scalar_one_or_none()

    if not comparison:
        raise HTTPException(status_code=404, detail="Comparison not found")

    if not comparison.report_markdown:
        raise HTTPException(
            status_code=400,
            detail=f"Report not ready. Current status: {comparison.status}",
        )

    # Build evaluation summaries for the PDF's overview table
    eval_summaries = await _get_evaluation_summaries(db, comparison.id)
    eval_dicts = [
        {
            "label": ev.label,
            "instructor_name": ev.instructor_name,
            "status": ev.status,
        }
        for ev in eval_summaries
    ]

    generator = ComparisonPDFGenerator()
    pdf_bytes = generator.generate_comparison_report(
        title=comparison.title,
        comparison_type=comparison.comparison_type,
        report_markdown=comparison.report_markdown,
        metrics=comparison.metrics,
        strengths=comparison.strengths,
        growth_opportunities=comparison.growth_opportunities,
        evaluations=eval_dicts,
    )

    safe_title = comparison.title.replace(" ", "_")[:50]
    filename = f"comparison_report_{safe_title}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{comparison_id}")
async def delete_comparison(
    comparison_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a comparison (does NOT delete the linked evaluations)."""
    result = await db.execute(
        select(Comparison).where(Comparison.id == comparison_id)
    )
    comparison = result.scalar_one_or_none()

    if not comparison:
        raise HTTPException(status_code=404, detail="Comparison not found")

    # Delete join table entries first (CASCADE should handle this,
    # but being explicit is clearer)
    await db.execute(
        select(ComparisonEvaluation)
        .where(ComparisonEvaluation.comparison_id == comparison_id)
    )
    # Actually delete via raw delete
    from sqlalchemy import delete
    await db.execute(
        delete(ComparisonEvaluation)
        .where(ComparisonEvaluation.comparison_id == comparison_id)
    )
    await db.delete(comparison)
    await db.commit()

    return {"detail": "Comparison deleted", "id": str(comparison_id)}


# --- Helper functions ---

async def _get_evaluation_summaries(
    db: AsyncSession,
    comparison_id: UUID,
) -> list[EvaluationSummary]:
    """Load evaluation summaries for a comparison's linked evaluations."""
    links_result = await db.execute(
        select(ComparisonEvaluation)
        .where(ComparisonEvaluation.comparison_id == comparison_id)
        .order_by(ComparisonEvaluation.display_order)
    )
    links = links_result.scalars().all()

    summaries = []
    for link in links:
        # Look up evaluation status
        eval_result = await db.execute(
            select(Evaluation).where(Evaluation.id == link.evaluation_id)
        )
        evaluation = eval_result.scalar_one_or_none()

        # Look up instructor name
        instructor_name = None
        if evaluation and evaluation.instructor_id:
            user_result = await db.execute(
                select(User).where(User.id == evaluation.instructor_id)
            )
            user = user_result.scalar_one_or_none()
            if user:
                instructor_name = user.display_name

        summaries.append(EvaluationSummary(
            evaluation_id=link.evaluation_id,
            display_order=link.display_order,
            label=link.label,
            status=evaluation.status if evaluation else None,
            instructor_name=instructor_name,
        ))

    return summaries

"""
Instructor dashboard and performance tracking API.

These endpoints power the instructor's view of their coaching history:
1. GET /instructors/{id}/dashboard — Aggregated stats + metric trends
2. GET /instructors/{id}/evaluations — Paginated evaluation history
3. GET /instructors/{id}/metrics/{metric} — Trend data for a specific metric

The dashboard is the "home page" for instructors. It answers:
- How am I improving over time?
- What are my consistent strengths?
- What growth areas keep coming up?

Design: These are READ-ONLY analytics endpoints. All the data already
exists in the evaluations table — we're just querying and aggregating it.
"""

from collections import Counter
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Evaluation, User, Video
from app.schemas.instructors import (
    EvaluationSummary,
    InstructorDashboard,
    MetricDataPoint,
    MetricTrend,
)

router = APIRouter(prefix="/api/v1/instructors", tags=["instructors"])

# --- Metric definitions ---
# Each metric has: key (in JSONB), display name, unit, target range
# This is the single source of truth for what metrics we track.
METRIC_DEFINITIONS = [
    {
        "key": "wpm",
        "display_name": "Speaking Pace",
        "unit": "WPM",
        "target_min": 120.0,
        "target_max": 160.0,
        "higher_is_better": None,  # Range — neither direction is better
    },
    {
        "key": "pauses_per_10min",
        "display_name": "Strategic Pauses",
        "unit": "per 10 min",
        "target_min": 4.0,
        "target_max": 6.0,
        "higher_is_better": True,  # More pauses (within range) is better
    },
    {
        "key": "filler_words_per_min",
        "display_name": "Filler Words",
        "unit": "per min",
        "target_min": None,
        "target_max": 3.0,
        "higher_is_better": False,  # Fewer is better
    },
    {
        "key": "questions_per_5min",
        "display_name": "Questions Asked",
        "unit": "per 5 min",
        "target_min": 1.0,
        "target_max": None,
        "higher_is_better": True,  # More questions is better
    },
    {
        "key": "tangent_percentage",
        "display_name": "Tangent Time",
        "unit": "%",
        "target_min": None,
        "target_max": 10.0,
        "higher_is_better": False,  # Less tangent time is better
    },
]


@router.get("/{instructor_id}/dashboard", response_model=InstructorDashboard)
async def get_instructor_dashboard(
    instructor_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get the instructor's coaching dashboard.

    Returns aggregated performance data across all completed evaluations:
    - Summary stats (total evaluations, sessions analyzed)
    - All evaluations with status and basic metrics
    - Metric trends over time (for charting)
    - Most common strengths and recurring growth areas
    """
    # Verify instructor exists
    user_result = await db.execute(
        select(User).where(User.id == instructor_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Instructor not found")

    # Load all completed evaluations for this instructor, newest first
    eval_result = await db.execute(
        select(Evaluation, Video.filename)
        .join(Video, Evaluation.video_id == Video.id, isouter=True)
        .where(
            Evaluation.instructor_id == instructor_id,
            Evaluation.status == "completed",
        )
        .order_by(Evaluation.created_at.asc())
    )
    rows = eval_result.all()

    # Build evaluation summaries
    evaluations = []
    for eval_obj, video_filename in rows:
        evaluations.append(EvaluationSummary(
            id=eval_obj.id,
            video_id=eval_obj.video_id,
            video_filename=video_filename,
            status=eval_obj.status,
            created_at=eval_obj.created_at,
            processing_completed_at=eval_obj.processing_completed_at,
            metrics=eval_obj.metrics,
            strength_count=len(eval_obj.strengths) if eval_obj.strengths else 0,
            growth_area_count=len(eval_obj.growth_opportunities) if eval_obj.growth_opportunities else 0,
        ))

    # Build metric trends
    metric_trends = _build_metric_trends(rows)

    # Aggregate strengths and growth areas across all evaluations
    top_strengths = _aggregate_themes(rows, "strengths")
    recurring_growth = _aggregate_themes(rows, "growth_opportunities")

    # Count total (including non-completed)
    total_result = await db.execute(
        select(func.count(Evaluation.id))
        .where(Evaluation.instructor_id == instructor_id)
    )
    total_evaluations = total_result.scalar() or 0

    return InstructorDashboard(
        instructor_id=instructor_id,
        instructor_name=user.display_name,
        total_evaluations=total_evaluations,
        total_sessions_analyzed=len(evaluations),
        evaluations=list(reversed(evaluations)),  # Newest first for display
        metric_trends=metric_trends,
        top_strengths=top_strengths,
        recurring_growth_areas=recurring_growth,
    )


@router.get("/{instructor_id}/evaluations")
async def list_instructor_evaluations(
    instructor_id: UUID,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List all evaluations for an instructor with filtering.

    Args:
        instructor_id: The instructor's UUID
        status: Optional filter (queued, transcribing, analyzing, completed, failed)
        page: Page number (1-indexed)
        page_size: Results per page (default 20, max 100)
    """
    page_size = min(page_size, 100)
    offset = (page - 1) * page_size

    # Base query
    query = (
        select(Evaluation, Video.filename)
        .join(Video, Evaluation.video_id == Video.id, isouter=True)
        .where(Evaluation.instructor_id == instructor_id)
        .order_by(Evaluation.created_at.desc())
    )
    count_query = (
        select(func.count(Evaluation.id))
        .where(Evaluation.instructor_id == instructor_id)
    )

    if status:
        query = query.where(Evaluation.status == status)
        count_query = count_query.where(Evaluation.status == status)

    # Get total
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get page
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    rows = result.all()

    evaluations = []
    for eval_obj, video_filename in rows:
        evaluations.append(EvaluationSummary(
            id=eval_obj.id,
            video_id=eval_obj.video_id,
            video_filename=video_filename,
            status=eval_obj.status,
            created_at=eval_obj.created_at,
            processing_completed_at=eval_obj.processing_completed_at,
            metrics=eval_obj.metrics,
            strength_count=len(eval_obj.strengths) if eval_obj.strengths else 0,
            growth_area_count=len(eval_obj.growth_opportunities) if eval_obj.growth_opportunities else 0,
        ))

    return {
        "evaluations": evaluations,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{instructor_id}/metrics/{metric_key}")
async def get_metric_trend(
    instructor_id: UUID,
    metric_key: str,
    db: AsyncSession = Depends(get_db),
):
    """Get trend data for a specific metric.

    Returns all data points for the given metric across completed evaluations.
    Useful for rendering a single metric's chart in detail.

    Valid metric_key values: wpm, pauses_per_10min, filler_words_per_min,
    questions_per_5min, tangent_percentage
    """
    # Validate metric key
    metric_def = next(
        (m for m in METRIC_DEFINITIONS if m["key"] == metric_key),
        None,
    )
    if not metric_def:
        valid_keys = [m["key"] for m in METRIC_DEFINITIONS]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metric '{metric_key}'. Valid: {valid_keys}",
        )

    # Query evaluations
    eval_result = await db.execute(
        select(Evaluation, Video.filename)
        .join(Video, Evaluation.video_id == Video.id, isouter=True)
        .where(
            Evaluation.instructor_id == instructor_id,
            Evaluation.status == "completed",
        )
        .order_by(Evaluation.created_at.asc())
    )
    rows = eval_result.all()

    # Build data points
    data_points = []
    for eval_obj, video_filename in rows:
        metrics = eval_obj.metrics or {}
        value = metrics.get(metric_key)
        if value is not None:
            data_points.append(MetricDataPoint(
                date=eval_obj.created_at,
                value=float(value),
                evaluation_id=eval_obj.id,
                video_filename=video_filename,
            ))

    # Calculate stats
    values = [dp.value for dp in data_points]
    trend = _compute_trend(values, metric_def.get("higher_is_better"))

    return MetricTrend(
        metric_name=metric_key,
        display_name=metric_def["display_name"],
        unit=metric_def["unit"],
        target_min=metric_def.get("target_min"),
        target_max=metric_def.get("target_max"),
        current_value=values[-1] if values else None,
        average_value=round(sum(values) / len(values), 1) if values else None,
        best_value=_best_value(values, metric_def.get("higher_is_better")),
        trend_direction=trend,
        data_points=data_points,
    )


# ------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------

def _build_metric_trends(rows: list) -> list[MetricTrend]:
    """Build trend data for all metrics from evaluation rows."""
    trends = []

    for metric_def in METRIC_DEFINITIONS:
        key = metric_def["key"]
        data_points = []

        for eval_obj, video_filename in rows:
            metrics = eval_obj.metrics or {}
            value = metrics.get(key)
            if value is not None:
                data_points.append(MetricDataPoint(
                    date=eval_obj.created_at,
                    value=float(value),
                    evaluation_id=eval_obj.id,
                    video_filename=video_filename,
                ))

        values = [dp.value for dp in data_points]
        higher_is_better = metric_def.get("higher_is_better")
        trend = _compute_trend(values, higher_is_better)

        trends.append(MetricTrend(
            metric_name=key,
            display_name=metric_def["display_name"],
            unit=metric_def["unit"],
            target_min=metric_def.get("target_min"),
            target_max=metric_def.get("target_max"),
            current_value=values[-1] if values else None,
            average_value=round(sum(values) / len(values), 1) if values else None,
            best_value=_best_value(values, higher_is_better),
            trend_direction=trend,
            data_points=data_points,
        ))

    return trends


def _compute_trend(values: list[float], higher_is_better: bool | None) -> str | None:
    """Determine if a metric is improving, declining, or stable.

    Uses a simple approach: compare the average of the last 2 values
    to the average of the first 2 values. If there aren't enough
    data points, return None (not enough data to determine trend).

    Args:
        values: Chronologically ordered metric values.
        higher_is_better: True if higher values = improvement,
                         False if lower = improvement,
                         None if it's a range target.
    """
    if len(values) < 2:
        return None

    # Compare recent vs. early values
    early = sum(values[:2]) / 2
    recent = sum(values[-2:]) / 2
    change = recent - early

    # Use a 5% threshold to distinguish real change from noise
    threshold = early * 0.05 if early != 0 else 0.5

    if abs(change) < threshold:
        return "stable"

    if higher_is_better is None:
        # Range target — can't determine "better" without context
        return "stable"
    elif higher_is_better:
        return "improving" if change > 0 else "declining"
    else:
        return "improving" if change < 0 else "declining"


def _best_value(values: list[float], higher_is_better: bool | None) -> float | None:
    """Get the best value from a list based on whether higher is better."""
    if not values:
        return None
    if higher_is_better is False:
        return min(values)
    elif higher_is_better is True:
        return max(values)
    else:
        # Range target — "best" isn't meaningful, return the median
        sorted_vals = sorted(values)
        mid = len(sorted_vals) // 2
        return sorted_vals[mid]


def _aggregate_themes(rows: list, field: str) -> list[dict]:
    """Find the most common strength/growth themes across evaluations.

    Counts how many times each titled item appears, so we can show
    "Your most consistent strength: Experience-Based Learning" or
    "Recurring growth area: Filler Word Reduction" on the dashboard.
    """
    title_counter = Counter()

    for eval_obj, _ in rows:
        items = getattr(eval_obj, field, None) or []
        for item in items:
            title = item.get("title", "").strip()
            if title:
                title_counter[title] += 1

    # Return top 5 most common, with count
    return [
        {"title": title, "count": count, "total_evaluations": len(rows)}
        for title, count in title_counter.most_common(5)
    ]

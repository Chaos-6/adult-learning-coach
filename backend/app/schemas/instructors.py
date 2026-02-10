"""
Pydantic schemas for instructor dashboard and performance tracking.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class MetricDataPoint(BaseModel):
    """A single metric value at a point in time.

    Used for building trend charts on the frontend.
    Example: {"date": "2026-01-15", "value": 145.0, "evaluation_id": "..."}
    """
    date: datetime
    value: float
    evaluation_id: UUID
    video_filename: Optional[str] = None


class MetricTrend(BaseModel):
    """Trend data for a single metric across evaluations.

    Contains the raw data points plus computed stats (average, best, latest).
    The frontend can use data_points for a line chart and the summary
    stats for dashboard cards.
    """
    metric_name: str
    display_name: str
    unit: str
    target_min: Optional[float] = None
    target_max: Optional[float] = None
    current_value: Optional[float] = None
    average_value: Optional[float] = None
    best_value: Optional[float] = None
    trend_direction: Optional[str] = None  # "improving", "declining", "stable"
    data_points: list[MetricDataPoint] = []


class EvaluationSummary(BaseModel):
    """Compact evaluation info for listing in the dashboard."""
    id: UUID
    video_id: UUID
    video_filename: Optional[str] = None
    status: str
    created_at: datetime
    processing_completed_at: Optional[datetime] = None
    metrics: Optional[dict] = None
    strength_count: int = 0
    growth_area_count: int = 0


class InstructorDashboard(BaseModel):
    """Aggregated dashboard data for an instructor.

    This is the main payload for the instructor's home screen.
    Contains summary stats, recent evaluations, and metric trends.
    """
    instructor_id: UUID
    instructor_name: str
    total_evaluations: int
    total_sessions_analyzed: int
    evaluations: list[EvaluationSummary]
    metric_trends: list[MetricTrend]
    top_strengths: list[dict]       # Most frequently identified strengths
    recurring_growth_areas: list[dict]  # Growth areas that appear repeatedly

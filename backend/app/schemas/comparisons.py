"""
Pydantic schemas for the Comparison API.

These validate request bodies and shape response bodies for the
comparison endpoints. Mirrors the evaluation schema patterns.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, field_validator


class ComparisonCreateRequest(BaseModel):
    """Request to create a new comparison.

    Requires at least 2 evaluation IDs and a comparison type.
    Set start_immediately=True to skip the draft state and begin analysis.
    """
    title: str
    comparison_type: str  # personal_performance, class_delivery, program_evaluation
    evaluation_ids: list[UUID]
    created_by_id: UUID
    organization_id: Optional[UUID] = None
    class_tag: Optional[str] = None
    anonymize_instructors: bool = False
    start_immediately: bool = True

    @field_validator("comparison_type")
    @classmethod
    def validate_comparison_type(cls, v: str) -> str:
        valid_types = ["personal_performance", "class_delivery", "program_evaluation"]
        if v not in valid_types:
            raise ValueError(f"comparison_type must be one of: {valid_types}")
        return v

    @field_validator("evaluation_ids")
    @classmethod
    def validate_evaluation_count(cls, v: list[UUID]) -> list[UUID]:
        if len(v) < 2:
            raise ValueError("At least 2 evaluations are required")
        if len(v) > 10:
            raise ValueError("Maximum 10 evaluations per comparison")
        return v


class EvaluationSummary(BaseModel):
    """Brief summary of a linked evaluation (nested in ComparisonResponse)."""
    evaluation_id: UUID
    display_order: int
    label: Optional[str] = None
    status: Optional[str] = None
    instructor_name: Optional[str] = None


class ComparisonResponse(BaseModel):
    """Full comparison details including linked evaluations."""
    id: UUID
    title: str
    comparison_type: str
    status: str
    organization_id: Optional[UUID] = None
    created_by_id: UUID
    class_tag: Optional[str] = None
    anonymize_instructors: bool
    has_report: bool
    metrics: Optional[dict] = None
    evaluations: list[EvaluationSummary] = []
    created_at: datetime
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ComparisonReportResponse(BaseModel):
    """Full comparison report with analysis results."""
    id: UUID
    title: str
    comparison_type: str
    status: str
    report_markdown: Optional[str] = None
    metrics: Optional[dict] = None
    strengths: Optional[list] = None
    growth_opportunities: Optional[list] = None
    evaluations: list[EvaluationSummary] = []
    created_at: datetime
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ComparisonListResponse(BaseModel):
    """Paginated list of comparisons."""
    items: list[ComparisonResponse]
    total: int
    page: int
    page_size: int

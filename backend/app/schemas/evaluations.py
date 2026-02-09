"""
Pydantic schemas for the Evaluation API.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class EvaluationCreateRequest(BaseModel):
    """Request to start a new evaluation."""
    video_id: UUID
    instructor_id: UUID


class EvaluationResponse(BaseModel):
    """Status and details of an evaluation."""
    id: UUID
    video_id: UUID
    instructor_id: UUID
    status: str
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    has_transcript: bool
    has_report: bool
    metrics: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TranscriptResponse(BaseModel):
    """Transcript content for a video."""
    id: UUID
    video_id: UUID
    transcript_text: str
    word_count: int
    speaker_count: Optional[int] = None
    processing_time_seconds: Optional[int] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}

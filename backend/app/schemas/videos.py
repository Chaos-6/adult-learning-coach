"""
Pydantic schemas for the Video API.

Schemas define the shape of data flowing through the API:
- Request schemas: what the client sends us
- Response schemas: what we send back

These are SEPARATE from SQLAlchemy models on purpose.
Models = database shape. Schemas = API shape.
They often overlap, but decoupling them means you can change
one without breaking the other.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# --- Response Schemas ---

class VideoResponse(BaseModel):
    """What we return when a client asks about a video."""
    id: UUID
    instructor_id: UUID
    filename: str
    file_size_bytes: int
    duration_seconds: Optional[int] = None
    format: Optional[str] = None
    upload_status: str
    uploaded_at: datetime
    metadata: Optional[dict] = Field(None, alias="metadata_")

    model_config = {"from_attributes": True, "populate_by_name": True}
    # from_attributes=True lets Pydantic read from SQLAlchemy model attributes
    # alias="metadata_" maps the ORM attribute name (metadata_) to our API field (metadata)
    # populate_by_name=True allows setting by either "metadata" or "metadata_"


class VideoUploadResponse(BaseModel):
    """Returned immediately after a successful upload."""
    video_id: UUID
    filename: str
    file_size_bytes: int
    format: str
    status: str
    message: str


class VideoListResponse(BaseModel):
    """Paginated list of videos."""
    videos: list[VideoResponse]
    total: int
    page: int
    page_size: int

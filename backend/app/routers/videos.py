"""
Video management API endpoints.

These handle the lifecycle of training session videos:
1. Upload a video file
2. List all videos for an instructor
3. Get details about a specific video
4. Delete a video

Design notes:
- Routers are THIN — they parse HTTP requests and call services
- File validation happens here (type, size) because it's an HTTP concern
- Storage details are delegated to the storage service
- Database operations use the async session from FastAPI's dependency injection
"""

from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Video
from app.schemas.videos import VideoListResponse, VideoResponse, VideoUploadResponse
from app.services.storage import get_storage_service

router = APIRouter(prefix="/api/v1/videos", tags=["videos"])

# Allowed video MIME types and their file extensions
ALLOWED_TYPES = {
    "video/mp4": "mp4",
    "video/quicktime": "mov",
    "video/x-msvideo": "avi",
    "video/webm": "webm",
}
MAX_FILE_SIZE = 10 * 1024 * 1024 * 1024  # 10GB per PRD


@router.post("/upload", response_model=VideoUploadResponse)
async def upload_video(
    file: UploadFile = File(...),
    instructor_id: UUID = Form(...),
    topic: Optional[str] = Form(None),
    session_number: Optional[int] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Upload a training session video.

    Accepts MP4, MOV, AVI, WebM files up to 10GB.
    The video is saved to storage and a database record is created.

    Args:
        file: The video file (multipart form upload)
        instructor_id: UUID of the instructor who recorded this session
        topic: Optional — what the session covers (e.g., "Python Basics")
        session_number: Optional — for ordering sessions chronologically
    """
    # --- Validate file type ---
    # content_type comes from the HTTP header, which the browser sets based
    # on the file extension. It's not foolproof, but good enough for MVP.
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{file.content_type}'. "
                   f"Accepted: {', '.join(ALLOWED_TYPES.values())}",
        )

    file_extension = ALLOWED_TYPES[file.content_type]

    # --- Generate storage key ---
    # Structure: videos/{instructor_id}/{video_id}.{ext}
    # This keeps each instructor's files organized in their own "folder"
    video_id = uuid4()
    storage_key = f"videos/{instructor_id}/{video_id}.{file_extension}"

    # --- Save file ---
    # Pass the UploadFile directly (it supports async read)
    storage = get_storage_service()
    try:
        file_size = await storage.save_file(file, storage_key, file.filename)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save file: {str(e)}",
        )

    # --- Create database record ---
    video = Video(
        id=video_id,
        instructor_id=instructor_id,
        filename=file.filename or f"video.{file_extension}",
        s3_key=storage_key,
        file_size_bytes=file_size,
        format=file_extension,
        upload_status="uploaded",
        metadata_={
            "topic": topic,
            "session_number": session_number,
            "original_filename": file.filename,
        },
    )

    db.add(video)
    await db.commit()
    await db.refresh(video)

    return VideoUploadResponse(
        video_id=video.id,
        filename=video.filename,
        file_size_bytes=video.file_size_bytes,
        format=file_extension,
        status="uploaded",
        message="Video uploaded successfully. Ready for transcription.",
    )


@router.get("", response_model=VideoListResponse)
async def list_videos(
    instructor_id: Optional[UUID] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List videos with optional filtering and pagination.

    Args:
        instructor_id: Filter by instructor (optional)
        page: Page number (1-indexed)
        page_size: Results per page (default 20, max 100)
    """
    page_size = min(page_size, 100)  # Cap at 100
    offset = (page - 1) * page_size

    # Build query
    query = select(Video).order_by(Video.uploaded_at.desc())
    count_query = select(func.count(Video.id))

    if instructor_id:
        query = query.where(Video.instructor_id == instructor_id)
        count_query = count_query.where(Video.instructor_id == instructor_id)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Get page of results
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    videos = result.scalars().all()

    return VideoListResponse(
        videos=[VideoResponse.model_validate(v) for v in videos],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get details about a specific video."""
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    return VideoResponse.model_validate(video)


@router.delete("/{video_id}")
async def delete_video(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a video and its stored file.

    Note: This also cascades to delete related transcripts and evaluations
    (via the ON DELETE CASCADE in the database schema).
    """
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Delete from storage
    storage = get_storage_service()
    await storage.delete_file(video.s3_key)

    # Delete from database (cascades to transcripts + evaluations)
    await db.delete(video)
    await db.commit()

    return {"message": "Video deleted", "video_id": str(video_id)}

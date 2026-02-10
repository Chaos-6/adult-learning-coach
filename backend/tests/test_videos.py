"""
Integration tests for the Videos API.

Tests the upload, list, get, and delete endpoints.
We test against the real database with real HTTP requests
via httpx's async test client.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_videos_empty(client: AsyncClient):
    """GET /api/v1/videos returns an empty list when no videos match."""
    # Use a random instructor_id that won't have any videos
    random_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/videos?instructor_id={random_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["videos"] == []
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_list_videos_with_data(client: AsyncClient, test_video):
    """GET /api/v1/videos returns videos when they exist."""
    response = await client.get(
        f"/api/v1/videos?instructor_id={test_video.instructor_id}"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    # Find our test video in the results
    video_ids = [v["id"] for v in data["videos"]]
    assert str(test_video.id) in video_ids


@pytest.mark.asyncio
async def test_get_video_success(client: AsyncClient, test_video):
    """GET /api/v1/videos/{id} returns video details."""
    response = await client.get(f"/api/v1/videos/{test_video.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(test_video.id)
    assert data["filename"] == "test_session.mp4"
    assert data["file_size_bytes"] == 1024 * 1024


@pytest.mark.asyncio
async def test_get_video_not_found(client: AsyncClient):
    """GET /api/v1/videos/{id} returns 404 for nonexistent video."""
    fake_id = uuid.uuid4()
    response = await client.get(f"/api/v1/videos/{fake_id}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_videos_pagination(client: AsyncClient, test_video):
    """GET /api/v1/videos supports pagination params."""
    response = await client.get("/api/v1/videos?page=1&page_size=5")

    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 5
    # page_size should be capped at what we requested
    assert len(data["videos"]) <= 5


@pytest.mark.asyncio
async def test_upload_video_wrong_type(client: AsyncClient, test_instructor):
    """POST /api/v1/videos/upload rejects non-video files."""
    response = await client.post(
        "/api/v1/videos/upload",
        data={"instructor_id": str(test_instructor.id)},
        files={"file": ("test.txt", b"hello world", "text/plain")},
    )

    assert response.status_code == 400
    assert "Invalid file type" in response.json()["detail"]

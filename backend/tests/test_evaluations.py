"""
Integration tests for the Evaluations API.

Tests the create, get, report, and PDF endpoints.
The pipeline itself (transcription + analysis) isn't tested here —
those are external services that would need mocking in unit tests.
These tests verify the HTTP layer and database interactions.
"""

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_evaluation_success(client: AsyncClient, test_evaluation):
    """GET /api/v1/evaluations/{id} returns evaluation status."""
    response = await client.get(f"/api/v1/evaluations/{test_evaluation.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(test_evaluation.id)
    assert data["status"] == "completed"
    assert data["has_transcript"] is True
    assert data["has_report"] is True
    assert data["metrics"]["wpm"] == 142.5


@pytest.mark.asyncio
async def test_get_evaluation_not_found(client: AsyncClient):
    """GET /api/v1/evaluations/{id} returns 404 for nonexistent evaluation."""
    fake_id = uuid.uuid4()
    response = await client.get(f"/api/v1/evaluations/{fake_id}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_evaluation_video_not_found(client: AsyncClient, test_instructor):
    """POST /api/v1/evaluations returns 404 when video doesn't exist."""
    response = await client.post(
        "/api/v1/evaluations",
        json={
            "video_id": str(uuid.uuid4()),
            "instructor_id": str(test_instructor.id),
        },
    )

    assert response.status_code == 404
    assert "Video not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_evaluation_duplicate(
    client: AsyncClient, test_evaluation, test_video, test_instructor
):
    """POST /api/v1/evaluations returns 409 for duplicate evaluation."""
    response = await client.post(
        "/api/v1/evaluations",
        json={
            "video_id": str(test_video.id),
            "instructor_id": str(test_instructor.id),
        },
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_report_success(client: AsyncClient, test_evaluation):
    """GET /api/v1/evaluations/{id}/report returns the coaching report."""
    response = await client.get(
        f"/api/v1/evaluations/{test_evaluation.id}/report"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert "Coaching Report" in data["report_markdown"]
    assert data["metrics"]["wpm"] == 142.5
    assert len(data["strengths"]) == 2
    assert data["strengths"][0]["title"] == "Clear Explanations"
    assert len(data["growth_opportunities"]) == 1


@pytest.mark.asyncio
async def test_get_report_not_ready(client: AsyncClient, test_video, test_instructor):
    """GET /api/v1/evaluations/{id}/report returns 400 when report isn't ready."""
    from app.models import Evaluation
    from app.database import AsyncSessionLocal

    # Create a queued evaluation (no report yet) via its own session
    eval_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        evaluation = Evaluation(
            id=eval_id,
            video_id=test_video.id,
            instructor_id=test_instructor.id,
            status="queued",
        )
        session.add(evaluation)
        await session.commit()

    response = await client.get(f"/api/v1/evaluations/{eval_id}/report")

    assert response.status_code == 400
    assert "not ready" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_transcript_success(client: AsyncClient, test_evaluation):
    """GET /api/v1/evaluations/{id}/transcript returns the transcript."""
    response = await client.get(
        f"/api/v1/evaluations/{test_evaluation.id}/transcript"
    )

    assert response.status_code == 200
    data = response.json()
    assert "Hello class" in data["transcript_text"]
    assert data["status"] == "completed"


@pytest.mark.asyncio
async def test_download_report_pdf(client: AsyncClient, test_evaluation):
    """GET /api/v1/evaluations/{id}/report/pdf returns a PDF file."""
    response = await client.get(
        f"/api/v1/evaluations/{test_evaluation.id}/report/pdf"
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    # PDF files start with %PDF
    assert response.content[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_download_worksheet_pdf(client: AsyncClient, test_evaluation):
    """GET /api/v1/evaluations/{id}/worksheet/pdf returns a PDF file."""
    response = await client.get(
        f"/api/v1/evaluations/{test_evaluation.id}/worksheet/pdf"
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:5] == b"%PDF-"

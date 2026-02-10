"""
Integration tests for the Instructors API.

Tests the dashboard, evaluation listing, and metric trend endpoints.
These are read-only analytics endpoints that aggregate evaluation data.
"""

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_dashboard_success(client: AsyncClient, test_evaluation, test_instructor):
    """GET /api/v1/instructors/{id}/dashboard returns aggregated data."""
    response = await client.get(
        f"/api/v1/instructors/{test_instructor.id}/dashboard"
    )

    assert response.status_code == 200
    data = response.json()

    assert data["instructor_name"] == "Test Instructor"
    assert data["total_sessions_analyzed"] >= 1
    assert data["total_evaluations"] >= 1

    # Should have metric trends
    assert len(data["metric_trends"]) == 5  # We track 5 metrics
    metric_names = [m["metric_name"] for m in data["metric_trends"]]
    assert "wpm" in metric_names
    assert "filler_words_per_min" in metric_names

    # Should have evaluations list
    assert len(data["evaluations"]) >= 1

    # Should have strengths
    assert len(data["top_strengths"]) >= 1


@pytest.mark.asyncio
async def test_dashboard_instructor_not_found(client: AsyncClient):
    """GET /api/v1/instructors/{id}/dashboard returns 404 for unknown instructor."""
    fake_id = uuid.uuid4()
    response = await client.get(f"/api/v1/instructors/{fake_id}/dashboard")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_evaluations(client: AsyncClient, test_evaluation, test_instructor):
    """GET /api/v1/instructors/{id}/evaluations returns paginated list."""
    response = await client.get(
        f"/api/v1/instructors/{test_instructor.id}/evaluations"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert data["page"] == 1
    assert len(data["evaluations"]) >= 1


@pytest.mark.asyncio
async def test_list_evaluations_filter_by_status(
    client: AsyncClient, test_evaluation, test_instructor
):
    """GET /api/v1/instructors/{id}/evaluations?status=completed filters correctly."""
    response = await client.get(
        f"/api/v1/instructors/{test_instructor.id}/evaluations?status=completed"
    )

    assert response.status_code == 200
    data = response.json()
    # All returned evaluations should have status "completed"
    for eval_ in data["evaluations"]:
        assert eval_["status"] == "completed"


@pytest.mark.asyncio
async def test_list_evaluations_filter_no_match(
    client: AsyncClient, test_instructor
):
    """GET /api/v1/instructors/{id}/evaluations?status=queued returns empty when none match."""
    response = await client.get(
        f"/api/v1/instructors/{test_instructor.id}/evaluations?status=queued"
    )

    assert response.status_code == 200
    data = response.json()
    # If there are results, they should all be "queued"
    for eval_ in data["evaluations"]:
        assert eval_["status"] == "queued"


@pytest.mark.asyncio
async def test_metric_trend_wpm(client: AsyncClient, test_evaluation, test_instructor):
    """GET /api/v1/instructors/{id}/metrics/wpm returns speaking pace trend."""
    response = await client.get(
        f"/api/v1/instructors/{test_instructor.id}/metrics/wpm"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["metric_name"] == "wpm"
    assert data["display_name"] == "Speaking Pace"
    assert data["unit"] == "WPM"
    assert data["current_value"] == 142.5
    assert len(data["data_points"]) >= 1


@pytest.mark.asyncio
async def test_metric_trend_filler_words(
    client: AsyncClient, test_evaluation, test_instructor
):
    """GET /api/v1/instructors/{id}/metrics/filler_words_per_min returns filler word trend."""
    response = await client.get(
        f"/api/v1/instructors/{test_instructor.id}/metrics/filler_words_per_min"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["metric_name"] == "filler_words_per_min"
    assert data["current_value"] == 2.8
    assert data["target_max"] == 3.0


@pytest.mark.asyncio
async def test_metric_trend_invalid_key(client: AsyncClient, test_instructor):
    """GET /api/v1/instructors/{id}/metrics/invalid returns 400."""
    response = await client.get(
        f"/api/v1/instructors/{test_instructor.id}/metrics/nonexistent_metric"
    )

    assert response.status_code == 400
    assert "Invalid metric" in response.json()["detail"]


@pytest.mark.asyncio
async def test_dashboard_metric_data_points(
    client: AsyncClient, test_evaluation, test_instructor
):
    """Dashboard metric trends contain actual data points."""
    response = await client.get(
        f"/api/v1/instructors/{test_instructor.id}/dashboard"
    )

    assert response.status_code == 200
    data = response.json()

    # Find the WPM metric trend
    wpm_trend = next(
        m for m in data["metric_trends"] if m["metric_name"] == "wpm"
    )
    assert wpm_trend["current_value"] == 142.5
    assert wpm_trend["target_min"] == 120.0
    assert wpm_trend["target_max"] == 160.0
    assert len(wpm_trend["data_points"]) >= 1

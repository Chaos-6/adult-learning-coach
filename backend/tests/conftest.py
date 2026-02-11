"""
Test fixtures shared across all integration tests.

Architecture:
- We use the REAL database (not SQLite) because we depend on PostgreSQL
  features (JSONB, UUID columns). SQLite would give false confidence.
- pytest.ini sets asyncio_default_fixture_loop_scope = session so all
  tests share ONE event loop. This is critical because asyncpg binds
  connections to the event loop that created them, and the app creates
  its engine at import time.
- Seed data is committed via the app's own AsyncSessionLocal.
- The HTTP test client uses the real FastAPI app with its own sessions.
- Each test gets seed data with unique UUIDs to avoid collisions.
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.database import AsyncSessionLocal, Base, engine
from app.main import app
from app.models import (
    Comparison,
    ComparisonEvaluation,
    Evaluation,
    Organization,
    Transcript,
    User,
    Video,
)


@pytest_asyncio.fixture(scope="session")
async def setup_db():
    """Create all tables once before the test session."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def client(setup_db):
    """Async HTTP test client.

    Uses the real FastAPI app with its own database sessions.
    No dependency overrides needed — the app manages its own sessions.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# --- Seed data fixtures ---
# Each fixture opens its own session, commits, and closes.
# Data is then visible to the app's sessions (same database, committed).

@pytest_asyncio.fixture
async def test_org(setup_db):
    """Create a test organization."""
    org = Organization(
        id=uuid.uuid4(),
        name="Test University",
        subscription_tier="professional",
    )
    async with AsyncSessionLocal() as session:
        session.add(org)
        await session.commit()
        await session.refresh(org)
    return org


@pytest_asyncio.fixture
async def test_instructor(test_org):
    """Create a test instructor user."""
    user = User(
        id=uuid.uuid4(),
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="not-a-real-hash",
        display_name="Test Instructor",
        role="instructor",
        organization_id=test_org.id,
    )
    async with AsyncSessionLocal() as session:
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_video(test_instructor):
    """Create a test video record (no actual file — just the DB record)."""
    video = Video(
        id=uuid.uuid4(),
        instructor_id=test_instructor.id,
        filename="test_session.mp4",
        s3_key=f"videos/{test_instructor.id}/test.mp4",
        file_size_bytes=1024 * 1024,  # 1MB
        format="mp4",
        upload_status="uploaded",
    )
    async with AsyncSessionLocal() as session:
        session.add(video)
        await session.commit()
        await session.refresh(video)
    return video


@pytest_asyncio.fixture
async def test_transcript(test_video):
    """Create a test transcript for the test video."""
    transcript = Transcript(
        id=uuid.uuid4(),
        video_id=test_video.id,
        transcript_text="[00:00:00] Speaker A: Hello class, welcome to today's session.",
        word_count=8,
        speaker_count=1,
        processing_time_seconds=5,
        status="completed",
    )
    async with AsyncSessionLocal() as session:
        session.add(transcript)
        await session.commit()
        await session.refresh(transcript)
    return transcript


@pytest_asyncio.fixture
async def test_evaluation(test_video, test_instructor, test_transcript):
    """Create a completed evaluation with mock report data."""
    evaluation = Evaluation(
        id=uuid.uuid4(),
        video_id=test_video.id,
        instructor_id=test_instructor.id,
        transcript_id=test_transcript.id,
        status="completed",
        processing_started_at=datetime.now(timezone.utc),
        processing_completed_at=datetime.now(timezone.utc),
        report_markdown="## Coaching Report\n\nThis is a test report.",
        metrics={
            "wpm": 142.5,
            "filler_words_per_min": 2.8,
            "questions_per_5min": 1.5,
            "pauses_per_10min": 4.5,
            "tangent_percentage": 8.0,
        },
        strengths=[
            {"title": "Clear Explanations", "description": "Good use of examples."},
            {"title": "Active Listening", "description": "Responds to student cues."},
        ],
        growth_opportunities=[
            {"title": "Pacing", "description": "Could slow down in complex sections."},
        ],
    )
    async with AsyncSessionLocal() as session:
        session.add(evaluation)
        await session.commit()
        await session.refresh(evaluation)
    return evaluation


@pytest_asyncio.fixture
async def test_evaluation_2(test_instructor, test_org):
    """Create a second completed evaluation for comparison tests.

    This creates its own video + transcript chain so it's fully independent
    from the first evaluation. Slightly different metrics let us verify
    that comparisons can detect variation.
    """
    video = Video(
        id=uuid.uuid4(),
        instructor_id=test_instructor.id,
        filename="test_session_2.mp4",
        s3_key=f"videos/{test_instructor.id}/test2.mp4",
        file_size_bytes=2 * 1024 * 1024,
        format="mp4",
        upload_status="transcribed",
    )
    transcript = Transcript(
        id=uuid.uuid4(),
        video_id=video.id,
        transcript_text="[00:00:00] Speaker A: Welcome back to session two.",
        word_count=7,
        speaker_count=1,
        processing_time_seconds=4,
        status="completed",
    )
    evaluation = Evaluation(
        id=uuid.uuid4(),
        video_id=video.id,
        instructor_id=test_instructor.id,
        transcript_id=transcript.id,
        status="completed",
        processing_started_at=datetime.now(timezone.utc),
        processing_completed_at=datetime.now(timezone.utc),
        report_markdown="## Coaching Report\n\nThis is a second test report.",
        metrics={
            "wpm": 155.0,
            "filler_words_per_min": 1.5,
            "questions_per_5min": 2.0,
            "pauses_per_10min": 5.0,
            "tangent_percentage": 5.0,
        },
        strengths=[
            {"title": "Engagement", "description": "Great question frequency."},
        ],
        growth_opportunities=[
            {"title": "Time Management", "description": "Went over by 5 minutes."},
        ],
    )
    async with AsyncSessionLocal() as session:
        # Insert in FK dependency order: video → transcript → evaluation.
        # We set raw UUID FKs (not ORM relationships), so SQLAlchemy
        # can't infer the correct insertion order automatically.
        session.add(video)
        await session.commit()

        session.add(transcript)
        await session.commit()

        session.add(evaluation)
        await session.commit()
        await session.refresh(evaluation)
    return evaluation


@pytest_asyncio.fixture
async def test_comparison(test_evaluation, test_evaluation_2, test_instructor, test_org):
    """Create a comparison linking two evaluations."""
    comparison = Comparison(
        id=uuid.uuid4(),
        title="Q1 Performance Review",
        comparison_type="personal_performance",
        status="completed",
        organization_id=test_org.id,
        created_by_id=test_instructor.id,
        report_markdown="## Comparison Report\n\nPerformance improved between sessions.",
        metrics={"avg_wpm": 148.75, "wpm_trend": "improving"},
        strengths=[{"title": "Consistency", "description": "Maintained strengths."}],
        growth_opportunities=[{"title": "Pacing", "description": "Still needs work."}],
        processing_started_at=datetime.now(timezone.utc),
        processing_completed_at=datetime.now(timezone.utc),
    )
    link1 = ComparisonEvaluation(
        id=uuid.uuid4(),
        comparison_id=comparison.id,
        evaluation_id=test_evaluation.id,
        display_order=0,
        label="Session 1",
    )
    link2 = ComparisonEvaluation(
        id=uuid.uuid4(),
        comparison_id=comparison.id,
        evaluation_id=test_evaluation_2.id,
        display_order=1,
        label="Session 2",
    )
    async with AsyncSessionLocal() as session:
        # Comparison must exist before join table entries can reference it
        session.add(comparison)
        await session.commit()

        session.add(link1)
        session.add(link2)
        await session.commit()
        await session.refresh(comparison)
    return comparison

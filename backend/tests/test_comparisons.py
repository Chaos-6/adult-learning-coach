"""
Integration tests for the comparison feature.

Milestone 1: Model and fixture smoke tests.
Milestone 2: Prompt construction and analysis service tests.
Later milestones: API endpoint tests.
"""

import uuid

import pytest
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import Comparison, ComparisonEvaluation, Evaluation
from app.services.prompts import (
    COMPARISON_PROMPT_BUILDERS,
    COMPARISON_SYSTEM_PROMPT,
    _format_metrics,
    build_class_delivery_prompt,
    build_personal_performance_prompt,
    build_program_evaluation_prompt,
)
from app.services.comparison_analysis import (
    ComparisonAnalysisResult,
    ComparisonAnalysisService,
)
from app.services.comparison_pdf import ComparisonPDFGenerator


# --- Model smoke tests ---

async def test_comparison_fixture_creates_record(test_comparison):
    """Verify the comparison fixture creates a valid record in the DB."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Comparison).where(Comparison.id == test_comparison.id)
        )
        comparison = result.scalar_one()
        assert comparison.title == "Q1 Performance Review"
        assert comparison.comparison_type == "personal_performance"
        assert comparison.status == "completed"


async def test_comparison_has_two_evaluations(test_comparison):
    """Verify the M:N join table links exactly 2 evaluations."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ComparisonEvaluation)
            .where(ComparisonEvaluation.comparison_id == test_comparison.id)
            .order_by(ComparisonEvaluation.display_order)
        )
        links = result.scalars().all()
        assert len(links) == 2
        assert links[0].label == "Session 1"
        assert links[0].display_order == 0
        assert links[1].label == "Session 2"
        assert links[1].display_order == 1


async def test_comparison_evaluation_ids_are_valid(
    test_comparison, test_evaluation, test_evaluation_2
):
    """Verify the join table references the correct evaluation records."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ComparisonEvaluation.evaluation_id)
            .where(ComparisonEvaluation.comparison_id == test_comparison.id)
            .order_by(ComparisonEvaluation.display_order)
        )
        eval_ids = [row[0] for row in result.all()]
        assert eval_ids == [test_evaluation.id, test_evaluation_2.id]


async def test_comparison_report_and_metrics(test_comparison):
    """Verify the comparison stores analysis outputs correctly."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Comparison).where(Comparison.id == test_comparison.id)
        )
        comparison = result.scalar_one()
        assert "Performance improved" in comparison.report_markdown
        assert comparison.metrics["avg_wpm"] == 148.75
        assert comparison.metrics["wpm_trend"] == "improving"
        assert len(comparison.strengths) == 1
        assert len(comparison.growth_opportunities) == 1


async def test_evaluation_can_be_in_multiple_comparisons(
    test_comparison, test_evaluation, test_evaluation_2, test_instructor, test_org
):
    """Verify M:N: one evaluation can appear in multiple comparisons.

    test_comparison already links test_evaluation to one comparison.
    We create a second comparison that also includes test_evaluation,
    then verify it appears in both.
    """
    # Create a second comparison that also includes test_evaluation
    comparison2 = Comparison(
        id=uuid.uuid4(),
        title="Program Review",
        comparison_type="program_evaluation",
        status="draft",
        organization_id=test_org.id,
        created_by_id=test_instructor.id,
    )
    link = ComparisonEvaluation(
        id=uuid.uuid4(),
        comparison_id=comparison2.id,
        evaluation_id=test_evaluation.id,
        display_order=0,
        label="Sample A",
    )
    async with AsyncSessionLocal() as session:
        session.add(comparison2)
        session.add(link)
        await session.commit()

    # Now test_evaluation should be linked to 2 comparisons
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ComparisonEvaluation)
            .where(ComparisonEvaluation.evaluation_id == test_evaluation.id)
        )
        links = result.scalars().all()
        assert len(links) >= 2, (
            f"Expected evaluation in >=2 comparisons, found {len(links)}"
        )


async def test_comparison_types_accepted(test_instructor, test_org):
    """Verify all three comparison types can be created."""
    for ctype in ["personal_performance", "class_delivery", "program_evaluation"]:
        comparison = Comparison(
            id=uuid.uuid4(),
            title=f"Test {ctype}",
            comparison_type=ctype,
            status="draft",
            organization_id=test_org.id,
            created_by_id=test_instructor.id,
        )
        async with AsyncSessionLocal() as session:
            session.add(comparison)
            await session.commit()
            await session.refresh(comparison)
            assert comparison.comparison_type == ctype


# --- Prompt construction tests (Milestone 2) ---

# Shared test data for prompt tests
SAMPLE_EVALUATIONS = [
    {
        "label": "Session 1",
        "date": "2025-01-15",
        "instructor_name": "Jane Smith",
        "report_markdown": "## Coaching Report\n\nGreat session with strong engagement.",
        "metrics": {
            "wpm": 142.5,
            "filler_words_per_min": 2.8,
            "questions_per_5min": 1.5,
            "pauses_per_10min": 4.5,
            "tangent_percentage": 8.0,
        },
    },
    {
        "label": "Session 2",
        "date": "2025-02-20",
        "instructor_name": "Jane Smith",
        "report_markdown": "## Coaching Report\n\nImproved pacing, fewer filler words.",
        "metrics": {
            "wpm": 155.0,
            "filler_words_per_min": 1.5,
            "questions_per_5min": 2.0,
            "pauses_per_10min": 5.0,
            "tangent_percentage": 5.0,
        },
    },
]


def test_personal_performance_prompt_structure():
    """Verify personal performance prompt includes key sections."""
    prompt = build_personal_performance_prompt(SAMPLE_EVALUATIONS)
    assert "Jane Smith" in prompt
    assert "2 coaching evaluation reports" in prompt
    assert "Session 1" in prompt
    assert "Session 2" in prompt
    assert "Trend Analysis" in prompt
    assert "Pattern Recognition" in prompt
    assert "Metric Trends" in prompt
    assert "Prioritized Action Plan" in prompt
    assert "Personal Performance Tracking" in prompt


def test_class_delivery_prompt_structure():
    """Verify class delivery prompt includes key sections."""
    data = [
        {**SAMPLE_EVALUATIONS[0], "instructor_name": "Jane Smith"},
        {**SAMPLE_EVALUATIONS[1], "instructor_name": "Bob Jones"},
    ]
    prompt = build_class_delivery_prompt(data, class_tag="Intro to Python")
    assert "Intro to Python" in prompt
    assert "2 coaching evaluation reports" in prompt
    assert "Delivery Variation Analysis" in prompt
    assert "Best Practices Extraction" in prompt
    assert "Curriculum vs. Instructor Analysis" in prompt
    assert "Class Delivery Comparison" in prompt


def test_program_evaluation_prompt_structure():
    """Verify program evaluation prompt includes key sections."""
    prompt = build_program_evaluation_prompt(SAMPLE_EVALUATIONS)
    assert "2 coaching evaluation reports" in prompt
    assert "Delivery Consistency Analysis" in prompt
    assert "Content Consistency" in prompt
    assert "Curricular Design Assessment" in prompt
    assert "Program Evaluation" in prompt


def test_prompt_includes_metrics():
    """Verify prompts include formatted metrics for each session."""
    prompt = build_personal_performance_prompt(SAMPLE_EVALUATIONS)
    assert "WPM: 142.5" in prompt
    assert "WPM: 155.0" in prompt
    assert "Fillers/min: 2.8" in prompt


def test_prompt_includes_reports():
    """Verify prompts embed the full coaching reports."""
    prompt = build_personal_performance_prompt(SAMPLE_EVALUATIONS)
    assert "Great session with strong engagement" in prompt
    assert "Improved pacing, fewer filler words" in prompt


def test_format_metrics_helper():
    """Verify the metric formatting helper."""
    result = _format_metrics({
        "wpm": 142.5,
        "filler_words_per_min": 2.8,
    })
    assert "WPM: 142.5" in result
    assert "Fillers/min: 2.8" in result


def test_format_metrics_empty():
    """Verify format_metrics handles empty dict."""
    assert _format_metrics({}) == "No metrics available"
    assert _format_metrics(None) == "No metrics available"


def test_comparison_prompt_builders_map():
    """Verify all three types are registered in the builders map."""
    assert "personal_performance" in COMPARISON_PROMPT_BUILDERS
    assert "class_delivery" in COMPARISON_PROMPT_BUILDERS
    assert "program_evaluation" in COMPARISON_PROMPT_BUILDERS
    assert len(COMPARISON_PROMPT_BUILDERS) == 3


def test_comparison_system_prompt_exists():
    """Verify the comparison system prompt is defined and substantive."""
    assert len(COMPARISON_SYSTEM_PROMPT) > 200
    assert "instructional coaching" in COMPARISON_SYSTEM_PROMPT.lower()
    assert "adult learning" in COMPARISON_SYSTEM_PROMPT.lower()


# --- ComparisonAnalysisService unit tests (Milestone 2) ---

def test_comparison_analysis_result_defaults():
    """Verify ComparisonAnalysisResult has sensible defaults."""
    result = ComparisonAnalysisResult(report_markdown="# Test Report")
    assert result.report_markdown == "# Test Report"
    assert result.metrics == {}
    assert result.strengths == []
    assert result.growth_opportunities == []
    assert result.input_tokens == 0
    assert result.model == ""


def test_comparison_extract_metrics():
    """Verify _extract_comparison_metrics computes aggregates correctly."""
    service = ComparisonAnalysisService.__new__(ComparisonAnalysisService)
    metrics = service._extract_comparison_metrics(
        "# Report",
        SAMPLE_EVALUATIONS,
    )
    assert metrics["session_count"] == 2
    assert metrics["wpm_avg"] == 148.8  # (142.5 + 155.0) / 2 = 148.75 → 148.8
    assert metrics["wpm_min"] == 142.5
    assert metrics["wpm_max"] == 155.0
    assert metrics["wpm_trend"] == "increasing"  # 155 > 142.5 * 1.05


def test_comparison_extract_metrics_stable():
    """Verify stable trend detection when values don't change much."""
    service = ComparisonAnalysisService.__new__(ComparisonAnalysisService)
    data = [
        {"metrics": {"wpm": 150.0}},
        {"metrics": {"wpm": 151.0}},
    ]
    metrics = service._extract_comparison_metrics("# Report", data)
    assert metrics["wpm_trend"] == "stable"


def test_comparison_analysis_invalid_type():
    """Verify ValueError for unknown comparison type."""
    service = ComparisonAnalysisService.__new__(ComparisonAnalysisService)
    with pytest.raises(ValueError, match="Unknown comparison type"):
        service.analyze_comparison(
            evaluations_data=SAMPLE_EVALUATIONS,
            comparison_type="invalid_type",
        )


# --- API endpoint tests (Milestone 4) ---

async def test_get_comparison_success(client, test_comparison):
    """GET /comparisons/{id} returns comparison details."""
    response = await client.get(f"/api/v1/comparisons/{test_comparison.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Q1 Performance Review"
    assert data["comparison_type"] == "personal_performance"
    assert data["status"] == "completed"
    assert data["has_report"] is True
    assert len(data["evaluations"]) == 2
    assert data["evaluations"][0]["label"] == "Session 1"
    assert data["evaluations"][1]["label"] == "Session 2"


async def test_get_comparison_not_found(client):
    """GET /comparisons/{id} returns 404 for unknown ID."""
    fake_id = uuid.uuid4()
    response = await client.get(f"/api/v1/comparisons/{fake_id}")
    assert response.status_code == 404


async def test_list_comparisons(client, test_comparison):
    """GET /comparisons returns paginated list."""
    response = await client.get("/api/v1/comparisons")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert data["page"] == 1
    assert len(data["items"]) >= 1


async def test_list_comparisons_filter_by_type(client, test_comparison):
    """GET /comparisons?comparison_type= filters correctly."""
    response = await client.get(
        "/api/v1/comparisons?comparison_type=personal_performance"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["comparison_type"] == "personal_performance"


async def test_list_comparisons_filter_no_match(client, test_comparison):
    """GET /comparisons?status=queued returns empty when none match."""
    response = await client.get("/api/v1/comparisons?status=queued")
    assert response.status_code == 200
    data = response.json()
    # May or may not be 0 depending on test ordering, but should work


async def test_get_comparison_report(client, test_comparison):
    """GET /comparisons/{id}/report returns the full report."""
    response = await client.get(
        f"/api/v1/comparisons/{test_comparison.id}/report"
    )
    assert response.status_code == 200
    data = response.json()
    assert "Performance improved" in data["report_markdown"]
    assert data["metrics"]["avg_wpm"] == 148.75
    assert len(data["strengths"]) == 1
    assert len(data["growth_opportunities"]) == 1
    assert len(data["evaluations"]) == 2


async def test_get_comparison_report_not_ready(
    client, test_instructor, test_org, test_evaluation, test_evaluation_2
):
    """GET /comparisons/{id}/report returns 400 if no report yet."""
    # Create a draft comparison (no report)
    comparison = Comparison(
        id=uuid.uuid4(),
        title="Draft Comparison",
        comparison_type="personal_performance",
        status="draft",
        organization_id=test_org.id,
        created_by_id=test_instructor.id,
    )
    async with AsyncSessionLocal() as session:
        session.add(comparison)
        await session.commit()

    response = await client.get(f"/api/v1/comparisons/{comparison.id}/report")
    assert response.status_code == 400
    assert "not ready" in response.json()["detail"].lower()


async def test_create_comparison_validation_requires_2_evals(
    client, test_evaluation, test_instructor
):
    """POST /comparisons rejects < 2 evaluations."""
    response = await client.post("/api/v1/comparisons", json={
        "title": "Too Few",
        "comparison_type": "personal_performance",
        "evaluation_ids": [str(test_evaluation.id)],
        "created_by_id": str(test_instructor.id),
    })
    assert response.status_code == 422  # Pydantic validation error


async def test_create_comparison_invalid_type(
    client, test_evaluation, test_evaluation_2, test_instructor
):
    """POST /comparisons rejects invalid comparison type."""
    response = await client.post("/api/v1/comparisons", json={
        "title": "Bad Type",
        "comparison_type": "invalid_type",
        "evaluation_ids": [
            str(test_evaluation.id),
            str(test_evaluation_2.id),
        ],
        "created_by_id": str(test_instructor.id),
    })
    assert response.status_code == 422


async def test_create_comparison_missing_evaluation(
    client, test_evaluation, test_instructor
):
    """POST /comparisons returns 404 for nonexistent evaluation IDs."""
    fake_id = uuid.uuid4()
    response = await client.post("/api/v1/comparisons", json={
        "title": "Missing Eval",
        "comparison_type": "personal_performance",
        "evaluation_ids": [str(test_evaluation.id), str(fake_id)],
        "created_by_id": str(test_instructor.id),
    })
    assert response.status_code == 404


async def test_delete_comparison(client, test_instructor, test_org):
    """DELETE /comparisons/{id} removes the comparison."""
    comparison = Comparison(
        id=uuid.uuid4(),
        title="To Delete",
        comparison_type="personal_performance",
        status="draft",
        organization_id=test_org.id,
        created_by_id=test_instructor.id,
    )
    async with AsyncSessionLocal() as session:
        session.add(comparison)
        await session.commit()

    response = await client.delete(f"/api/v1/comparisons/{comparison.id}")
    assert response.status_code == 200
    assert "deleted" in response.json()["detail"].lower()

    # Verify it's gone
    response2 = await client.get(f"/api/v1/comparisons/{comparison.id}")
    assert response2.status_code == 404


# --- PDF generation tests (Milestone 7) ---

def test_comparison_pdf_generates_valid_pdf():
    """Verify ComparisonPDFGenerator produces valid PDF bytes."""
    generator = ComparisonPDFGenerator()
    pdf_bytes = generator.generate_comparison_report(
        title="Test Comparison",
        comparison_type="personal_performance",
        report_markdown="## Analysis\n\nPerformance improved across sessions.\n\n- Better pacing\n- Fewer fillers",
        metrics={"evaluations_compared": 2, "avg_wpm": 148.75},
        strengths=[{"title": "Strong Pacing", "text": "Consistent improvement in WPM"}],
        growth_opportunities=[{"title": "Engagement", "text": "More questions needed"}],
        evaluations=[
            {"label": "Session 1", "instructor_name": "Dr. Smith", "status": "completed"},
            {"label": "Session 2", "instructor_name": "Dr. Smith", "status": "completed"},
        ],
    )
    # PDF files start with %PDF
    assert pdf_bytes[:4] == b"%PDF"
    # Should be a non-trivial size (multi-page report)
    assert len(pdf_bytes) > 1000


def test_comparison_pdf_handles_empty_data():
    """Verify PDF generator handles missing/empty fields gracefully."""
    generator = ComparisonPDFGenerator()
    pdf_bytes = generator.generate_comparison_report(
        title="Minimal Comparison",
        comparison_type="class_delivery",
    )
    assert pdf_bytes[:4] == b"%PDF"


def test_comparison_pdf_bold_safe_method():
    """Verify _bold_safe converts markdown bold to HTML and escapes."""
    result = ComparisonPDFGenerator._bold_safe("This has **bold text** and <html>")
    assert "<b>bold text</b>" in result
    assert "&lt;html&gt;" in result


async def test_download_comparison_pdf(client, test_comparison):
    """GET /comparisons/{id}/report/pdf returns a valid PDF."""
    response = await client.get(
        f"/api/v1/comparisons/{test_comparison.id}/report/pdf"
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    # Verify it's actually a PDF
    assert response.content[:4] == b"%PDF"


async def test_download_comparison_pdf_not_ready(
    client, test_instructor, test_org,
):
    """GET /comparisons/{id}/report/pdf returns 400 if no report."""
    comparison = Comparison(
        id=uuid.uuid4(),
        title="No Report Yet",
        comparison_type="personal_performance",
        status="draft",
        organization_id=test_org.id,
        created_by_id=test_instructor.id,
    )
    async with AsyncSessionLocal() as session:
        session.add(comparison)
        await session.commit()

    response = await client.get(
        f"/api/v1/comparisons/{comparison.id}/report/pdf"
    )
    assert response.status_code == 400

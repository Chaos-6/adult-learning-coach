"""
Comparison pipeline orchestrator.

This service runs the multi-video comparison analysis:
1. Load the comparison record and linked evaluations
2. Validate all evaluations are completed with reports
3. Send evaluation reports to Claude for comparison analysis
4. Save the comparison report and metrics

Status progression: queued → analyzing → completed/failed

Design: Mirrors the evaluation pipeline pattern (evaluation.py).
Runs as a background task with its own database session.
"""

import asyncio
import traceback
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import Comparison, ComparisonEvaluation, Evaluation, User, Video
from app.services.comparison_analysis import ComparisonAnalysisService


async def run_comparison_pipeline(comparison_id: UUID) -> None:
    """Run the comparison analysis pipeline.

    This is the main entry point, called from a background task.
    It manages its own database sessions (since it runs outside
    the request lifecycle).

    Args:
        comparison_id: UUID of the comparison to process.
    """
    async with AsyncSessionLocal() as db:
        try:
            # Load comparison record
            comp_result = await db.execute(
                select(Comparison).where(Comparison.id == comparison_id)
            )
            comparison = comp_result.scalar_one_or_none()
            if not comparison:
                print(f"❌ Comparison {comparison_id} not found")
                return

            # --- Load linked evaluations ---
            evaluations_data = await _load_evaluation_data(db, comparison)
            if not evaluations_data:
                return  # _load_evaluation_data handles failure

            # --- Run comparison analysis ---
            comparison.status = "analyzing"
            comparison.processing_started_at = datetime.now(timezone.utc)
            await db.commit()

            print(
                f"🔍 Starting {comparison.comparison_type} comparison analysis "
                f"with {len(evaluations_data)} evaluations..."
            )

            success = await _run_comparison_analysis(
                db, comparison, evaluations_data
            )
            if not success:
                return  # _run_comparison_analysis handles failure

            # --- Mark complete ---
            comparison.status = "completed"
            comparison.processing_completed_at = datetime.now(timezone.utc)
            await db.commit()

            print(f"🎉 Comparison {comparison_id} pipeline complete")

        except Exception as e:
            print(f"❌ Comparison pipeline error: {str(e)}")
            traceback.print_exc()
            try:
                await _fail_comparison(db, comparison, str(e))
            except Exception:
                pass  # Don't let error handling crash


async def _load_evaluation_data(
    db: AsyncSession,
    comparison: Comparison,
) -> list[dict] | None:
    """Load and validate all linked evaluations.

    Returns a list of dicts ready to pass to the analysis service,
    or None if validation fails.
    """
    try:
        # Get all linked evaluations ordered by display_order
        links_result = await db.execute(
            select(ComparisonEvaluation)
            .where(ComparisonEvaluation.comparison_id == comparison.id)
            .order_by(ComparisonEvaluation.display_order)
        )
        links = links_result.scalars().all()

        if len(links) < 2:
            await _fail_comparison(
                db, comparison,
                f"Comparison requires at least 2 evaluations, found {len(links)}"
            )
            return None

        evaluations_data = []
        for link in links:
            # Load the evaluation
            eval_result = await db.execute(
                select(Evaluation).where(Evaluation.id == link.evaluation_id)
            )
            evaluation = eval_result.scalar_one_or_none()

            if not evaluation:
                await _fail_comparison(
                    db, comparison,
                    f"Linked evaluation {link.evaluation_id} not found"
                )
                return None

            if evaluation.status != "completed":
                await _fail_comparison(
                    db, comparison,
                    f"Evaluation {link.evaluation_id} is not completed "
                    f"(status: {evaluation.status})"
                )
                return None

            if not evaluation.report_markdown:
                await _fail_comparison(
                    db, comparison,
                    f"Evaluation {link.evaluation_id} has no report"
                )
                return None

            # Look up instructor name
            instructor_name = "Unknown Instructor"
            if evaluation.instructor_id:
                user_result = await db.execute(
                    select(User).where(User.id == evaluation.instructor_id)
                )
                user = user_result.scalar_one_or_none()
                if user:
                    instructor_name = user.display_name
                    # Anonymize if requested
                    if comparison.anonymize_instructors:
                        instructor_name = f"Instructor {link.display_order + 1}"

            # Get video date for context
            session_date = "Not specified"
            if evaluation.video_id:
                video_result = await db.execute(
                    select(Video).where(Video.id == evaluation.video_id)
                )
                video = video_result.scalar_one_or_none()
                if video and video.uploaded_at:
                    session_date = video.uploaded_at.strftime("%Y-%m-%d")

            evaluations_data.append({
                "label": link.label or f"Session {link.display_order + 1}",
                "date": session_date,
                "instructor_name": instructor_name,
                "report_markdown": evaluation.report_markdown,
                "metrics": evaluation.metrics or {},
            })

        return evaluations_data

    except Exception as e:
        print(f"❌ Failed to load evaluation data: {str(e)}")
        traceback.print_exc()
        await _fail_comparison(
            db, comparison, f"Failed to load evaluations: {str(e)}"
        )
        return None


async def _run_comparison_analysis(
    db: AsyncSession,
    comparison: Comparison,
    evaluations_data: list[dict],
) -> bool:
    """Run the comparison analysis with Claude.

    Like the evaluation pipeline, the Anthropic SDK is synchronous,
    so we run it in a thread pool.

    Returns:
        True if successful, False if failed.
    """
    try:
        service = ComparisonAnalysisService()
        result = await asyncio.to_thread(
            service.analyze_comparison,
            evaluations_data,
            comparison.comparison_type,
            comparison.class_tag,
        )

        # Save analysis results
        comparison.report_markdown = result.report_markdown
        comparison.strengths = result.strengths
        comparison.growth_opportunities = result.growth_opportunities
        comparison.metrics = {
            **result.metrics,
            "analysis_input_tokens": result.input_tokens,
            "analysis_output_tokens": result.output_tokens,
            "analysis_processing_seconds": result.processing_time_seconds,
            "analysis_model": result.model,
        }

        await db.commit()
        return True

    except Exception as e:
        print(f"❌ Comparison analysis failed: {str(e)}")
        traceback.print_exc()
        await _fail_comparison(
            db, comparison, f"Analysis failed: {str(e)}"
        )
        return False


async def _fail_comparison(
    db: AsyncSession,
    comparison: Comparison,
    error_message: str,
) -> None:
    """Mark a comparison as failed with an error message."""
    comparison.status = "failed"
    comparison.processing_completed_at = datetime.now(timezone.utc)
    comparison.metrics = {"error": error_message}
    await db.commit()
    print(f"❌ Comparison {comparison.id} marked as failed: {error_message}")

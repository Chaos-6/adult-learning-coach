"""
CLI tool for exporting coaching reports as Google Docs.

Connects to the same database as the web app and uses Google's
OAuth2 flow to create formatted documents in your Google Drive.

Usage:
    python cli.py list                              # List evaluations
    python cli.py list --comparisons                # List comparisons
    python cli.py export <evaluation_id>            # Export coaching report
    python cli.py export <evaluation_id> --worksheet  # Export worksheet
    python cli.py export-comparison <comparison_id> # Export comparison

First run will open a browser for Google sign-in. Subsequent runs
use the cached token at ~/.alca/google_token.json.
"""

import argparse
import asyncio
import sys
from uuid import UUID

from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Comparison, ComparisonEvaluation, Evaluation, User
from app.services.google_auth import get_google_services
from app.services.google_docs_report import GoogleDocsReportGenerator


async def list_reports(show_comparisons: bool = False):
    """Print a table of available evaluations or comparisons."""
    async with AsyncSessionLocal() as db:
        if show_comparisons:
            result = await db.execute(
                select(Comparison)
                .where(Comparison.status == "completed")
                .order_by(Comparison.created_at.desc())
            )
            comparisons = result.scalars().all()

            if not comparisons:
                print("No completed comparisons found.")
                return

            print(f"\n{'ID':<38} {'Title':<35} {'Type':<25} {'Created'}")
            print("-" * 120)
            for c in comparisons:
                created = c.created_at.strftime("%Y-%m-%d") if c.created_at else "—"
                print(
                    f"{str(c.id):<38} "
                    f"{(c.title or '—')[:33]:<35} "
                    f"{(c.comparison_type or '—'):<25} "
                    f"{created}"
                )
            print(f"\n{len(comparisons)} comparison(s) available for export.\n")

        else:
            result = await db.execute(
                select(Evaluation, User)
                .join(User, Evaluation.instructor_id == User.id, isouter=True)
                .where(Evaluation.status == "completed")
                .order_by(Evaluation.created_at.desc())
            )
            rows = result.all()

            if not rows:
                print("No completed evaluations found.")
                return

            print(f"\n{'ID':<38} {'Instructor':<25} {'Status':<12} {'Created'}")
            print("-" * 100)
            for evaluation, user in rows:
                name = user.display_name if user else "Unknown"
                created = (
                    evaluation.created_at.strftime("%Y-%m-%d")
                    if evaluation.created_at
                    else "—"
                )
                print(
                    f"{str(evaluation.id):<38} "
                    f"{name[:23]:<25} "
                    f"{evaluation.status:<12} "
                    f"{created}"
                )
            print(f"\n{len(rows)} evaluation(s) available for export.\n")


async def export_evaluation(evaluation_id: str, worksheet: bool = False):
    """Export an evaluation as a Google Doc."""
    try:
        eval_uuid = UUID(evaluation_id)
    except ValueError:
        print(f"Error: Invalid UUID: {evaluation_id}", file=sys.stderr)
        sys.exit(1)

    async with AsyncSessionLocal() as db:
        # Fetch evaluation
        result = await db.execute(
            select(Evaluation).where(Evaluation.id == eval_uuid)
        )
        evaluation = result.scalar_one_or_none()

        if not evaluation:
            print(f"Error: Evaluation {evaluation_id} not found.", file=sys.stderr)
            sys.exit(1)
        if not evaluation.report_markdown:
            print(
                f"Error: Evaluation {evaluation_id} has no report yet "
                f"(status: {evaluation.status}).",
                file=sys.stderr,
            )
            sys.exit(1)

        # Get instructor name
        instructor_name = "Instructor"
        if evaluation.instructor_id:
            user_result = await db.execute(
                select(User).where(User.id == evaluation.instructor_id)
            )
            user = user_result.scalar_one_or_none()
            if user:
                instructor_name = user.display_name

    # Authenticate with Google (outside the DB session — this may open a browser)
    print("Authenticating with Google...")
    docs_service, drive_service = get_google_services(
        settings.GOOGLE_CLIENT_ID, settings.GOOGLE_CLIENT_SECRET
    )

    generator = GoogleDocsReportGenerator(docs_service, drive_service)

    if worksheet:
        print(f"Creating reflection worksheet for {instructor_name}...")
        url = generator.generate_reflection_worksheet(
            instructor_name=instructor_name,
            strengths=evaluation.strengths,
            growth_opportunities=evaluation.growth_opportunities,
            report_markdown=evaluation.report_markdown or "",
        )
        print(f"\nReflection worksheet created:\n  {url}\n")
    else:
        print(f"Creating coaching report for {instructor_name}...")
        url = generator.generate_coaching_report(
            report_markdown=evaluation.report_markdown,
            instructor_name=instructor_name,
            metrics=evaluation.metrics,
            strengths=evaluation.strengths,
            growth_opportunities=evaluation.growth_opportunities,
        )
        print(f"\nCoaching report created:\n  {url}\n")


async def export_comparison(comparison_id: str):
    """Export a comparison report as a Google Doc."""
    try:
        comp_uuid = UUID(comparison_id)
    except ValueError:
        print(f"Error: Invalid UUID: {comparison_id}", file=sys.stderr)
        sys.exit(1)

    async with AsyncSessionLocal() as db:
        # Fetch comparison
        result = await db.execute(
            select(Comparison).where(Comparison.id == comp_uuid)
        )
        comparison = result.scalar_one_or_none()

        if not comparison:
            print(f"Error: Comparison {comparison_id} not found.", file=sys.stderr)
            sys.exit(1)
        if not comparison.report_markdown:
            print(
                f"Error: Comparison {comparison_id} has no report yet "
                f"(status: {comparison.status}).",
                file=sys.stderr,
            )
            sys.exit(1)

        # Fetch linked evaluation summaries
        links_result = await db.execute(
            select(ComparisonEvaluation)
            .where(ComparisonEvaluation.comparison_id == comp_uuid)
            .order_by(ComparisonEvaluation.display_order)
        )
        links = links_result.scalars().all()

        eval_dicts = []
        for link in links:
            eval_result = await db.execute(
                select(Evaluation, User)
                .join(User, Evaluation.instructor_id == User.id, isouter=True)
                .where(Evaluation.id == link.evaluation_id)
            )
            row = eval_result.first()
            if row:
                ev, user = row
                eval_dicts.append({
                    "label": link.label or f"Session",
                    "instructor_name": user.display_name if user else "Unknown",
                    "status": ev.status,
                })

    # Authenticate with Google
    print("Authenticating with Google...")
    docs_service, drive_service = get_google_services(
        settings.GOOGLE_CLIENT_ID, settings.GOOGLE_CLIENT_SECRET
    )

    generator = GoogleDocsReportGenerator(docs_service, drive_service)

    print(f"Creating comparison report: {comparison.title}...")
    url = generator.generate_comparison_report(
        title=comparison.title,
        comparison_type=comparison.comparison_type,
        report_markdown=comparison.report_markdown,
        metrics=comparison.metrics,
        strengths=comparison.strengths,
        growth_opportunities=comparison.growth_opportunities,
        evaluations=eval_dicts,
    )
    print(f"\nComparison report created:\n  {url}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Export coaching reports as Google Docs",
        prog="alca",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list command
    list_parser = subparsers.add_parser("list", help="List available reports")
    list_parser.add_argument(
        "--comparisons",
        action="store_true",
        help="List comparisons instead of evaluations",
    )

    # export command
    export_parser = subparsers.add_parser(
        "export", help="Export evaluation as Google Doc"
    )
    export_parser.add_argument("id", help="Evaluation UUID")
    export_parser.add_argument(
        "--worksheet",
        action="store_true",
        help="Export reflection worksheet instead of full report",
    )

    # export-comparison command
    comp_parser = subparsers.add_parser(
        "export-comparison", help="Export comparison as Google Doc"
    )
    comp_parser.add_argument("id", help="Comparison UUID")

    args = parser.parse_args()

    if args.command == "list":
        asyncio.run(list_reports(show_comparisons=args.comparisons))
    elif args.command == "export":
        asyncio.run(export_evaluation(args.id, worksheet=args.worksheet))
    elif args.command == "export-comparison":
        asyncio.run(export_comparison(args.id))


if __name__ == "__main__":
    main()

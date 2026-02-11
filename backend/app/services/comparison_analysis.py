"""
Comparison analysis service — sends multiple evaluation reports to Claude
for cross-session analysis.

This mirrors the AnalysisService pattern but operates on evaluation REPORTS
instead of raw transcripts. This is a key design decision:

    10 transcripts ≈ 500K tokens (exceeds Claude's context window)
    10 reports     ≈  80K tokens (fits comfortably, costs ~$0.50)

The service:
1. Takes a list of evaluation data (report + metrics + metadata)
2. Selects the right prompt variant based on comparison type
3. Sends to Claude with the comparison system prompt
4. Returns structured results (same shape as single evaluations)

Three comparison types, each with a different analytical lens:
- personal_performance: Temporal tracking of one instructor
- class_delivery: Different instructors, same class
- program_evaluation: Sample from a training program
"""

import re
import time
from dataclasses import dataclass, field

import anthropic

from app.config import settings
from app.services.prompts import (
    COMPARISON_PROMPT_BUILDERS,
    COMPARISON_SYSTEM_PROMPT,
)


@dataclass
class ComparisonAnalysisResult:
    """Structured output from a comparison analysis.

    Same shape as AnalysisResult for consistency — the pipeline,
    router, and frontend all handle the same fields.
    """
    report_markdown: str
    metrics: dict = field(default_factory=dict)
    strengths: list = field(default_factory=list)
    growth_opportunities: list = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    processing_time_seconds: int = 0
    model: str = ""


class ComparisonAnalysisService:
    """Sends evaluation reports to Claude for cross-session analysis.

    Usage:
        service = ComparisonAnalysisService()
        result = service.analyze_comparison(
            evaluations_data=[
                {"label": "Session 1", "report_markdown": "...", "metrics": {...}},
                {"label": "Session 2", "report_markdown": "...", "metrics": {...}},
            ],
            comparison_type="personal_performance",
        )
        print(result.report_markdown)
    """

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = "claude-sonnet-4-20250514"

    def analyze_comparison(
        self,
        evaluations_data: list[dict],
        comparison_type: str,
        class_tag: str | None = None,
    ) -> ComparisonAnalysisResult:
        """Run a comparison analysis across multiple evaluation reports.

        This is a BLOCKING call. It will be run in a thread pool
        via asyncio.to_thread() (same pattern as AnalysisService).

        Args:
            evaluations_data: List of dicts with keys:
                - label: str (display label for the session)
                - date: str (session date, ISO format or human-readable)
                - instructor_name: str
                - report_markdown: str (individual coaching report)
                - metrics: dict (extracted metrics)
            comparison_type: One of 'personal_performance', 'class_delivery',
                'program_evaluation'.
            class_tag: Optional class name (used only for class_delivery).

        Returns:
            ComparisonAnalysisResult with the comparison report and extracted data.

        Raises:
            ValueError: If comparison_type is not recognized.
            anthropic.APIError: If the Claude API call fails.
        """
        start_time = time.time()

        # Select the right prompt builder
        builder = COMPARISON_PROMPT_BUILDERS.get(comparison_type)
        if not builder:
            raise ValueError(
                f"Unknown comparison type: {comparison_type}. "
                f"Expected one of: {list(COMPARISON_PROMPT_BUILDERS.keys())}"
            )

        # Build the prompt (class_delivery needs class_tag)
        if comparison_type == "class_delivery" and class_tag:
            user_prompt = builder(evaluations_data, class_tag=class_tag)
        else:
            user_prompt = builder(evaluations_data)

        # Call Claude — higher max_tokens since comparison reports are longer
        message = self.client.messages.create(
            model=self.model,
            max_tokens=12000,  # Comparison reports are longer than single evals
            temperature=0.3,
            system=COMPARISON_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_prompt}
            ],
        )

        processing_time = int(time.time() - start_time)

        report_markdown = message.content[0].text

        # Extract structured data from the comparison report
        metrics = self._extract_comparison_metrics(report_markdown, evaluations_data)
        strengths = self._extract_sections(report_markdown, "Cross-Session Strengths")
        if not strengths:
            # Program eval and class delivery use different section titles
            strengths = self._extract_sections(
                report_markdown, "Strengths Across the Program"
            )
            if not strengths:
                strengths = self._extract_sections(
                    report_markdown, "Best Practices to Share"
                )

        growth = self._extract_sections(
            report_markdown, "Cross-Session Growth Opportunities"
        )
        if not growth:
            growth = self._extract_sections(
                report_markdown, "Areas for Improvement"
            )
            if not growth:
                growth = self._extract_sections(
                    report_markdown, "Common Delivery Gaps"
                )

        return ComparisonAnalysisResult(
            report_markdown=report_markdown,
            metrics=metrics,
            strengths=strengths,
            growth_opportunities=growth,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            processing_time_seconds=processing_time,
            model=self.model,
        )

    def _extract_comparison_metrics(
        self, report: str, evaluations_data: list[dict]
    ) -> dict:
        """Extract aggregate metrics from the comparison report.

        Computes averages, ranges, and trends from the individual
        evaluation metrics that were passed in.
        """
        metrics = {
            "session_count": len(evaluations_data),
            "comparison_generated": True,
        }

        # Aggregate from individual evaluation metrics
        metric_keys = [
            "wpm", "pauses_per_10min", "filler_words_per_min",
            "questions_per_5min", "tangent_percentage",
        ]
        for key in metric_keys:
            values = [
                ev["metrics"][key]
                for ev in evaluations_data
                if ev.get("metrics") and key in ev["metrics"]
            ]
            if values:
                metrics[f"{key}_avg"] = round(sum(values) / len(values), 1)
                metrics[f"{key}_min"] = min(values)
                metrics[f"{key}_max"] = max(values)
                if len(values) >= 2:
                    # Simple trend: compare first half avg to second half avg
                    mid = len(values) // 2
                    first_half = sum(values[:mid]) / mid
                    second_half = sum(values[mid:]) / (len(values) - mid)
                    if second_half > first_half * 1.05:
                        metrics[f"{key}_trend"] = "increasing"
                    elif second_half < first_half * 0.95:
                        metrics[f"{key}_trend"] = "decreasing"
                    else:
                        metrics[f"{key}_trend"] = "stable"

        return metrics

    def _extract_sections(self, report: str, section_title: str) -> list[dict]:
        """Extract individual items from a report section.

        Same pattern as AnalysisService._extract_sections.
        """
        items = []

        section_pattern = rf'## {re.escape(section_title)}\s*\n(.*?)(?=\n## |\Z)'
        section_match = re.search(section_pattern, report, re.DOTALL)

        if not section_match:
            return items

        section_text = section_match.group(1)

        item_pattern = r'\*\*(.+?)\*\*\s*\n(.*?)(?=\n\s*(?:- )?\*\*|\Z)'
        for match in re.finditer(item_pattern, section_text, re.DOTALL):
            title = match.group(1).strip()
            body = match.group(2).strip()
            items.append({
                "title": title,
                "text": body[:500],
            })

        return items

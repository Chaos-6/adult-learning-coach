"""
Coaching analysis service — sends transcripts to Claude for evaluation.

This service:
1. Takes a transcript and instructor name
2. Builds the coaching prompt (from prompts.py)
3. Sends it to Claude 3.5 Sonnet via the Anthropic API
4. Parses the response into a structured report
5. Extracts metrics from the report for historical tracking

Key Anthropic API details:
- Model: claude-sonnet-4-20250514 (best balance of quality and cost)
- Temperature: 0.3 (low = more consistent/reproducible analysis)
- Max tokens: 8192 (enough for a comprehensive report)
- The transcript goes in the user message, coaching framework in system prompt

Cost per evaluation (from PRD):
- ~50K input tokens (transcript + prompt)
- ~8K output tokens (report)
- ≈ $0.38 per evaluation
"""

import json
import re
import time
from dataclasses import dataclass, field

import anthropic

from app.config import settings
from app.services.prompts import SYSTEM_PROMPT, build_analysis_prompt


@dataclass
class AnalysisResult:
    """Structured output from the coaching analysis."""
    report_markdown: str             # Full coaching report
    metrics: dict = field(default_factory=dict)  # Extracted metrics for tracking
    strengths: list = field(default_factory=list)
    growth_opportunities: list = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    processing_time_seconds: int = 0
    model: str = ""


class AnalysisService:
    """Sends transcripts to Claude for coaching analysis.

    Usage:
        service = AnalysisService()
        result = service.analyze(transcript_text, "Jane Smith")
        print(result.report_markdown)
    """

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        # claude-sonnet-4-20250514 is the PRD's recommended model
        # Good balance of quality, speed, and cost for coaching analysis
        self.model = "claude-sonnet-4-20250514"

    def analyze(self, transcript: str, instructor_name: str = "the instructor") -> AnalysisResult:
        """Analyze a transcript and generate a coaching report.

        This is a BLOCKING call (like transcription). It will be run
        in a thread pool via asyncio.to_thread().

        Args:
            transcript: Time-stamped transcript text.
            instructor_name: Instructor's name for personalized report.

        Returns:
            AnalysisResult with the full report and extracted data.
        """
        start_time = time.time()

        # Build the prompt
        user_prompt = build_analysis_prompt(transcript, instructor_name)

        # Call Claude
        message = self.client.messages.create(
            model=self.model,
            max_tokens=8192,
            temperature=0.3,      # Low temp = more consistent analysis
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_prompt}
            ],
        )

        processing_time = int(time.time() - start_time)

        # Extract the report text
        report_markdown = message.content[0].text

        # Parse metrics from the report
        metrics = self._extract_metrics(report_markdown)
        strengths = self._extract_sections(report_markdown, "Strengths to Build On")
        growth = self._extract_sections(report_markdown, "Growth Opportunities")

        return AnalysisResult(
            report_markdown=report_markdown,
            metrics=metrics,
            strengths=strengths,
            growth_opportunities=growth,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            processing_time_seconds=processing_time,
            model=self.model,
        )

    def _extract_metrics(self, report: str) -> dict:
        """Parse the Metrics Snapshot table from the report.

        Looks for the markdown table and extracts key-value pairs.
        This is best-effort — if Claude formats the table differently,
        we still have the full report as fallback.
        """
        metrics = {}

        # Try to extract WPM
        wpm_match = re.search(r'Speaking Pace.*?\|\s*(\d+(?:\.\d+)?)', report)
        if wpm_match:
            metrics["wpm"] = float(wpm_match.group(1))

        # Strategic pauses per 10 min
        pause_match = re.search(r'Strategic Pauses.*?\|\s*(\d+(?:\.\d+)?)', report)
        if pause_match:
            metrics["pauses_per_10min"] = float(pause_match.group(1))

        # Filler words per min
        filler_match = re.search(r'Filler Words.*?\|\s*(\d+(?:\.\d+)?)', report)
        if filler_match:
            metrics["filler_words_per_min"] = float(filler_match.group(1))

        # Questions per 5 min
        question_match = re.search(r'Questions.*?\|\s*(\d+(?:\.\d+)?)', report)
        if question_match:
            metrics["questions_per_5min"] = float(question_match.group(1))

        # Tangent time %
        tangent_match = re.search(r'Tangent.*?\|\s*(\d+(?:\.\d+)?)%?', report)
        if tangent_match:
            metrics["tangent_percentage"] = float(tangent_match.group(1))

        return metrics

    def _extract_sections(self, report: str, section_title: str) -> list[dict]:
        """Extract individual items from a report section.

        Looks for bold headings (**text**) under the given section
        and captures the content until the next heading.
        """
        items = []

        # Find the section
        section_pattern = rf'## {re.escape(section_title)}\s*\n(.*?)(?=\n## |\Z)'
        section_match = re.search(section_pattern, report, re.DOTALL)

        if not section_match:
            return items

        section_text = section_match.group(1)

        # Find individual items (bold headings)
        item_pattern = r'\*\*(.+?)\*\*\s*\n(.*?)(?=\n\s*(?:- )?\*\*|\Z)'
        for match in re.finditer(item_pattern, section_text, re.DOTALL):
            title = match.group(1).strip()
            body = match.group(2).strip()

            # Try to extract a timestamp
            timestamp_match = re.search(r'\[(\d{2}:\d{2}:\d{2})\]', body)
            timestamp = timestamp_match.group(1) if timestamp_match else None

            items.append({
                "title": title,
                "text": body[:500],  # Cap at 500 chars for DB storage
                "timestamp": timestamp,
            })

        return items

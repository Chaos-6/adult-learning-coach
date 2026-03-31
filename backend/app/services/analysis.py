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
        """Parse the Metrics Snapshot from the report.

        Supports both the new plain-text format ("Speaking Pace: 145 WPM")
        and the legacy markdown table format ("Speaking Pace | 145").
        This is best-effort — if Claude formats differently, we still
        have the full report as fallback.
        """
        metrics = {}

        # Plain-text format: "Speaking Pace: 145 WPM" or "Speaking Pace: 145.2 WPM"
        # Legacy markdown: "Speaking Pace | 145"
        wpm_match = re.search(
            r'Speaking Pace[:\s|]+(\d+(?:\.\d+)?)', report
        )
        if wpm_match:
            metrics["wpm"] = float(wpm_match.group(1))

        pause_match = re.search(
            r'Strategic Pauses[:\s|]+(\d+(?:\.\d+)?)', report
        )
        if pause_match:
            metrics["pauses_per_10min"] = float(pause_match.group(1))

        filler_match = re.search(
            r'Filler Words[:\s|]+(\d+(?:\.\d+)?)', report
        )
        if filler_match:
            metrics["filler_words_per_min"] = float(filler_match.group(1))

        question_match = re.search(
            r'Questions\s*(?:Asked)?[:\s|]+(\d+(?:\.\d+)?)', report
        )
        if question_match:
            metrics["questions_per_5min"] = float(question_match.group(1))

        tangent_match = re.search(
            r'Tangent\s*(?:Time)?[:\s|]+(\d+(?:\.\d+)?)%?', report
        )
        if tangent_match:
            metrics["tangent_percentage"] = float(tangent_match.group(1))

        return metrics

    def _extract_sections(self, report: str, section_title: str) -> list[dict]:
        """Extract individual items from a report section.

        Supports both the new plain-text format and the legacy markdown format.

        New format:
            STRENGTHS TO BUILD ON
            1. Title Here
            Why this is effective:
            paragraph...
            How to amplify:
            paragraph...

        Legacy format:
            ## Strengths to Build On
            - **Title Here**
              - bullet text...
        """
        items = []

        # Try new plain-text format first: "SECTION TITLE" in all caps on its own line
        # Map display titles to the ALL CAPS headers used in the new prompt format
        caps_title = section_title.upper()
        section_pattern = rf'^{re.escape(caps_title)}\s*\n(.*?)(?=\n[A-Z][A-Z ]{{5,}}\s*$|\Z)'
        section_match = re.search(section_pattern, report, re.DOTALL | re.MULTILINE)

        if not section_match:
            # Fallback: try legacy markdown format
            section_pattern = rf'##\s+{re.escape(section_title)}\s*\n(.*?)(?=\n##\s|\Z)'
            section_match = re.search(section_pattern, report, re.DOTALL)

        if not section_match:
            return items

        section_text = section_match.group(1)

        # Try new plain-text format: "1. Title\nWhy this is effective:\n..."
        numbered_pattern = r'(\d+)\.\s+(.+?)(?:\n)(?:Why this (?:is effective|matters):)(.*?)(?=\n\d+\.\s+|\Z)'
        numbered_matches = list(re.finditer(numbered_pattern, section_text, re.DOTALL))

        if numbered_matches:
            for match in numbered_matches:
                title = match.group(2).strip()
                body = match.group(3).strip()

                # Extract timestamp — supports MM:SS and HH:MM:SS, with or without brackets
                timestamp_match = re.search(
                    r'\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?', body
                )
                timestamp = timestamp_match.group(1) if timestamp_match else None

                items.append({
                    "title": title,
                    "text": body[:500],
                    "timestamp": timestamp,
                })
        else:
            # Fallback: legacy markdown bold heading format
            item_pattern = r'\*\*(.+?)\*\*\s*\n(.*?)(?=\n\s*(?:- )?\*\*|\Z)'
            for match in re.finditer(item_pattern, section_text, re.DOTALL):
                title = match.group(1).strip()
                body = match.group(2).strip()

                timestamp_match = re.search(r'\[(\d{2}:\d{2}:\d{2})\]', body)
                timestamp = timestamp_match.group(1) if timestamp_match else None

                items.append({
                    "title": title,
                    "text": body[:500],
                    "timestamp": timestamp,
                })

        return items

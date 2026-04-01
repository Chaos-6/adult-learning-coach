from __future__ import annotations

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
from typing import Optional

import anthropic

from app.config import settings
from app.services.prompts import SYSTEM_PROMPT, build_analysis_prompt


@dataclass
class AnalysisResult:
    """Structured output from the coaching analysis."""
    report_markdown: str             # Raw Claude response (JSON string)
    coaching_data: dict = field(default_factory=dict)  # Parsed JSON from Claude
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
        self.model = "claude-sonnet-4-5-20250929"

    def analyze(self, transcript: str, instructor_name: str = "the instructor", class_name: str | None = None) -> AnalysisResult:
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
        user_prompt = build_analysis_prompt(transcript, instructor_name, class_name)

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

        # Extract the raw response text
        raw_response = message.content[0].text

        # Parse the JSON response from Claude
        coaching_data = self._parse_json_response(raw_response)

        # Pull metrics and sections directly from the structured JSON.
        # The metrics dict may contain calculation and confidence fields
        # alongside the numeric values; extract only the numeric keys for
        # the DB metrics column (used for historical tracking/comparisons).
        raw_metrics = coaching_data.get("metrics", {})
        numeric_metric_keys = {
            "wpm", "pauses_per_10min", "filler_words_per_min",
            "questions_per_5min", "understanding_checks_per_hour",
            "tangent_percentage", "curse_of_knowledge_count",
        }
        metrics = {k: v for k, v in raw_metrics.items()
                   if k in numeric_metric_keys and v is not None}

        # Convert strengths to the legacy list-of-dicts format that the
        # legacy PDF path and worksheet expect, while preserving new fields
        # in coaching_data for the JSON-based rendering path.
        strengths = [
            {
                "title": s.get("title", ""),
                "text": f"{s.get('why_effective', '')} {s.get('how_to_amplify', '')}",
                "timestamp": s.get("timestamp"),
                "segment": s.get("segment"),
            }
            for s in coaching_data.get("strengths", [])
        ]
        growth = [
            {
                "title": g.get("title", ""),
                "text": f"{g.get('why_it_matters', '')} {g.get('specific_action', '')}",
                "timestamp": g.get("timestamp"),
                "segment": g.get("segment"),
            }
            for g in coaching_data.get("growth_opportunities", [])
        ]

        return AnalysisResult(
            report_markdown=raw_response,
            coaching_data=coaching_data,
            metrics=metrics,
            strengths=strengths,
            growth_opportunities=growth,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            processing_time_seconds=processing_time,
            model=self.model,
        )

    def _parse_json_response(self, raw_response: str) -> dict:
        """Parse Claude's JSON response, with a safe fallback if parsing fails.

        Claude should return pure JSON (per the prompt), but defensively we
        strip any accidental markdown code fences before parsing.
        If parsing still fails we return a minimal valid structure so the
        rest of the pipeline does not crash.
        """
        # Strip markdown code fences if Claude accidentally added them
        cleaned = raw_response.strip()
        # Remove opening fence: ```json or ```
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        # Remove closing fence
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Log the error and return a safe empty structure so the
            # pipeline does not crash on a malformed response.
            print(f"[AnalysisService] JSON parse error: {e}")
            print(f"[AnalysisService] First 500 chars of response: {raw_response[:500]}")
            return {
                "instructor_name": "Unknown",
                "session_date": "",
                "session_topic": "",
                "metrics": {},
                "strengths": [],
                "growth_opportunities": [],
                "top_5_improvements": [],
                "timestamped_moments": [],
                "coaching_reflections": {
                    "proud_moment_prompt": "What moment in this session are you most proud of? Why?",
                    "reteach_prompt": "If you could re-teach one segment, what would you change?",
                    "next_session_goal_prompt": "What is one goal you will set for your next session?",
                },
                "action_plan": {
                    "instructions": "Write 1-3 concrete actions you will take before your next session.",
                    "action_1_label": "Action 1:",
                    "action_2_label": "Action 2:",
                    "action_3_label": "Action 3:",
                },
            }

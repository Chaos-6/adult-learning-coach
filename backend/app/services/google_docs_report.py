"""
Google Docs report generator — converts markdown coaching reports
into formatted Google Docs using the Google Docs API.

Parallel to pdf_report.py but outputs to Google Docs instead of PDF.
Uses the Docs API batchUpdate to apply formatting (headings, bold,
italic, tables, colored text) that matches the PDF brand colors.

Google Docs API key concepts:
- Document content is a flat list of "structural elements" with integer indices
- batchUpdate takes an array of requests applied atomically
- Text is inserted first (insertText), then styled (updateTextStyle,
  updateParagraphStyle) using index ranges
- Tables require a two-pass approach: insert the table, re-read the doc
  to get cell indices, then populate cells in a second batchUpdate
"""

import re
from datetime import datetime
from typing import Optional

# Brand colors as Google Docs API RGB (0.0-1.0 floats)
# These match the hex values in pdf_report.py
BRAND_PRIMARY = {"red": 0.102, "green": 0.212, "blue": 0.365}      # #1a365d
BRAND_SECONDARY = {"red": 0.169, "green": 0.424, "blue": 0.690}    # #2b6cb0
BRAND_ACCENT = {"red": 0.220, "green": 0.631, "blue": 0.412}       # #38a169
BRAND_CAUTION = {"red": 0.839, "green": 0.620, "blue": 0.180}      # #d69e2e
BRAND_TEXT = {"red": 0.176, "green": 0.216, "blue": 0.282}          # #2d3748
BRAND_MUTED = {"red": 0.443, "green": 0.502, "blue": 0.588}        # #718096
BRAND_COMPARE = {"red": 0.502, "green": 0.353, "blue": 0.835}      # #805ad5

# Comparison type display names (mirrors comparison_pdf.py)
TYPE_LABELS = {
    "personal_performance": "Personal Performance Comparison",
    "class_delivery": "Class Delivery Comparison",
    "program_evaluation": "Program Evaluation",
}


class GoogleDocsReportGenerator:
    """Generates formatted Google Docs from coaching report data.

    Usage:
        generator = GoogleDocsReportGenerator(docs_service, drive_service)
        url = generator.generate_coaching_report(
            report_markdown="# Coaching Report...",
            instructor_name="Dr. Sarah Chen",
            metrics={...},
            strengths=[...],
            growth_opportunities=[...],
        )
        print(url)  # https://docs.google.com/document/d/.../edit
    """

    def __init__(self, docs_service, drive_service):
        self.docs = docs_service
        self.drive = drive_service

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def generate_coaching_report(
        self,
        report_markdown: str,
        instructor_name: str = "Instructor",
        metrics: Optional[dict] = None,
        strengths: Optional[list] = None,
        growth_opportunities: Optional[list] = None,
    ) -> str:
        """Generate the full coaching report as a Google Doc.

        Returns the URL of the created Google Doc.
        """
        title = f"Coaching Report - {instructor_name}"
        doc_id = self._create_doc(title)

        requests = []
        cursor = 1  # Google Docs content starts at index 1

        # Title block
        cursor = self._insert_heading(
            requests, cursor, "Coaching Report", 1, BRAND_PRIMARY
        )
        cursor = self._insert_styled_text(
            requests, cursor, instructor_name, BRAND_SECONDARY, bold=True
        )
        cursor = self._insert_styled_text(
            requests, cursor,
            f"Generated {datetime.now().strftime('%B %d, %Y')}",
            BRAND_MUTED,
        )
        cursor = self._insert_newline(requests, cursor)

        # Executive Summary
        summary = self._extract_section(report_markdown, "Executive Summary")
        if summary:
            cursor = self._insert_heading(
                requests, cursor, "Executive Summary", 2, BRAND_PRIMARY
            )
            cursor = self._insert_text(requests, cursor, summary)

        # Metrics Snapshot (handled separately — requires table)
        if metrics:
            # Flush current requests, then handle the table
            self._batch_update(doc_id, requests)
            requests.clear()
            cursor = self._insert_metrics_table(doc_id, cursor, metrics)

        # Strengths
        cursor = self._insert_heading(
            requests, cursor, "Strengths to Build On", 2, BRAND_PRIMARY
        )
        if strengths:
            for i, s in enumerate(strengths, 1):
                title_text = s.get("title", f"Strength {i}")
                text = s.get("text", "")
                timestamp = s.get("timestamp")
                label = f"{title_text}"
                if timestamp:
                    label += f"  [{timestamp}]"
                cursor = self._insert_styled_text(
                    requests, cursor, label, BRAND_ACCENT, bold=True
                )
                if text:
                    for line in text.split("\n"):
                        line = line.strip().lstrip("-•").strip()
                        if line:
                            cursor = self._insert_bullet(requests, cursor, line)
        else:
            section = self._extract_section(report_markdown, "Strengths to Build On")
            if section:
                cursor = self._render_markdown_body(requests, cursor, section)

        # Growth Opportunities
        cursor = self._insert_heading(
            requests, cursor, "Growth Opportunities", 2, BRAND_PRIMARY
        )
        if growth_opportunities:
            for i, g in enumerate(growth_opportunities, 1):
                title_text = g.get("title", f"Growth Area {i}")
                text = g.get("text", "")
                timestamp = g.get("timestamp")
                label = f"{title_text}"
                if timestamp:
                    label += f"  [{timestamp}]"
                cursor = self._insert_styled_text(
                    requests, cursor, label, BRAND_CAUTION, bold=True
                )
                if text:
                    for line in text.split("\n"):
                        line = line.strip().lstrip("-•").strip()
                        if line:
                            cursor = self._insert_bullet(requests, cursor, line)
        else:
            section = self._extract_section(report_markdown, "Growth Opportunities")
            if section:
                cursor = self._render_markdown_body(requests, cursor, section)

        # Prioritized Improvements
        section = self._extract_section(
            report_markdown, "Top 5 Prioritized Improvements"
        )
        if section:
            cursor = self._insert_heading(
                requests, cursor,
                "Top 5 Prioritized Improvements", 2, BRAND_PRIMARY,
            )
            cursor = self._render_markdown_body(requests, cursor, section)

        # Timestamped Moments
        section = self._extract_section(
            report_markdown, "Timestamped Moments to Review"
        )
        if section:
            cursor = self._insert_heading(
                requests, cursor,
                "Timestamped Moments to Review", 2, BRAND_PRIMARY,
            )
            cursor = self._render_markdown_body(requests, cursor, section)

        # Coaching Reflections
        reflections = self._extract_reflections(report_markdown)
        if reflections:
            cursor = self._insert_heading(
                requests, cursor, "Coaching Reflections", 2, BRAND_PRIMARY
            )
            for i, question in enumerate(reflections, 1):
                cursor = self._insert_text(requests, cursor, f"{i}. {question}")

        # Next Steps
        next_steps = self._extract_section(report_markdown, "Next Steps")
        if next_steps:
            cursor = self._insert_heading(
                requests, cursor, "Next Steps", 2, BRAND_PRIMARY
            )
            next_steps = re.sub(r'\n---.*', '', next_steps, flags=re.DOTALL)
            cursor = self._render_markdown_body(requests, cursor, next_steps)

        # Footer
        cursor = self._insert_newline(requests, cursor)
        cursor = self._insert_styled_text(
            requests, cursor,
            "Analysis generated by Adult Learning Coaching Agent  •  "
            "4-Dimension Instructional Coaching Model",
            BRAND_MUTED,
        )

        self._batch_update(doc_id, requests)
        return f"https://docs.google.com/document/d/{doc_id}/edit"

    def generate_reflection_worksheet(
        self,
        instructor_name: str = "Instructor",
        strengths: Optional[list] = None,
        growth_opportunities: Optional[list] = None,
        report_markdown: str = "",
    ) -> str:
        """Generate the reflection worksheet as a Google Doc.

        Returns the URL of the created Google Doc.
        """
        title = f"Reflection Worksheet - {instructor_name}"
        doc_id = self._create_doc(title)

        requests = []
        cursor = 1

        # Title
        cursor = self._insert_heading(
            requests, cursor, "Reflection Worksheet", 1, BRAND_PRIMARY
        )
        cursor = self._insert_styled_text(
            requests, cursor, instructor_name, BRAND_SECONDARY, bold=True
        )
        cursor = self._insert_styled_text(
            requests, cursor,
            f"Session reviewed: {datetime.now().strftime('%B %d, %Y')}",
            BRAND_MUTED,
        )
        cursor = self._insert_newline(requests, cursor)

        # Section 1: Your Strengths
        cursor = self._insert_heading(
            requests, cursor, "Your Strengths", 2, BRAND_PRIMARY
        )
        cursor = self._insert_styled_text(
            requests, cursor,
            "These are the things you're doing well. Reflect on how you "
            "can continue to build on these strengths.",
            BRAND_MUTED, italic=True,
        )
        for i, s in enumerate(strengths or [], 1):
            title_text = s.get("title", f"Strength {i}")
            cursor = self._insert_styled_text(
                requests, cursor, f"{i}. {title_text}", BRAND_ACCENT, bold=True
            )
            # Blank lines for handwritten notes
            cursor = self._insert_text(requests, cursor, "")
            cursor = self._insert_text(requests, cursor, "")

        # Section 2: Growth Opportunities
        cursor = self._insert_heading(
            requests, cursor, "Growth Opportunities", 2, BRAND_PRIMARY
        )
        cursor = self._insert_styled_text(
            requests, cursor,
            "These are areas where small changes can make a big impact. "
            "For each one, write down one specific thing you'll try in "
            "your next session.",
            BRAND_MUTED, italic=True,
        )
        for i, g in enumerate(growth_opportunities or [], 1):
            title_text = g.get("title", f"Growth Area {i}")
            cursor = self._insert_styled_text(
                requests, cursor, f"{i}. {title_text}", BRAND_CAUTION, bold=True
            )
            cursor = self._insert_text(requests, cursor, "What I'll try next time:")
            cursor = self._insert_text(requests, cursor, "")
            cursor = self._insert_text(requests, cursor, "")

        # Section 3: Coaching Reflections
        cursor = self._insert_heading(
            requests, cursor, "Coaching Reflections", 2, BRAND_PRIMARY
        )
        reflections = self._extract_reflections(report_markdown)
        if not reflections:
            reflections = [
                "What moment in this session are you most proud of? Why?",
                "If you could re-teach one segment, what would you change?",
                "What is one goal you'll set for your next session?",
            ]
        for i, question in enumerate(reflections, 1):
            cursor = self._insert_text(
                requests, cursor, f"Question {i}: {question}"
            )
            cursor = self._insert_text(requests, cursor, "")
            cursor = self._insert_text(requests, cursor, "")
            cursor = self._insert_text(requests, cursor, "")

        # Section 4: My Action Plan
        cursor = self._insert_heading(
            requests, cursor, "My Action Plan", 2, BRAND_PRIMARY
        )
        cursor = self._insert_styled_text(
            requests, cursor,
            "Write 1-3 concrete actions you'll take before your next session.",
            BRAND_MUTED, italic=True,
        )
        for i in range(1, 4):
            cursor = self._insert_text(requests, cursor, f"Action {i}:")
            cursor = self._insert_text(requests, cursor, "")
            cursor = self._insert_text(requests, cursor, "")

        # Footer
        cursor = self._insert_newline(requests, cursor)
        cursor = self._insert_styled_text(
            requests, cursor,
            "Adult Learning Coaching Agent  •  Reflection Worksheet",
            BRAND_MUTED,
        )

        self._batch_update(doc_id, requests)
        return f"https://docs.google.com/document/d/{doc_id}/edit"

    def generate_comparison_report(
        self,
        title: str,
        comparison_type: str,
        report_markdown: str = "",
        metrics: Optional[dict] = None,
        strengths: Optional[list] = None,
        growth_opportunities: Optional[list] = None,
        evaluations: Optional[list] = None,
    ) -> str:
        """Generate a comparison report as a Google Doc.

        Returns the URL of the created Google Doc.
        """
        doc_title = f"Comparison Report - {title}"
        doc_id = self._create_doc(doc_title)

        requests = []
        cursor = 1

        # Title block
        cursor = self._insert_heading(
            requests, cursor, "Comparison Report", 1, BRAND_PRIMARY
        )
        cursor = self._insert_styled_text(
            requests, cursor, title, BRAND_SECONDARY, bold=True
        )
        type_label = TYPE_LABELS.get(comparison_type, comparison_type)
        cursor = self._insert_styled_text(
            requests, cursor,
            f"{type_label}  •  {len(evaluations or [])} evaluations compared"
            f"  •  Generated {datetime.now().strftime('%B %d, %Y')}",
            BRAND_MUTED,
        )
        cursor = self._insert_newline(requests, cursor)

        # Evaluations overview (as formatted text since tables need special handling)
        if evaluations:
            cursor = self._insert_heading(
                requests, cursor, "Evaluations Compared", 2, BRAND_COMPARE
            )
            for i, ev in enumerate(evaluations, 1):
                label = ev.get("label", f"Session {i}")
                instructor = ev.get("instructor_name", "Unknown")
                status = ev.get("status", "—")
                cursor = self._insert_text(
                    requests, cursor,
                    f"{i}. {label} — {instructor} ({status})",
                )

        # Comparison metrics summary
        if metrics:
            cursor = self._insert_heading(
                requests, cursor, "Comparison Metrics", 2, BRAND_PRIMARY
            )
            metric_keys = [
                ("evaluations_compared", "Evaluations Compared"),
                ("avg_wpm", "Average Speaking Pace (WPM)"),
                ("avg_pauses_per_10min", "Average Pauses per 10 min"),
                ("avg_filler_words_per_min", "Average Filler Words per min"),
                ("avg_questions_per_5min", "Average Questions per 5 min"),
                ("avg_tangent_percentage", "Average Tangent Time (%)"),
            ]
            for key, label in metric_keys:
                if key in metrics:
                    value = metrics[key]
                    display = (
                        f"{value:.1f}" if isinstance(value, float) else str(value)
                    )
                    cursor = self._insert_text(
                        requests, cursor, f"{label}: {display}"
                    )
            if "wpm_trend" in metrics:
                trend = metrics["wpm_trend"].replace("_", " ").title()
                cursor = self._insert_text(
                    requests, cursor, f"Speaking Pace Trend: {trend}"
                )

        # Strengths
        if strengths:
            cursor = self._insert_heading(
                requests, cursor, "Cross-Session Strengths", 2, BRAND_PRIMARY
            )
            cursor = self._insert_styled_text(
                requests, cursor,
                "Patterns of excellence that appear consistently across sessions.",
                BRAND_MUTED, italic=True,
            )
            for i, s in enumerate(strengths, 1):
                title_text = s.get("title", f"Strength {i}")
                text = s.get("text") or s.get("description", "")
                cursor = self._insert_styled_text(
                    requests, cursor, title_text, BRAND_ACCENT, bold=True
                )
                if text:
                    for line in text.split("\n"):
                        line = line.strip().lstrip("-•").strip()
                        if line:
                            cursor = self._insert_bullet(requests, cursor, line)

        # Growth opportunities
        if growth_opportunities:
            cursor = self._insert_heading(
                requests, cursor, "Growth Opportunities", 2, BRAND_PRIMARY
            )
            cursor = self._insert_styled_text(
                requests, cursor,
                "Areas where targeted improvement would have the highest impact.",
                BRAND_MUTED, italic=True,
            )
            for i, g in enumerate(growth_opportunities, 1):
                title_text = g.get("title", f"Growth Area {i}")
                text = g.get("text") or g.get("description", "")
                cursor = self._insert_styled_text(
                    requests, cursor, title_text, BRAND_CAUTION, bold=True
                )
                if text:
                    for line in text.split("\n"):
                        line = line.strip().lstrip("-•").strip()
                        if line:
                            cursor = self._insert_bullet(requests, cursor, line)

        # Full report analysis
        if report_markdown:
            cursor = self._insert_heading(
                requests, cursor, "Full Comparison Analysis", 2, BRAND_PRIMARY
            )
            cursor = self._render_markdown_body(requests, cursor, report_markdown)

        # Footer
        cursor = self._insert_newline(requests, cursor)
        cursor = self._insert_styled_text(
            requests, cursor,
            "Analysis generated by Adult Learning Coaching Agent  •  "
            "Multi-Video Comparison",
            BRAND_MUTED,
        )

        self._batch_update(doc_id, requests)
        return f"https://docs.google.com/document/d/{doc_id}/edit"

    # ------------------------------------------------------------------
    # TEXT INSERTION HELPERS
    # ------------------------------------------------------------------

    def _insert_heading(
        self, requests: list, cursor: int, text: str, level: int, color: dict,
    ) -> int:
        """Insert a heading and return the new cursor position."""
        text_nl = text + "\n"
        end = cursor + len(text_nl)

        requests.append({
            "insertText": {"location": {"index": cursor}, "text": text_nl}
        })
        requests.append({
            "updateParagraphStyle": {
                "range": {"startIndex": cursor, "endIndex": end},
                "paragraphStyle": {"namedStyleType": f"HEADING_{level}"},
                "fields": "namedStyleType",
            }
        })
        requests.append({
            "updateTextStyle": {
                "range": {"startIndex": cursor, "endIndex": end - 1},
                "textStyle": {
                    "foregroundColor": {"color": {"rgbColor": color}},
                },
                "fields": "foregroundColor",
            }
        })

        return end

    def _insert_text(self, requests: list, cursor: int, text: str) -> int:
        """Insert a plain text paragraph and return the new cursor."""
        text_nl = text + "\n"
        end = cursor + len(text_nl)

        requests.append({
            "insertText": {"location": {"index": cursor}, "text": text_nl}
        })

        return end

    def _insert_styled_text(
        self,
        requests: list,
        cursor: int,
        text: str,
        color: dict,
        bold: bool = False,
        italic: bool = False,
    ) -> int:
        """Insert styled text (color, bold, italic) and return new cursor."""
        text_nl = text + "\n"
        end = cursor + len(text_nl)

        requests.append({
            "insertText": {"location": {"index": cursor}, "text": text_nl}
        })

        style = {"foregroundColor": {"color": {"rgbColor": color}}}
        fields = ["foregroundColor"]
        if bold:
            style["bold"] = True
            fields.append("bold")
        if italic:
            style["italic"] = True
            fields.append("italic")

        requests.append({
            "updateTextStyle": {
                "range": {"startIndex": cursor, "endIndex": end - 1},
                "textStyle": style,
                "fields": ",".join(fields),
            }
        })

        return end

    def _insert_bullet(self, requests: list, cursor: int, text: str) -> int:
        """Insert a bullet point line. Uses a unicode bullet prefix.

        Google Docs API bullet lists require creating a named list
        and assigning paragraphs to it, which is complex. A simpler
        approach for our use case: prefix with a bullet character
        and indent.
        """
        bullet_text = f"  •  {text}\n"
        end = cursor + len(bullet_text)

        requests.append({
            "insertText": {"location": {"index": cursor}, "text": bullet_text}
        })

        return end

    def _insert_newline(self, requests: list, cursor: int) -> int:
        """Insert a blank line separator."""
        requests.append({
            "insertText": {"location": {"index": cursor}, "text": "\n"}
        })
        return cursor + 1

    # ------------------------------------------------------------------
    # METRICS TABLE
    # ------------------------------------------------------------------

    def _insert_metrics_table(
        self, doc_id: str, cursor: int, metrics: dict,
    ) -> int:
        """Insert a metrics table into the document.

        Tables in the Google Docs API require a multi-step approach:
        1. Insert a heading + the table structure
        2. Read back the doc to get exact cell indices
        3. Populate cells in a second batchUpdate

        Returns the cursor position after the table.
        """
        # Metric definitions (mirrors pdf_report.py)
        metric_rows = [
            ("Speaking Pace", "wpm", "WPM", "120-160", 120, 160),
            ("Strategic Pauses", "pauses_per_10min", "per 10 min", "4-6", 4, 6),
            ("Filler Words", "filler_words_per_min", "per min", "<3", None, 3),
            ("Questions Asked", "questions_per_5min", "per 5 min", ">1", 1, None),
            ("Tangent Time", "tangent_percentage", "%", "<10%", None, 10),
        ]

        # Filter to metrics we actually have data for
        rows_with_data = []
        for label, key, unit, target, low, high in metric_rows:
            value = metrics.get(key)
            if value is not None:
                display = (
                    f"{value:.1f} {unit}"
                    if isinstance(value, float)
                    else f"{value} {unit}"
                )
                status = self._get_status_text(value, low, high)
                rows_with_data.append((label, display, target, status))

        if not rows_with_data:
            return cursor

        num_rows = len(rows_with_data) + 1  # +1 for header
        num_cols = 4

        # Step 1: Insert the heading text and table structure
        heading_text = "Metrics Snapshot\n"
        heading_end = cursor + len(heading_text)

        setup_requests = [
            {"insertText": {"location": {"index": cursor}, "text": heading_text}},
            {
                "updateParagraphStyle": {
                    "range": {"startIndex": cursor, "endIndex": heading_end},
                    "paragraphStyle": {"namedStyleType": "HEADING_2"},
                    "fields": "namedStyleType",
                }
            },
            {
                "updateTextStyle": {
                    "range": {"startIndex": cursor, "endIndex": heading_end - 1},
                    "textStyle": {
                        "foregroundColor": {"color": {"rgbColor": BRAND_PRIMARY}},
                    },
                    "fields": "foregroundColor",
                }
            },
            {
                "insertTable": {
                    "location": {"index": heading_end},
                    "rows": num_rows,
                    "columns": num_cols,
                }
            },
        ]
        self._batch_update(doc_id, setup_requests)

        # Step 2: Read the doc to find cell indices
        doc = self.docs.documents().get(documentId=doc_id).execute()
        table_element = None
        for element in doc["body"]["content"]:
            if "table" in element:
                table_element = element["table"]

        if not table_element:
            return heading_end + 1

        # Step 3: Populate cells (work backwards to avoid index shifting)
        cell_requests = []
        all_cells = []  # (row, col, text)

        # Header row
        headers = ["Metric", "Value", "Target", "Status"]
        for col, header in enumerate(headers):
            all_cells.append((0, col, header))

        # Data rows
        for row_idx, (label, display, target, status) in enumerate(rows_with_data):
            all_cells.append((row_idx + 1, 0, label))
            all_cells.append((row_idx + 1, 1, display))
            all_cells.append((row_idx + 1, 2, target))
            all_cells.append((row_idx + 1, 3, status))

        # Build requests in reverse order (last cell first) to avoid
        # index shifting when inserting text
        for row, col, text in reversed(all_cells):
            cell = table_element["tableRows"][row]["tableCells"][col]
            cell_start = cell["content"][0]["startIndex"]
            cell_requests.append({
                "insertText": {
                    "location": {"index": cell_start},
                    "text": text,
                }
            })

        # Bold the header row
        header_row = table_element["tableRows"][0]
        h_start = header_row["tableCells"][0]["content"][0]["startIndex"]
        h_end = header_row["tableCells"][-1]["content"][-1]["endIndex"]
        cell_requests.append({
            "updateTextStyle": {
                "range": {"startIndex": h_start, "endIndex": h_end},
                "textStyle": {
                    "bold": True,
                    "foregroundColor": {"color": {"rgbColor": BRAND_PRIMARY}},
                },
                "fields": "bold,foregroundColor",
            }
        })

        if cell_requests:
            self._batch_update(doc_id, cell_requests)

        # Find the end of the table for cursor positioning
        last_row = table_element["tableRows"][-1]
        last_cell = last_row["tableCells"][-1]
        table_end = last_cell["content"][-1]["endIndex"]
        # Account for text we just inserted (approximate)
        # Re-read document to get accurate position
        doc = self.docs.documents().get(documentId=doc_id).execute()
        body_end = doc["body"]["content"][-1]["endIndex"]

        return body_end - 1

    # ------------------------------------------------------------------
    # MARKDOWN RENDERING
    # ------------------------------------------------------------------

    def _render_markdown_body(
        self, requests: list, cursor: int, markdown: str,
    ) -> int:
        """Render a markdown section as formatted Google Doc content.

        Handles: headings (##, ###), bullets (-, *), numbered lists,
        bold (**text**), italic (*text*), and horizontal rules (---).
        """
        for line in markdown.split("\n"):
            trimmed = line.strip()

            if not trimmed:
                continue
            elif trimmed.startswith("# ") and not trimmed.startswith("## "):
                # Top-level heading — skip (covered by section headers)
                continue
            elif trimmed.startswith("## "):
                cursor = self._insert_heading(
                    requests, cursor, trimmed[3:], 2, BRAND_PRIMARY
                )
            elif trimmed.startswith("### "):
                cursor = self._insert_heading(
                    requests, cursor, trimmed[4:], 3, BRAND_SECONDARY
                )
            elif trimmed.startswith("---"):
                cursor = self._insert_newline(requests, cursor)
            elif trimmed.startswith("- ") or trimmed.startswith("* "):
                content = trimmed[2:]
                # Handle bold within bullets
                content = self._strip_markdown_bold(content)
                cursor = self._insert_bullet(requests, cursor, content)
            elif re.match(r'^\d+\.\s', trimmed):
                content = self._strip_markdown_bold(trimmed)
                cursor = self._insert_text(requests, cursor, content)
            elif (trimmed.startswith("*") and trimmed.endswith("*")
                  and not trimmed.startswith("**")):
                # Full italic line
                cursor = self._insert_styled_text(
                    requests, cursor, trimmed.strip("*"), BRAND_MUTED, italic=True
                )
            else:
                content = self._strip_markdown_bold(trimmed)
                cursor = self._insert_text(requests, cursor, content)

        return cursor

    # ------------------------------------------------------------------
    # SECTION PARSING (mirrors pdf_report.py helpers)
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_section(markdown: str, heading: str) -> str:
        """Extract text between a ## heading and the next ## heading."""
        pattern = rf'##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)'
        match = re.search(pattern, markdown, re.DOTALL)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _extract_reflections(markdown: str) -> list[str]:
        """Extract reflection questions from the Coaching Reflections section."""
        pattern = r'##\s+Coaching Reflections\s*\n(.*?)(?=\n##\s|\Z)'
        match = re.search(pattern, markdown, re.DOTALL)
        if not match:
            return []

        section = match.group(1).strip()
        questions = re.findall(
            r'\d+\.\s+\*\*.*?\*\*:?\s*(.*?)(?=\n\d+\.|\Z)',
            section, re.DOTALL,
        )
        return [q.strip() for q in questions if q.strip()]

    # ------------------------------------------------------------------
    # UTILITY HELPERS
    # ------------------------------------------------------------------

    def _create_doc(self, title: str) -> str:
        """Create a new Google Doc and return its document ID."""
        doc = self.docs.documents().create(body={"title": title}).execute()
        return doc["documentId"]

    def _batch_update(self, doc_id: str, requests: list):
        """Execute a batch of requests against the document."""
        if requests:
            self.docs.documents().batchUpdate(
                documentId=doc_id, body={"requests": requests}
            ).execute()

    @staticmethod
    def _strip_markdown_bold(text: str) -> str:
        """Remove markdown **bold** markers from text.

        Google Docs API applies bold via updateTextStyle, not inline
        markers. For simplicity, we strip the markers and render as
        plain text. A future enhancement could track bold ranges
        and apply them via the API.
        """
        return re.sub(r'\*\*(.+?)\*\*', r'\1', text)

    @staticmethod
    def _get_status_text(
        value: float, low: Optional[float], high: Optional[float],
    ) -> str:
        """Return a status indicator based on value vs targets.

        Same logic as PDFReportGenerator._get_status_text.
        """
        if low is not None and high is not None:
            if low <= value <= high:
                return "On Target"
            elif abs(value - low) <= low * 0.1 or abs(value - high) <= high * 0.1:
                return "Near Target"
            else:
                return "Needs Focus"
        elif high is not None:
            if value <= high:
                return "On Target"
            elif value <= high * 1.5:
                return "Near Target"
            else:
                return "Needs Focus"
        elif low is not None:
            if value >= low:
                return "On Target"
            elif value >= low * 0.5:
                return "Near Target"
            else:
                return "Needs Focus"
        return "—"

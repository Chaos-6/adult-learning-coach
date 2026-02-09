"""
PDF report generator — converts markdown coaching reports into professional PDFs.

This service produces two PDF documents:
1. Full Coaching Report: The complete analysis with metrics, strengths,
   growth areas, and timestamped review moments.
2. Reflection Worksheet: A condensed, fillable document that instructors
   use to plan their improvement actions.

Uses ReportLab's Platypus (Page Layout and Typography Using Scripts) engine.
Platypus is a high-level layout system where you build a list of "flowables"
(paragraphs, tables, spacers, etc.) and ReportLab handles pagination,
line breaks, and page flow automatically.

Key ReportLab concepts:
- SimpleDocTemplate: Manages pages, margins, and the overall document
- Paragraph: A styled block of text (supports HTML-like markup)
- Table: A grid of cells with configurable borders and colors
- Spacer: Vertical whitespace between elements
- ParagraphStyle: Reusable text formatting (font, size, color, spacing)
- PageBreak: Forces content to the next page
"""

import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    HRFlowable,
    KeepTogether,
)


# --- Brand Colors ---
# Consistent palette across all reports. Easy to swap for white-labeling.
BRAND_PRIMARY = colors.HexColor("#1a365d")     # Deep navy — headings
BRAND_SECONDARY = colors.HexColor("#2b6cb0")   # Medium blue — subheadings
BRAND_ACCENT = colors.HexColor("#38a169")       # Green — strengths/positive
BRAND_CAUTION = colors.HexColor("#d69e2e")      # Amber — growth areas
BRAND_DANGER = colors.HexColor("#e53e3e")       # Red — metrics below target
BRAND_LIGHT_BG = colors.HexColor("#f7fafc")     # Light gray — table backgrounds
BRAND_TEXT = colors.HexColor("#2d3748")          # Dark gray — body text
BRAND_MUTED = colors.HexColor("#718096")         # Medium gray — captions


def _build_styles() -> dict:
    """Create all paragraph styles used in the coaching report.

    Returns a dict of style_name → ParagraphStyle. Centralizing styles
    here keeps the report builder clean and makes restyling easy.
    """
    base = getSampleStyleSheet()

    styles = {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontSize=24,
            textColor=BRAND_PRIMARY,
            spaceAfter=6,
            alignment=TA_LEFT,
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=base["Normal"],
            fontSize=12,
            textColor=BRAND_MUTED,
            spaceAfter=20,
        ),
        "h2": ParagraphStyle(
            "Heading2",
            parent=base["Heading2"],
            fontSize=16,
            textColor=BRAND_PRIMARY,
            spaceBefore=16,
            spaceAfter=8,
            borderPadding=(0, 0, 4, 0),
        ),
        "h3": ParagraphStyle(
            "Heading3",
            parent=base["Heading3"],
            fontSize=13,
            textColor=BRAND_SECONDARY,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "BodyText",
            parent=base["Normal"],
            fontSize=10,
            textColor=BRAND_TEXT,
            leading=14,
            spaceAfter=6,
        ),
        "body_italic": ParagraphStyle(
            "BodyItalic",
            parent=base["Normal"],
            fontSize=10,
            textColor=BRAND_MUTED,
            leading=14,
            spaceAfter=6,
            fontName="Helvetica-Oblique",
        ),
        "bullet": ParagraphStyle(
            "BulletPoint",
            parent=base["Normal"],
            fontSize=10,
            textColor=BRAND_TEXT,
            leading=14,
            leftIndent=20,
            spaceAfter=4,
            bulletIndent=8,
        ),
        "sub_bullet": ParagraphStyle(
            "SubBulletPoint",
            parent=base["Normal"],
            fontSize=9,
            textColor=BRAND_TEXT,
            leading=13,
            leftIndent=36,
            spaceAfter=3,
            bulletIndent=24,
        ),
        "strength_title": ParagraphStyle(
            "StrengthTitle",
            parent=base["Normal"],
            fontSize=11,
            textColor=BRAND_ACCENT,
            fontName="Helvetica-Bold",
            spaceBefore=8,
            spaceAfter=4,
        ),
        "growth_title": ParagraphStyle(
            "GrowthTitle",
            parent=base["Normal"],
            fontSize=11,
            textColor=BRAND_CAUTION,
            fontName="Helvetica-Bold",
            spaceBefore=8,
            spaceAfter=4,
        ),
        "metric_label": ParagraphStyle(
            "MetricLabel",
            parent=base["Normal"],
            fontSize=9,
            textColor=BRAND_TEXT,
            alignment=TA_LEFT,
        ),
        "metric_value": ParagraphStyle(
            "MetricValue",
            parent=base["Normal"],
            fontSize=9,
            textColor=BRAND_TEXT,
            alignment=TA_CENTER,
        ),
        "footer": ParagraphStyle(
            "Footer",
            parent=base["Normal"],
            fontSize=8,
            textColor=BRAND_MUTED,
            alignment=TA_CENTER,
        ),
        "number_circle": ParagraphStyle(
            "NumberCircle",
            parent=base["Normal"],
            fontSize=11,
            textColor=colors.white,
            fontName="Helvetica-Bold",
            alignment=TA_CENTER,
        ),
    }

    return styles


class PDFReportGenerator:
    """Generates professional PDF coaching reports from markdown analysis.

    Usage:
        generator = PDFReportGenerator()

        # Full coaching report
        pdf_bytes = generator.generate_coaching_report(
            report_markdown="# Coaching Report...",
            instructor_name="Dr. Sarah Chen",
            metrics={"wpm": 145, ...},
            strengths=[{"title": "...", "text": "..."}],
            growth_opportunities=[{"title": "...", "text": "..."}],
        )

        # Reflection worksheet
        worksheet_bytes = generator.generate_reflection_worksheet(
            instructor_name="Dr. Sarah Chen",
            strengths=[...],
            growth_opportunities=[...],
            reflections=["question 1", "question 2", "question 3"],
        )
    """

    def __init__(self):
        self.styles = _build_styles()

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
    ) -> bytes:
        """Generate the full coaching report PDF.

        Parses the markdown report and renders each section into
        styled PDF elements. Returns raw PDF bytes (ready to save
        to disk or stream via HTTP).
        """
        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
            title=f"Coaching Report - {instructor_name}",
            author="Adult Learning Coaching Agent",
        )

        # Build the document as a list of "flowables" — ReportLab renders
        # them in order, automatically handling page breaks.
        story = []

        # --- Title Page Content ---
        story.append(Spacer(1, 0.5 * inch))
        story.append(Paragraph(f"Coaching Report", self.styles["title"]))
        story.append(Paragraph(instructor_name, self.styles["h2"]))
        story.append(Paragraph(
            f"Generated {datetime.now().strftime('%B %d, %Y')}",
            self.styles["subtitle"],
        ))
        story.append(HRFlowable(
            width="100%", thickness=2, color=BRAND_PRIMARY,
            spaceAfter=12, spaceBefore=4,
        ))

        # --- Parse and render each section ---
        self._render_executive_summary(story, report_markdown)
        self._render_metrics_table(story, metrics or {})
        story.append(PageBreak())
        self._render_strengths(story, report_markdown, strengths or [])
        self._render_growth_opportunities(story, report_markdown, growth_opportunities or [])
        story.append(PageBreak())
        self._render_prioritized_improvements(story, report_markdown)
        self._render_timestamped_moments(story, report_markdown)
        story.append(PageBreak())
        self._render_reflections_and_next_steps(story, report_markdown)

        # --- Footer ---
        story.append(Spacer(1, 0.3 * inch))
        story.append(HRFlowable(
            width="100%", thickness=1, color=BRAND_MUTED,
            spaceAfter=8, spaceBefore=8,
        ))
        story.append(Paragraph(
            "Analysis generated by Adult Learning Coaching Agent  •  "
            "4-Dimension Instructional Coaching Model",
            self.styles["footer"],
        ))

        # Build PDF with custom page numbering
        doc.build(story, onFirstPage=self._add_page_number,
                  onLaterPages=self._add_page_number)

        return buffer.getvalue()

    def generate_reflection_worksheet(
        self,
        instructor_name: str = "Instructor",
        strengths: Optional[list] = None,
        growth_opportunities: Optional[list] = None,
        report_markdown: str = "",
    ) -> bytes:
        """Generate the reflection worksheet PDF.

        This is a shorter, action-oriented document that instructors
        use for self-reflection and planning. It includes:
        - Key strengths to maintain
        - Growth areas with action prompts
        - Reflective questions
        - Blank space for written responses
        """
        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
            title=f"Reflection Worksheet - {instructor_name}",
            author="Adult Learning Coaching Agent",
        )

        story = []

        # --- Title ---
        story.append(Paragraph("Reflection Worksheet", self.styles["title"]))
        story.append(Paragraph(instructor_name, self.styles["h2"]))
        story.append(Paragraph(
            f"Session reviewed: {datetime.now().strftime('%B %d, %Y')}",
            self.styles["subtitle"],
        ))
        story.append(HRFlowable(
            width="100%", thickness=2, color=BRAND_PRIMARY,
            spaceAfter=16, spaceBefore=4,
        ))

        # --- Section 1: Your Strengths ---
        story.append(Paragraph("Your Strengths", self.styles["h2"]))
        story.append(Paragraph(
            "These are the things you're doing well. Reflect on how you "
            "can continue to build on these strengths.",
            self.styles["body_italic"],
        ))

        for i, strength in enumerate(strengths or [], 1):
            title = strength.get("title", f"Strength {i}")
            story.append(Paragraph(
                f"<b>{i}. {self._safe(title)}</b>",
                self.styles["strength_title"],
            ))
            # Add lined space for notes
            self._add_lined_space(story, lines=3)

        # --- Section 2: Growth Opportunities ---
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph("Growth Opportunities", self.styles["h2"]))
        story.append(Paragraph(
            "These are areas where small changes can make a big impact. "
            "For each one, write down one specific thing you'll try in "
            "your next session.",
            self.styles["body_italic"],
        ))

        for i, growth in enumerate(growth_opportunities or [], 1):
            title = growth.get("title", f"Growth Area {i}")
            story.append(Paragraph(
                f"<b>{i}. {self._safe(title)}</b>",
                self.styles["growth_title"],
            ))
            story.append(Paragraph(
                "What I'll try next time:",
                self.styles["body"],
            ))
            self._add_lined_space(story, lines=3)

        # --- Section 3: Coaching Reflections ---
        story.append(PageBreak())
        story.append(Paragraph("Coaching Reflections", self.styles["h2"]))

        reflections = self._extract_reflections(report_markdown)
        if reflections:
            for i, question in enumerate(reflections, 1):
                story.append(Paragraph(
                    f"<b>Question {i}:</b> {self._safe(question)}",
                    self.styles["body"],
                ))
                self._add_lined_space(story, lines=5)
        else:
            # Fallback generic reflections
            for question in [
                "What moment in this session are you most proud of? Why?",
                "If you could re-teach one segment, what would you change?",
                "What is one goal you'll set for your next session?",
            ]:
                story.append(Paragraph(
                    f"<b>Reflect:</b> {question}",
                    self.styles["body"],
                ))
                self._add_lined_space(story, lines=5)

        # --- Section 4: My Action Plan ---
        story.append(Paragraph("My Action Plan", self.styles["h2"]))
        story.append(Paragraph(
            "Write 1-3 concrete actions you'll take before your next session.",
            self.styles["body_italic"],
        ))

        for i in range(1, 4):
            story.append(Paragraph(f"<b>Action {i}:</b>", self.styles["body"]))
            self._add_lined_space(story, lines=3)

        # --- Footer ---
        story.append(Spacer(1, 0.3 * inch))
        story.append(HRFlowable(
            width="100%", thickness=1, color=BRAND_MUTED,
            spaceAfter=8, spaceBefore=8,
        ))
        story.append(Paragraph(
            "Adult Learning Coaching Agent  •  Reflection Worksheet",
            self.styles["footer"],
        ))

        doc.build(story, onFirstPage=self._add_page_number,
                  onLaterPages=self._add_page_number)

        return buffer.getvalue()

    # ------------------------------------------------------------------
    # SECTION RENDERERS — Each handles one section of the coaching report
    # ------------------------------------------------------------------

    def _render_executive_summary(self, story: list, markdown: str):
        """Render the Executive Summary section."""
        story.append(Paragraph("Executive Summary", self.styles["h2"]))

        summary = self._extract_section(markdown, "Executive Summary")
        if summary:
            story.append(Paragraph(self._safe(summary), self.styles["body"]))
        story.append(Spacer(1, 0.1 * inch))

    def _render_metrics_table(self, story: list, metrics: dict):
        """Render the Metrics Snapshot as a professional table.

        This is the visual centerpiece of the report — a clean table
        showing each metric, its value, target, and status indicator.
        """
        story.append(Paragraph("Metrics Snapshot", self.styles["h2"]))

        # Define metric display configuration
        metric_rows = [
            ("Speaking Pace", "wpm", "WPM", "120-160", 120, 160),
            ("Strategic Pauses", "pauses_per_10min", "per 10 min", "4-6", 4, 6),
            ("Filler Words", "filler_words_per_min", "per min", "<3", None, 3),
            ("Questions Asked", "questions_per_5min", "per 5 min", ">1", 1, None),
            ("Tangent Time", "tangent_percentage", "%", "<10%", None, 10),
        ]

        # Build table data: [header_row, data_rows...]
        header = ["Metric", "Value", "Target", "Status"]
        table_data = [header]

        for label, key, unit, target, low, high in metric_rows:
            value = metrics.get(key)
            if value is not None:
                display_value = f"{value:.1f} {unit}" if isinstance(value, float) else f"{value} {unit}"
                status = self._get_status_text(value, low, high)
            else:
                display_value = "—"
                status = "—"

            table_data.append([label, display_value, target, status])

        # Create table with styling
        col_widths = [2.5 * inch, 1.5 * inch, 1.2 * inch, 1.2 * inch]
        table = Table(table_data, colWidths=col_widths)

        table.setStyle(TableStyle([
            # Header row
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_PRIMARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("TOPPADDING", (0, 0), (-1, 0), 8),

            # Data rows
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("ALIGN", (1, 1), (-1, -1), "CENTER"),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
            ("TOPPADDING", (0, 1), (-1, -1), 6),

            # Alternating row colors
            *[("BACKGROUND", (0, i), (-1, i), BRAND_LIGHT_BG)
              for i in range(2, len(table_data), 2)],

            # Grid
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("LINEBELOW", (0, 0), (-1, 0), 2, BRAND_PRIMARY),
        ]))

        story.append(table)
        story.append(Spacer(1, 0.1 * inch))

    def _render_strengths(self, story: list, markdown: str, strengths: list):
        """Render the Strengths to Build On section."""
        story.append(Paragraph(
            "Strengths to Build On",
            self.styles["h2"],
        ))

        # Use extracted strengths if available, otherwise parse from markdown
        if strengths:
            for i, strength in enumerate(strengths, 1):
                title = strength.get("title", f"Strength {i}")
                text = strength.get("text", "")
                timestamp = strength.get("timestamp")

                elements = []
                elements.append(Paragraph(
                    f"<b>{self._safe(title)}</b>"
                    + (f"  <font color='#718096'>[{timestamp}]</font>" if timestamp else ""),
                    self.styles["strength_title"],
                ))

                # Parse out the sub-bullets from the text
                for line in text.split("\n"):
                    line = line.strip()
                    if line.startswith("- ") or line.startswith("• "):
                        line = line[2:]
                    if line:
                        elements.append(Paragraph(
                            f"• {self._safe(line)}",
                            self.styles["sub_bullet"],
                        ))

                elements.append(Spacer(1, 4))
                story.append(KeepTogether(elements))
        else:
            # Fallback: render raw markdown section
            section = self._extract_section(markdown, "Strengths to Build On")
            if section:
                self._render_markdown_section(story, section, self.styles["strength_title"])

    def _render_growth_opportunities(self, story: list, markdown: str, growth: list):
        """Render the Growth Opportunities section."""
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph(
            "Growth Opportunities",
            self.styles["h2"],
        ))

        if growth:
            for i, item in enumerate(growth, 1):
                title = item.get("title", f"Growth Area {i}")
                text = item.get("text", "")
                timestamp = item.get("timestamp")

                elements = []
                elements.append(Paragraph(
                    f"<b>{self._safe(title)}</b>"
                    + (f"  <font color='#718096'>[{timestamp}]</font>" if timestamp else ""),
                    self.styles["growth_title"],
                ))

                for line in text.split("\n"):
                    line = line.strip()
                    if line.startswith("- ") or line.startswith("• "):
                        line = line[2:]
                    if line:
                        elements.append(Paragraph(
                            f"• {self._safe(line)}",
                            self.styles["sub_bullet"],
                        ))

                elements.append(Spacer(1, 4))
                story.append(KeepTogether(elements))
        else:
            section = self._extract_section(markdown, "Growth Opportunities")
            if section:
                self._render_markdown_section(story, section, self.styles["growth_title"])

    def _render_prioritized_improvements(self, story: list, markdown: str):
        """Render the Top 5 Prioritized Improvements section."""
        story.append(Paragraph(
            "Top 5 Prioritized Improvements",
            self.styles["h2"],
        ))

        section = self._extract_section(markdown, "Top 5 Prioritized Improvements")
        if not section:
            return

        # Parse numbered items: "1. **Title**\n   - bullet..."
        # Use findall instead of split to capture both number and title reliably
        item_pattern = r'(\d+)\.\s+\*\*(.+?)\*\*\s*\n(.*?)(?=\n\d+\.\s+\*\*|\Z)'
        matches = re.findall(item_pattern, section, re.DOTALL)

        for num, title, body in matches:
            bullets = [b.strip().lstrip("- ") for b in body.strip().split("\n")
                       if b.strip().startswith("-")]

            elements = []
            elements.append(Paragraph(
                f"<font color='{BRAND_SECONDARY.hexval()}'><b>{num}.</b></font> "
                f"<b>{self._safe(title.strip())}</b>",
                self.styles["h3"],
            ))

            for bullet in bullets:
                elements.append(Paragraph(
                    f"• {self._safe(bullet)}",
                    self.styles["sub_bullet"],
                ))

            elements.append(Spacer(1, 4))
            story.append(KeepTogether(elements))

    def _render_timestamped_moments(self, story: list, markdown: str):
        """Render the Timestamped Moments to Review section."""
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph(
            "Timestamped Moments to Review",
            self.styles["h2"],
        ))

        section = self._extract_section(markdown, "Timestamped Moments to Review")
        if not section:
            return

        # Parse "- [HH:MM:SS] — Description" lines
        moment_pattern = r'-\s*\[(\d{2}:\d{2}:\d{2})\]\s*[—–-]\s*(.+)'
        moments = re.findall(moment_pattern, section)

        if moments:
            # Build a clean table of timestamps
            table_data = [["Timestamp", "What to Notice"]]
            for ts, desc in moments:
                table_data.append([ts, desc.strip()])

            table = Table(table_data, colWidths=[1.2 * inch, 5.2 * inch])
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), BRAND_SECONDARY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                *[("BACKGROUND", (0, i), (-1, i), BRAND_LIGHT_BG)
                  for i in range(2, len(table_data), 2)],
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("LINEBELOW", (0, 0), (-1, 0), 2, BRAND_SECONDARY),
            ]))
            story.append(table)

    def _render_reflections_and_next_steps(self, story: list, markdown: str):
        """Render Coaching Reflections and Next Steps sections."""
        # Reflections
        story.append(Paragraph("Coaching Reflections", self.styles["h2"]))

        reflections = self._extract_reflections(markdown)
        for i, question in enumerate(reflections, 1):
            story.append(Paragraph(
                f"<b>{i}.</b> {self._safe(question)}",
                self.styles["body"],
            ))
            story.append(Spacer(1, 4))

        # Next Steps
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph("Next Steps", self.styles["h2"]))

        next_steps = self._extract_section(markdown, "Next Steps")
        if next_steps:
            # Strip trailing markdown footer (--- and *text*)
            next_steps = re.sub(r'\n---.*', '', next_steps, flags=re.DOTALL)

            # Parse numbered items with bold titles
            steps = re.findall(
                r'\d+\.\s+\*\*(.+?)\*\*:?\s*(.*?)(?=\n\d+\.|\Z)',
                next_steps, re.DOTALL,
            )
            for title, body in steps:
                # Remove trailing colon from title (Claude formats "One thing to keep doing:")
                clean_title = title.rstrip(":")
                clean_body = body.strip()
                story.append(Paragraph(
                    f"<b>{self._safe(clean_title)}:</b> {self._safe(clean_body)}",
                    self.styles["bullet"],
                ))
                story.append(Spacer(1, 4))

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _extract_section(self, markdown: str, heading: str) -> str:
        """Extract text content between a ## heading and the next ## heading."""
        pattern = rf'##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)'
        match = re.search(pattern, markdown, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _extract_reflections(self, markdown: str) -> list[str]:
        """Extract reflection questions from the Coaching Reflections section."""
        section = self._extract_section(markdown, "Coaching Reflections")
        if not section:
            return []

        # Pattern: "1. **Title:** Question text"
        questions = re.findall(
            r'\d+\.\s+\*\*.*?\*\*:?\s*(.*?)(?=\n\d+\.|\Z)',
            section, re.DOTALL,
        )
        return [q.strip() for q in questions if q.strip()]

    def _render_markdown_section(self, story: list, text: str, title_style):
        """Render a raw markdown section as paragraphs and bullets."""
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("**") and line.endswith("**"):
                # Bold heading
                title = line.strip("*").strip()
                story.append(Paragraph(
                    f"<b>{self._safe(title)}</b>", title_style,
                ))
            elif line.startswith("- "):
                story.append(Paragraph(
                    f"• {self._safe(line[2:])}",
                    self.styles["sub_bullet"],
                ))
            else:
                story.append(Paragraph(
                    self._safe(line), self.styles["body"],
                ))

    def _get_status_text(self, value: float, low: Optional[float], high: Optional[float]) -> str:
        """Return a status indicator based on value vs targets."""
        if low is not None and high is not None:
            # Range target (e.g., 120-160 WPM)
            if low <= value <= high:
                return "On Target"
            elif abs(value - low) <= low * 0.1 or abs(value - high) <= high * 0.1:
                return "Near Target"
            else:
                return "Needs Focus"
        elif high is not None:
            # Max target (e.g., <3 filler words)
            if value <= high:
                return "On Target"
            elif value <= high * 1.5:
                return "Near Target"
            else:
                return "Needs Focus"
        elif low is not None:
            # Min target (e.g., >1 question per 5 min)
            if value >= low:
                return "On Target"
            elif value >= low * 0.5:
                return "Near Target"
            else:
                return "Needs Focus"
        return "—"

    def _add_lined_space(self, story: list, lines: int = 4):
        """Add lined writing space for the reflection worksheet."""
        for _ in range(lines):
            story.append(Spacer(1, 16))
            story.append(HRFlowable(
                width="100%", thickness=0.5, color=colors.HexColor("#cbd5e0"),
                spaceAfter=0, spaceBefore=0,
            ))

    @staticmethod
    def _safe(text: str) -> str:
        """Escape text for ReportLab's XML-based paragraph parser.

        ReportLab paragraphs use an HTML-like markup system.
        Raw text with <, >, & characters will break the parser.
        """
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        # But we want our own HTML tags to work, so restore them
        text = text.replace("&lt;b&gt;", "<b>")
        text = text.replace("&lt;/b&gt;", "</b>")
        text = text.replace("&lt;i&gt;", "<i>")
        text = text.replace("&lt;/i&gt;", "</i>")
        return text

    @staticmethod
    def _add_page_number(canvas, doc):
        """Add page numbers to the bottom of each page."""
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#718096"))
        page_num = canvas.getPageNumber()
        canvas.drawCentredString(
            letter[0] / 2, 0.4 * inch,
            f"Page {page_num}",
        )
        canvas.restoreState()

"""
PDF generator for multi-video comparison reports.

Produces a professional PDF that presents cross-session analysis:
1. Cover page with comparison title and metadata
2. Evaluation overview table (which sessions were compared)
3. Cross-session metrics comparison table
4. Strengths & growth opportunities sections
5. Full comparison analysis (parsed from markdown)

Uses the same ReportLab/Platypus approach as pdf_report.py but with
comparison-specific sections (no timestamps, no individual metrics —
instead, cross-session tables and trend analysis).

Design decision: Separate class from PDFReportGenerator rather than
extending it. Comparison PDFs have fundamentally different section
structure. Shared constants (colors, page numbers) are imported from
the existing module.
"""

import re
from datetime import datetime
from io import BytesIO
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Reuse brand colors from the existing PDF module for visual consistency
from app.services.pdf_report import (
    BRAND_ACCENT,
    BRAND_CAUTION,
    BRAND_LIGHT_BG,
    BRAND_MUTED,
    BRAND_PRIMARY,
    BRAND_SECONDARY,
    BRAND_TEXT,
)

# --- Comparison-specific color ---
BRAND_COMPARE = colors.HexColor("#805ad5")  # Purple — comparison accent


def _build_comparison_styles() -> dict:
    """Create paragraph styles for comparison report PDFs.

    Reuses the same design language as coaching report styles
    (font sizes, color palette) but adds comparison-specific styles
    for metric tables and evaluation summaries.
    """
    base = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "CompTitle",
            parent=base["Title"],
            fontSize=24,
            textColor=BRAND_PRIMARY,
            spaceAfter=6,
            alignment=TA_LEFT,
        ),
        "subtitle": ParagraphStyle(
            "CompSubtitle",
            parent=base["Normal"],
            fontSize=12,
            textColor=BRAND_MUTED,
            spaceAfter=20,
        ),
        "h2": ParagraphStyle(
            "CompH2",
            parent=base["Heading2"],
            fontSize=16,
            textColor=BRAND_PRIMARY,
            spaceBefore=16,
            spaceAfter=8,
        ),
        "h3": ParagraphStyle(
            "CompH3",
            parent=base["Heading3"],
            fontSize=13,
            textColor=BRAND_SECONDARY,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "CompBody",
            parent=base["Normal"],
            fontSize=10,
            textColor=BRAND_TEXT,
            leading=14,
            spaceAfter=6,
        ),
        "body_italic": ParagraphStyle(
            "CompBodyItalic",
            parent=base["Normal"],
            fontSize=10,
            textColor=BRAND_MUTED,
            leading=14,
            spaceAfter=6,
            fontName="Helvetica-Oblique",
        ),
        "bullet": ParagraphStyle(
            "CompBullet",
            parent=base["Normal"],
            fontSize=10,
            textColor=BRAND_TEXT,
            leading=14,
            leftIndent=20,
            spaceAfter=4,
            bulletIndent=8,
        ),
        "sub_bullet": ParagraphStyle(
            "CompSubBullet",
            parent=base["Normal"],
            fontSize=9,
            textColor=BRAND_TEXT,
            leading=13,
            leftIndent=36,
            spaceAfter=3,
            bulletIndent=24,
        ),
        "strength_title": ParagraphStyle(
            "CompStrengthTitle",
            parent=base["Normal"],
            fontSize=11,
            textColor=BRAND_ACCENT,
            fontName="Helvetica-Bold",
            spaceBefore=8,
            spaceAfter=4,
        ),
        "growth_title": ParagraphStyle(
            "CompGrowthTitle",
            parent=base["Normal"],
            fontSize=11,
            textColor=BRAND_CAUTION,
            fontName="Helvetica-Bold",
            spaceBefore=8,
            spaceAfter=4,
        ),
        "footer": ParagraphStyle(
            "CompFooter",
            parent=base["Normal"],
            fontSize=8,
            textColor=BRAND_MUTED,
            alignment=TA_CENTER,
        ),
    }


# --- Comparison type display names ---
TYPE_LABELS = {
    "personal_performance": "Personal Performance Comparison",
    "class_delivery": "Class Delivery Comparison",
    "program_evaluation": "Program Evaluation",
}


class ComparisonPDFGenerator:
    """Generates professional PDF reports for multi-video comparisons.

    Usage:
        generator = ComparisonPDFGenerator()
        pdf_bytes = generator.generate_comparison_report(
            title="Q1 Instructor Comparison",
            comparison_type="class_delivery",
            report_markdown="# Cross-Session Analysis...",
            metrics={"evaluations_compared": 3, ...},
            strengths=[{"title": "...", "text": "..."}],
            growth_opportunities=[{"title": "...", "text": "..."}],
            evaluations=[{"label": "Session 1", ...}],
        )
    """

    def __init__(self):
        self.styles = _build_comparison_styles()

    def generate_comparison_report(
        self,
        title: str,
        comparison_type: str,
        report_markdown: str = "",
        metrics: Optional[dict] = None,
        strengths: Optional[list] = None,
        growth_opportunities: Optional[list] = None,
        evaluations: Optional[list] = None,
    ) -> bytes:
        """Generate a comparison report PDF.

        Args:
            title: Comparison title (user-provided).
            comparison_type: One of personal_performance, class_delivery,
                program_evaluation.
            report_markdown: Full comparison analysis from Claude.
            metrics: Aggregated comparison metrics dict.
            strengths: List of cross-session strength dicts.
            growth_opportunities: List of cross-session growth area dicts.
            evaluations: List of evaluation summary dicts with keys:
                label, instructor_name, status, date (optional).

        Returns:
            Raw PDF bytes ready to stream via HTTP or save to disk.
        """
        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
            title=f"Comparison Report - {title}",
            author="Adult Learning Coaching Agent",
        )

        story = []

        # --- Cover / Title ---
        story.append(Spacer(1, 0.5 * inch))
        story.append(Paragraph("Comparison Report", self.styles["title"]))
        story.append(Paragraph(self._safe(title), self.styles["h2"]))
        type_label = TYPE_LABELS.get(comparison_type, comparison_type)
        story.append(Paragraph(
            f"{type_label}  •  "
            f"{len(evaluations or [])} evaluations compared  •  "
            f"Generated {datetime.now().strftime('%B %d, %Y')}",
            self.styles["subtitle"],
        ))
        story.append(HRFlowable(
            width="100%", thickness=2, color=BRAND_COMPARE,
            spaceAfter=16, spaceBefore=4,
        ))

        # --- Evaluations Overview Table ---
        self._render_evaluations_table(story, evaluations or [])

        # --- Cross-Session Metrics ---
        self._render_metrics_summary(story, metrics or {})

        story.append(PageBreak())

        # --- Strengths ---
        self._render_strengths(story, strengths or [])

        # --- Growth Opportunities ---
        self._render_growth_opportunities(story, growth_opportunities or [])

        story.append(PageBreak())

        # --- Full Comparison Analysis ---
        self._render_full_report(story, report_markdown)

        # --- Footer ---
        story.append(Spacer(1, 0.3 * inch))
        story.append(HRFlowable(
            width="100%", thickness=1, color=BRAND_MUTED,
            spaceAfter=8, spaceBefore=8,
        ))
        story.append(Paragraph(
            "Analysis generated by Adult Learning Coaching Agent  •  "
            "Multi-Video Comparison",
            self.styles["footer"],
        ))

        doc.build(
            story,
            onFirstPage=self._add_page_number,
            onLaterPages=self._add_page_number,
        )

        return buffer.getvalue()

    # ------------------------------------------------------------------
    # SECTION RENDERERS
    # ------------------------------------------------------------------

    def _render_evaluations_table(self, story: list, evaluations: list):
        """Render a table of the evaluations included in this comparison.

        Shows each session's label, instructor, and status in a clean
        table format. This gives the reader immediate context about what
        was compared.
        """
        if not evaluations:
            return

        story.append(Paragraph("Evaluations Compared", self.styles["h2"]))

        header = ["#", "Session", "Instructor", "Status"]
        table_data = [header]

        for i, ev in enumerate(evaluations, 1):
            table_data.append([
                str(i),
                ev.get("label", f"Session {i}"),
                ev.get("instructor_name", "Unknown"),
                ev.get("status", "—"),
            ])

        col_widths = [0.5 * inch, 2.5 * inch, 2.5 * inch, 1.2 * inch]
        table = Table(table_data, colWidths=col_widths)

        table.setStyle(TableStyle([
            # Header
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_COMPARE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
            # Data
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("ALIGN", (0, 1), (0, -1), "CENTER"),
            ("ALIGN", (3, 1), (3, -1), "CENTER"),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
            ("TOPPADDING", (0, 1), (-1, -1), 6),
            # Alternating rows
            *[("BACKGROUND", (0, i), (-1, i), BRAND_LIGHT_BG)
              for i in range(2, len(table_data), 2)],
            # Grid
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("LINEBELOW", (0, 0), (-1, 0), 2, BRAND_COMPARE),
        ]))

        story.append(table)
        story.append(Spacer(1, 0.2 * inch))

    def _render_metrics_summary(self, story: list, metrics: dict):
        """Render cross-session metrics as a summary table.

        The comparison pipeline stores aggregated metrics like
        evaluations_compared, avg/min/max scores, and trend direction.
        We present the most useful ones in a clean table.
        """
        if not metrics:
            return

        story.append(Paragraph("Comparison Metrics", self.styles["h2"]))

        # Build rows from available metrics. We show a curated subset
        # rather than dumping everything — keeps the table readable.
        table_data = [["Metric", "Value"]]

        # Evaluation count is always useful context
        if "evaluations_compared" in metrics:
            table_data.append([
                "Evaluations Compared",
                str(metrics["evaluations_compared"]),
            ])

        # Aggregate metrics from individual evaluations
        metric_keys = [
            ("avg_wpm", "Average Speaking Pace (WPM)"),
            ("avg_pauses_per_10min", "Average Pauses per 10 min"),
            ("avg_filler_words_per_min", "Average Filler Words per min"),
            ("avg_questions_per_5min", "Average Questions per 5 min"),
            ("avg_tangent_percentage", "Average Tangent Time (%)"),
        ]

        for key, label in metric_keys:
            if key in metrics:
                value = metrics[key]
                display = f"{value:.1f}" if isinstance(value, float) else str(value)
                table_data.append([label, display])

        # Trend information
        if "wpm_trend" in metrics:
            table_data.append([
                "Speaking Pace Trend",
                metrics["wpm_trend"].replace("_", " ").title(),
            ])

        # Only render if we have data beyond the header
        if len(table_data) <= 1:
            return

        col_widths = [4.5 * inch, 2.0 * inch]
        table = Table(table_data, colWidths=col_widths)

        table.setStyle(TableStyle([
            # Header
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_PRIMARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
            # Data
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("ALIGN", (1, 1), (1, -1), "CENTER"),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
            ("TOPPADDING", (0, 1), (-1, -1), 6),
            # Alternating rows
            *[("BACKGROUND", (0, i), (-1, i), BRAND_LIGHT_BG)
              for i in range(2, len(table_data), 2)],
            # Grid
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("LINEBELOW", (0, 0), (-1, 0), 2, BRAND_PRIMARY),
        ]))

        story.append(table)
        story.append(Spacer(1, 0.2 * inch))

    def _render_strengths(self, story: list, strengths: list):
        """Render cross-session strengths section."""
        if not strengths:
            return

        story.append(Paragraph("Cross-Session Strengths", self.styles["h2"]))
        story.append(Paragraph(
            "Patterns of excellence that appear consistently across sessions.",
            self.styles["body_italic"],
        ))

        for i, strength in enumerate(strengths, 1):
            title = strength.get("title", f"Strength {i}")
            text = strength.get("text") or strength.get("description", "")

            elements = []
            elements.append(Paragraph(
                f"<b>{self._safe(title)}</b>",
                self.styles["strength_title"],
            ))

            if text:
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

    def _render_growth_opportunities(self, story: list, growth: list):
        """Render cross-session growth opportunities section."""
        if not growth:
            return

        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph("Growth Opportunities", self.styles["h2"]))
        story.append(Paragraph(
            "Areas where targeted improvement would have the highest impact.",
            self.styles["body_italic"],
        ))

        for i, item in enumerate(growth, 1):
            title = item.get("title", f"Growth Area {i}")
            text = item.get("text") or item.get("description", "")

            elements = []
            elements.append(Paragraph(
                f"<b>{self._safe(title)}</b>",
                self.styles["growth_title"],
            ))

            if text:
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

    def _render_full_report(self, story: list, markdown: str):
        """Render the full comparison markdown report.

        Parses the markdown line-by-line, same approach as the
        coaching report PDF. Handles headings, bullets, numbered
        lists, and body text with bold support.
        """
        if not markdown:
            return

        story.append(Paragraph("Full Comparison Analysis", self.styles["h2"]))
        story.append(HRFlowable(
            width="100%", thickness=1, color=BRAND_COMPARE,
            spaceAfter=12, spaceBefore=4,
        ))

        for line in markdown.split("\n"):
            trimmed = line.strip()

            if not trimmed:
                story.append(Spacer(1, 4))
            elif trimmed.startswith("# ") and not trimmed.startswith("## "):
                # Top-level heading — skip (we already have section titles)
                pass
            elif trimmed.startswith("## "):
                story.append(Paragraph(
                    self._safe(trimmed[3:]),
                    self.styles["h2"],
                ))
            elif trimmed.startswith("### "):
                story.append(Paragraph(
                    self._safe(trimmed[4:]),
                    self.styles["h3"],
                ))
            elif trimmed.startswith("---"):
                story.append(HRFlowable(
                    width="100%", thickness=0.5, color=BRAND_MUTED,
                    spaceAfter=8, spaceBefore=8,
                ))
            elif trimmed.startswith("- ") or trimmed.startswith("* "):
                content = trimmed[2:]
                story.append(Paragraph(
                    f"• {self._bold_safe(content)}",
                    self.styles["bullet"],
                ))
            elif re.match(r'^\d+\.\s', trimmed):
                story.append(Paragraph(
                    self._bold_safe(trimmed),
                    self.styles["bullet"],
                ))
            elif (trimmed.startswith("*") and trimmed.endswith("*")
                  and not trimmed.startswith("**")):
                # Italic line
                story.append(Paragraph(
                    f"<i>{self._safe(trimmed.strip('*'))}</i>",
                    self.styles["body_italic"],
                ))
            else:
                story.append(Paragraph(
                    self._bold_safe(trimmed),
                    self.styles["body"],
                ))

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    @staticmethod
    def _safe(text: str) -> str:
        """Escape text for ReportLab's XML paragraph parser.

        Same approach as PDFReportGenerator — escape &, <, >
        but preserve our own <b>, </b>, <i>, </i> tags.
        """
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        # Restore intentional HTML tags
        for tag in ["b", "/b", "i", "/i"]:
            text = text.replace(f"&lt;{tag}&gt;", f"<{tag}>")
        return text

    @classmethod
    def _bold_safe(cls, text: str) -> str:
        """Escape text and convert **bold** markdown to <b>bold</b> tags."""
        # Convert markdown bold BEFORE escaping, so we can preserve it
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        return cls._safe(text)

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

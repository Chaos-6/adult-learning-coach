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
        class_name: Optional[str] = None,
        metrics: Optional[dict] = None,
        strengths: Optional[list] = None,
        growth_opportunities: Optional[list] = None,
        coaching_data: Optional[dict] = None,
    ) -> bytes:
        """Generate the full coaching report PDF.

        When coaching_data (the parsed JSON from Claude) is provided, ALL
        sections render from structured data — no markdown parsing needed.
        This is the primary path for new evaluations and eliminates the
        empty-section bug where markdown parsers fail on JSON strings.

        Falls back to legacy markdown parsing when coaching_data is absent
        (backward compatibility with older evaluation records).

        Returns raw PDF bytes (ready to save to disk or stream via HTTP).
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
        # Title order: Class Name first (identifier), then Instructor Name
        if class_name:
            story.append(Paragraph(
                self._safe(class_name) + ": Coaching Report",
                self.styles["title"],
            ))
            story.append(Paragraph(
                self._safe(instructor_name),
                self.styles["h2"],
            ))
        else:
            story.append(Paragraph(
                self._safe(instructor_name) + ": Coaching Report",
                self.styles["title"],
            ))
        story.append(Paragraph(
            f"Generated {datetime.now().strftime('%B %d, %Y')}",
            self.styles["subtitle"],
        ))
        story.append(HRFlowable(
            width="100%", thickness=2, color=BRAND_PRIMARY,
            spaceAfter=12, spaceBefore=4,
        ))

        # --- Render each section ---
        # When coaching_data is available, use it as the authoritative source
        # for ALL sections. Fall back to markdown parsing for legacy records.
        if coaching_data:
            self._render_executive_summary_from_json(story, coaching_data)
            self._render_metrics_table(story, coaching_data.get("metrics", {}))
            story.append(PageBreak())
            self._render_strengths_from_json(story, coaching_data)
            self._render_growth_opportunities_from_json(story, coaching_data)
            story.append(PageBreak())
            self._render_prioritized_improvements_from_json(story, coaching_data)
            self._render_timestamped_moments_from_json(story, coaching_data)
            story.append(PageBreak())
            self._render_reflections_from_json(story, coaching_data)
            self._render_next_steps_from_json(story, coaching_data)
        else:
            # Legacy path: parse from markdown/raw text
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
        class_name: Optional[str] = None,
        strengths: Optional[list] = None,
        growth_opportunities: Optional[list] = None,
        report_markdown: str = "",
        coaching_data: Optional[dict] = None,
    ) -> bytes:
        """Generate the reflection worksheet PDF.

        When coaching_data (the parsed JSON from Claude) is provided, it is
        used as the authoritative source for all sections — no markdown parsing,
        no missing sections, no markdown bleed-through.

        Falls back to the legacy path when coaching_data is not available
        (backward compatibility with older evaluation records).
        """
        if coaching_data:
            return self._generate_worksheet_from_json(coaching_data, class_name)
        return self._generate_worksheet_legacy(
            instructor_name, class_name, strengths, growth_opportunities, report_markdown
        )

    def _generate_worksheet_from_json(
        self,
        data: dict,
        class_name: Optional[str] = None,
    ) -> bytes:
        """Render the worksheet entirely from the structured JSON coaching_data dict.

        This is the primary path for all new evaluations. Every section maps
        directly to a key in the JSON — no regex, no markdown parsing.
        """
        # Extra colors needed for the new sections
        COLOR_RULE  = colors.HexColor("#CBD5E0")
        COLOR_RANK  = colors.HexColor("#C05621")
        COLOR_TS    = colors.HexColor("#276749")

        base = getSampleStyleSheet()

        def s(name, **kw):
            return ParagraphStyle(name, parent=base["Normal"], **kw)

        st = {
            "doc_title":  s("ws_doc_title",  fontName="Helvetica-Bold", fontSize=20,
                            textColor=BRAND_PRIMARY, alignment=TA_CENTER, spaceAfter=4),
            "doc_sub":    s("ws_doc_sub",    fontName="Helvetica", fontSize=11,
                            textColor=BRAND_MUTED, alignment=TA_CENTER, spaceAfter=16),
            "sec_hdr":    s("ws_sec_hdr",    fontName="Helvetica-Bold", fontSize=13,
                            textColor=colors.white, leftIndent=8, spaceBefore=14, spaceAfter=8),
            "sec_desc":   s("ws_sec_desc",   fontName="Helvetica-Oblique", fontSize=9,
                            textColor=BRAND_MUTED, spaceAfter=8),
            "item_title": s("ws_item_title", fontName="Helvetica-Bold", fontSize=11,
                            textColor=BRAND_SECONDARY, spaceBefore=10, spaceAfter=3),
            "sub_label":  s("ws_sub_label",  fontName="Helvetica-Bold", fontSize=9,
                            textColor=BRAND_MUTED, spaceAfter=2),
            "body":       s("ws_body",       fontName="Helvetica", fontSize=9.5,
                            textColor=BRAND_TEXT, leading=14, spaceAfter=6),
            "ts":         s("ws_ts",         fontName="Helvetica-Bold", fontSize=9,
                            textColor=COLOR_TS, spaceAfter=1),
            "rank":       s("ws_rank",       fontName="Helvetica-Bold", fontSize=22,
                            textColor=COLOR_RANK, alignment=TA_CENTER),
            "reflect":    s("ws_reflect",    fontName="Helvetica-Oblique", fontSize=10,
                            textColor=BRAND_PRIMARY, spaceAfter=4),
            "action_lbl": s("ws_action_lbl", fontName="Helvetica-Bold", fontSize=10,
                            textColor=BRAND_SECONDARY, spaceAfter=2),
            "footer":     s("ws_footer",     fontName="Helvetica-Oblique", fontSize=8,
                            textColor=BRAND_MUTED, alignment=TA_CENTER),
        }

        def banner(title):
            """Navy section header banner."""
            p = Paragraph(title.upper(), st["sec_hdr"])
            t = Table([[p]], colWidths=[7.0 * inch])
            t.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), BRAND_PRIMARY),
                ("TOPPADDING",    (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING",   (0, 0), (-1, -1), 10),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
            ]))
            return t

        def dotted_lines(n=3):
            return [HRFlowable(width="100%", thickness=0.5, color=COLOR_RULE,
                               spaceAfter=14, spaceBefore=2, dash=(2, 4))
                    for _ in range(n)]

        def thin_rule():
            return HRFlowable(width="100%", thickness=0.5, color=COLOR_RULE,
                              spaceBefore=6, spaceAfter=6)

        buffer = BytesIO()
        topic = class_name or data.get("session_topic", "")
        name  = data.get("instructor_name", "Instructor")
        date  = data.get("session_date", datetime.now().strftime("%B %d, %Y"))

        doc = SimpleDocTemplate(
            buffer, pagesize=letter,
            leftMargin=0.75 * inch, rightMargin=0.75 * inch,
            topMargin=0.75 * inch,  bottomMargin=0.75 * inch,
            title=f"Reflection Worksheet - {name}",
            author="Adult Learning Coaching Agent",
        )

        story = []

        # ---- Header ----
        story.append(Paragraph("Reflection Worksheet", st["doc_title"]))
        story.append(Paragraph(
            f"{self._safe(topic)}  |  {self._safe(name)}  |  {self._safe(date)}",
            st["doc_sub"]
        ))
        story.append(HRFlowable(width="100%", thickness=2, color=BRAND_PRIMARY, spaceAfter=12))

        # ---- Strengths ----
        story.append(banner("Your Strengths"))
        story.append(Paragraph(
            "These are the things you're doing well. Reflect on how you can continue "
            "to build on these strengths.",
            st["sec_desc"]
        ))
        for item in data.get("strengths", []):
            block = [
                Paragraph(f"{item['number']}.  {self._safe(item['title'])}", st["item_title"]),
                Paragraph("Why this is effective:", st["sub_label"]),
                Paragraph(self._safe(item.get("why_effective", "")), st["body"]),
                Paragraph("How to amplify:", st["sub_label"]),
                Paragraph(self._safe(item.get("how_to_amplify", "")), st["body"]),
                thin_rule(),
            ]
            story.append(KeepTogether(block))

        # ---- Growth Opportunities ----
        story.append(banner("Growth Opportunities"))
        story.append(Paragraph(
            "These are areas where small changes can make a big impact. "
            "For each one, write down one specific thing you'll try in your next session.",
            st["sec_desc"]
        ))
        for item in data.get("growth_opportunities", []):
            block = [
                Paragraph(f"{item['number']}.  {self._safe(item['title'])}", st["item_title"]),
                Paragraph("Why this matters:", st["sub_label"]),
                Paragraph(self._safe(item.get("why_it_matters", "")), st["body"]),
                Paragraph("Specific action to try:", st["sub_label"]),
                Paragraph(self._safe(item.get("specific_action", "")), st["body"]),
                Paragraph("What I'll try next time:", st["sub_label"]),
            ] + dotted_lines(2) + [thin_rule()]
            story.append(KeepTogether(block))

        # ---- Top 5 Prioritized Improvements ----
        story.append(banner("Top 5 Prioritized Improvements"))
        story.append(Paragraph(
            "Ranked by potential impact on learner outcomes. Start with Rank 1.",
            st["sec_desc"]
        ))
        for item in data.get("top_5_improvements", []):
            rank_cell = Paragraph(str(item.get("rank", "")), st["rank"])
            # Support both new format (title/observation/suggestions) and
            # legacy format (improvement/rationale)
            main_text = item.get("title", "") or item.get("improvement", "")
            sub_text = item.get("observation", "") or item.get("rationale", "")
            if item.get("suggestions"):
                sub_text += f" {item['suggestions']}" if sub_text else item["suggestions"]
            inner = Table(
                [[Paragraph(self._safe(main_text), st["body"])],
                 [Paragraph(self._safe(sub_text), st["sec_desc"])]],
                colWidths=[5.8 * inch]
            )
            inner.setStyle(TableStyle([
                ("TOPPADDING",    (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING",   (0, 0), (-1, -1), 0),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ]))
            row = Table([[rank_cell, inner]], colWidths=[0.7 * inch, 6.0 * inch])
            row.setStyle(TableStyle([
                ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
                ("BACKGROUND",    (0, 0), (0,  0),  BRAND_LIGHT_BG),
                ("TOPPADDING",    (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING",   (0, 0), (-1, -1), 8),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
                ("BOX",           (0, 0), (-1, -1), 0.5, COLOR_RULE),
                ("LINEAFTER",     (0, 0), (0,  -1), 0.5, COLOR_RULE),
            ]))
            story.append(KeepTogether([row, Spacer(1, 6)]))

        # ---- Timestamped Moments ----
        story.append(banner("Timestamped Moments to Review"))
        story.append(Paragraph(
            "Key moments from this session — both exemplary practices and areas to revisit.",
            st["sec_desc"]
        ))
        for moment in data.get("timestamped_moments", []):
            ts_p  = Paragraph(self._safe(moment.get("timestamp", "")), st["ts"])
            # Support both new format (type/coaching_note) and legacy (label/note)
            moment_type = moment.get("type", "")
            label = moment.get("label", "")
            coaching_note = moment.get("coaching_note", "")
            note = moment.get("note", "")
            context = moment.get("context", "")
            display_label = moment_type or label
            display_note = coaching_note or note or context
            lbl_p = Paragraph(
                f"<b>{self._safe(display_label)}</b>  "
                f"{self._safe(display_note)}",
                st["body"]
            )
            row = Table([[ts_p, lbl_p]], colWidths=[0.85 * inch, 5.85 * inch])
            row.setStyle(TableStyle([
                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING",    (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING",   (0, 0), (-1, -1), 6),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
                ("LINEBELOW",     (0, 0), (-1, -1), 0.5, COLOR_RULE),
            ]))
            story.append(row)
        story.append(Spacer(1, 8))

        # ---- Coaching Reflections ----
        story.append(banner("Coaching Reflections"))
        reflections = data.get("coaching_reflections", [])
        if isinstance(reflections, list):
            # New format: list of reflective question strings
            for prompt_text in reflections:
                story.append(KeepTogether(
                    [Paragraph(self._safe(prompt_text), st["reflect"])] + dotted_lines(3)
                ))
                story.append(Spacer(1, 4))
        elif isinstance(reflections, dict):
            # Legacy format: dict with named prompt keys
            for prompt_text in [
                reflections.get("proud_moment_prompt",      "What moment in this session are you most proud of? Why?"),
                reflections.get("reteach_prompt",           "If you could re-teach one segment, what would you change?"),
                reflections.get("next_session_goal_prompt", "What is one goal you will set for your next session?"),
            ]:
                story.append(KeepTogether(
                    [Paragraph(self._safe(prompt_text), st["reflect"])] + dotted_lines(3)
                ))
                story.append(Spacer(1, 4))

        # ---- Action Plan / Next Steps ----
        next_steps = data.get("next_steps", {})
        ap = data.get("action_plan", {})

        if isinstance(next_steps, dict) and next_steps:
            # New format: keep_doing / start_doing / adjust
            story.append(banner("Next Steps"))
            story.append(Paragraph(
                "Three concrete actions for your next session.",
                st["sec_desc"]
            ))
            labels = [
                ("keep_doing", "Keep doing"),
                ("start_doing", "Start doing"),
                ("adjust", "Adjust"),
            ]
            for key, label in labels:
                value = next_steps.get(key, "")
                story.append(KeepTogether([
                    Paragraph(self._safe(label), st["action_lbl"]),
                    Paragraph(self._safe(value), st["body"]) if value else Spacer(1, 1),
                ] + dotted_lines(2)))
                story.append(Spacer(1, 4))
        elif ap:
            # Legacy format: action_plan with numbered labels
            story.append(banner("My Action Plan"))
            story.append(Paragraph(
                self._safe(ap.get("instructions", "Write 1-3 concrete actions you will take before your next session.")),
                st["sec_desc"]
            ))
            for key in ["action_1_label", "action_2_label", "action_3_label"]:
                story.append(KeepTogether(
                    [Paragraph(self._safe(ap.get(key, "Action:")), st["action_lbl"])] + dotted_lines(2)
                ))
                story.append(Spacer(1, 4))

        # ---- Footer ----
        story.append(Spacer(1, 16))
        story.append(HRFlowable(width="100%", thickness=1, color=BRAND_PRIMARY))
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            "Adult Learning Coaching Agent  •  Reflection Worksheet",
            st["footer"]
        ))

        doc.build(story, onFirstPage=self._add_page_number, onLaterPages=self._add_page_number)
        return buffer.getvalue()

    def _generate_worksheet_legacy(
        self,
        instructor_name: str = "Instructor",
        class_name: Optional[str] = None,
        strengths: Optional[list] = None,
        growth_opportunities: Optional[list] = None,
        report_markdown: str = "",
    ) -> bytes:
        """Legacy worksheet renderer — used only when coaching_data is unavailable.

        Kept for backward compatibility with older evaluation records stored
        as raw markdown rather than structured JSON.
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=letter,
            topMargin=0.75 * inch, bottomMargin=0.75 * inch,
            leftMargin=0.75 * inch, rightMargin=0.75 * inch,
            title=f"Reflection Worksheet - {instructor_name}",
            author="Adult Learning Coaching Agent",
        )
        story = []

        if class_name:
            story.append(Paragraph(self._safe(class_name) + ": Reflection Worksheet", self.styles["title"]))
            story.append(Paragraph(self._safe(instructor_name), self.styles["h2"]))
        else:
            story.append(Paragraph(self._safe(instructor_name) + ": Reflection Worksheet", self.styles["title"]))
        story.append(Paragraph(f"Session reviewed: {datetime.now().strftime('%B %d, %Y')}", self.styles["subtitle"]))
        story.append(HRFlowable(width="100%", thickness=2, color=BRAND_PRIMARY, spaceAfter=16, spaceBefore=4))

        story.append(Paragraph("Your Strengths", self.styles["h2"]))
        story.append(Paragraph(
            "These are the things you're doing well. Reflect on how you can continue to build on these strengths.",
            self.styles["body_italic"],
        ))
        for i, strength in enumerate(strengths or [], 1):
            story.append(Paragraph(f"<b>{i}. {self._safe(strength.get('title', f'Strength {i}'))}</b>", self.styles["strength_title"]))
            self._add_lined_space(story, lines=3)

        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph("Growth Opportunities", self.styles["h2"]))
        story.append(Paragraph(
            "These are areas where small changes can make a big impact. "
            "For each one, write down one specific thing you'll try in your next session.",
            self.styles["body_italic"],
        ))
        for i, growth in enumerate(growth_opportunities or [], 1):
            story.append(Paragraph(f"<b>{i}. {self._safe(growth.get('title', f'Growth Area {i}'))}</b>", self.styles["growth_title"]))
            story.append(Paragraph("What I'll try next time:", self.styles["body"]))
            self._add_lined_space(story, lines=3)

        story.append(PageBreak())
        story.append(Paragraph("Coaching Reflections", self.styles["h2"]))
        for question in [
            "What moment in this session are you most proud of? Why?",
            "If you could re-teach one segment, what would you change?",
            "What is one goal you'll set for your next session?",
        ]:
            story.append(Paragraph(f"<b>Reflect:</b> {question}", self.styles["body"]))
            self._add_lined_space(story, lines=5)

        story.append(Paragraph("My Action Plan", self.styles["h2"]))
        story.append(Paragraph("Write 1-3 concrete actions you'll take before your next session.", self.styles["body_italic"]))
        for i in range(1, 4):
            story.append(Paragraph(f"<b>Action {i}:</b>", self.styles["body"]))
            self._add_lined_space(story, lines=3)

        story.append(Spacer(1, 0.3 * inch))
        story.append(HRFlowable(width="100%", thickness=1, color=BRAND_MUTED, spaceAfter=8, spaceBefore=8))
        story.append(Paragraph("Adult Learning Coaching Agent  •  Reflection Worksheet", self.styles["footer"]))

        doc.build(story, onFirstPage=self._add_page_number, onLaterPages=self._add_page_number)
        return buffer.getvalue()

    # ------------------------------------------------------------------
    # JSON-BASED SECTION RENDERERS — Primary path for new evaluations
    # ------------------------------------------------------------------
    # These methods render directly from the structured coaching_data dict
    # returned by Claude. No markdown parsing, no regex — every section
    # maps to a JSON key, so nothing is ever empty or missing.

    def _render_executive_summary_from_json(self, story: list, data: dict):
        """Render Executive Summary from JSON coaching_data."""
        story.append(Paragraph("Executive Summary", self.styles["h2"]))
        summary = data.get("executive_summary", "")
        if summary:
            story.append(Paragraph(self._safe(summary), self.styles["body"]))
        story.append(Spacer(1, 0.1 * inch))

    def _render_strengths_from_json(self, story: list, data: dict):
        """Render Strengths to Build On from JSON coaching_data."""
        story.append(Paragraph("Strengths to Build On", self.styles["h2"]))

        for item in data.get("strengths", []):
            title = item.get("title", "")
            segment = item.get("segment", "")
            timestamp = item.get("timestamp", "")

            elements = []
            # Title with segment label
            segment_label = f" (Segment {segment})" if segment else ""
            elements.append(Paragraph(
                f"<b>{self._safe(title)}{segment_label}</b>",
                self.styles["strength_title"],
            ))

            # Evidence quote with timestamp
            quote = item.get("evidence_quote", "")
            if quote or timestamp:
                ts_text = f"[{timestamp}] " if timestamp else ""
                elements.append(Paragraph(
                    f"<font color='#718096'>{self._safe(ts_text)}</font>"
                    f"<i>{self._safe(quote)}</i>",
                    self.styles["body"],
                ))

            # Why effective
            why = item.get("why_effective", "")
            if why:
                elements.append(Paragraph(
                    self._safe(why),
                    self.styles["sub_bullet"],
                ))

            # How to amplify
            amplify = item.get("how_to_amplify", "")
            if amplify:
                elements.append(Paragraph(
                    self._safe(amplify),
                    self.styles["sub_bullet"],
                ))

            elements.append(Spacer(1, 6))
            story.append(KeepTogether(elements))

    def _render_growth_opportunities_from_json(self, story: list, data: dict):
        """Render Growth Opportunities from JSON coaching_data."""
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph("Growth Opportunities", self.styles["h2"]))

        for item in data.get("growth_opportunities", []):
            title = item.get("title", "")
            segment = item.get("segment", "")
            timestamp = item.get("timestamp", "")

            elements = []
            segment_label = f" (Segment {segment})" if segment else ""
            elements.append(Paragraph(
                f"<b>{self._safe(title)}{segment_label}</b>",
                self.styles["growth_title"],
            ))

            # Evidence quote with timestamp
            quote = item.get("evidence_quote", "")
            if quote or timestamp:
                ts_text = f"[{timestamp}] " if timestamp else ""
                elements.append(Paragraph(
                    f"<font color='#718096'>{self._safe(ts_text)}</font>"
                    f"<i>{self._safe(quote)}</i>",
                    self.styles["body"],
                ))

            # Why it matters
            why = item.get("why_it_matters", "")
            if why:
                elements.append(Paragraph(
                    self._safe(why),
                    self.styles["sub_bullet"],
                ))

            # Specific action
            action = item.get("specific_action", "")
            if action:
                elements.append(Paragraph(
                    self._safe(action),
                    self.styles["sub_bullet"],
                ))

            elements.append(Spacer(1, 6))
            story.append(KeepTogether(elements))

    def _render_prioritized_improvements_from_json(self, story: list, data: dict):
        """Render Top 5 Prioritized Improvements from JSON coaching_data."""
        story.append(Paragraph(
            "Top 5 Prioritized Improvements",
            self.styles["h2"],
        ))

        for item in data.get("top_5_improvements", []):
            rank = item.get("rank", "")
            title = item.get("title", "")
            observation = item.get("observation", "")
            evidence = item.get("evidence", [])
            impact = item.get("impact", "")
            suggestions = item.get("suggestions", "")
            first_step = item.get("first_step", "")

            # Legacy format support: single sentence + rationale
            improvement = item.get("improvement", "")
            rationale = item.get("rationale", "")

            elements = []
            elements.append(Paragraph(
                f"<font color='{BRAND_SECONDARY.hexval()}'><b>{rank}.</b></font> "
                f"<b>{self._safe(title or improvement)}</b>",
                self.styles["h3"],
            ))

            if observation:
                elements.append(Paragraph(
                    self._safe(observation),
                    self.styles["body"],
                ))

            # Evidence timestamps
            if evidence:
                for ev in evidence:
                    elements.append(Paragraph(
                        f"<font color='#718096'>{self._safe(str(ev))}</font>",
                        self.styles["sub_bullet"],
                    ))

            if impact:
                elements.append(Paragraph(
                    f"<b>Impact:</b> {self._safe(impact)}",
                    self.styles["sub_bullet"],
                ))

            if suggestions:
                elements.append(Paragraph(
                    f"<b>Try this:</b> {self._safe(suggestions)}",
                    self.styles["sub_bullet"],
                ))

            if first_step:
                elements.append(Paragraph(
                    f"<b>First step:</b> {self._safe(first_step)}",
                    self.styles["sub_bullet"],
                ))

            # Legacy fallback for old-format items
            if rationale and not observation:
                elements.append(Paragraph(
                    self._safe(rationale),
                    self.styles["sub_bullet"],
                ))

            elements.append(Spacer(1, 4))
            story.append(KeepTogether(elements))

    def _render_timestamped_moments_from_json(self, story: list, data: dict):
        """Render Timestamped Moments to Review from JSON coaching_data."""
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph(
            "Timestamped Moments to Review",
            self.styles["h2"],
        ))

        moments = data.get("timestamped_moments", [])
        if not moments:
            return

        for moment in moments:
            timestamp = moment.get("timestamp", "")
            segment = moment.get("segment", "")
            moment_type = moment.get("type", "")
            context = moment.get("context", "")
            quote = moment.get("quote", "")
            coaching_note = moment.get("coaching_note", "")
            reframe = moment.get("suggested_reframe", "")

            # Legacy format support
            label = moment.get("label", "")
            note = moment.get("note", "")

            # Choose color based on type
            type_color = BRAND_ACCENT.hexval() if moment_type == "Exemplary" else BRAND_CAUTION.hexval()
            type_label = moment_type or label

            elements = []
            elements.append(Paragraph(
                f"<font color='#718096'>[{self._safe(timestamp)}]</font> "
                f"<font color='{type_color}'><b>{self._safe(type_label)}</b></font>"
                + (f"  {self._safe(context)}" if context else ""),
                self.styles["body"],
            ))

            if quote:
                elements.append(Paragraph(
                    f"<i>{self._safe(quote)}</i>",
                    self.styles["sub_bullet"],
                ))

            if coaching_note:
                elements.append(Paragraph(
                    self._safe(coaching_note),
                    self.styles["sub_bullet"],
                ))
            elif note:
                elements.append(Paragraph(
                    self._safe(note),
                    self.styles["sub_bullet"],
                ))

            if reframe:
                elements.append(Paragraph(
                    f"<b>Suggestion:</b> {self._safe(reframe)}",
                    self.styles["sub_bullet"],
                ))

            elements.append(Spacer(1, 4))
            story.append(KeepTogether(elements))

    def _render_reflections_from_json(self, story: list, data: dict):
        """Render Coaching Reflections from JSON coaching_data."""
        story.append(Paragraph("Coaching Reflections", self.styles["h2"]))

        reflections = data.get("coaching_reflections", [])

        # Handle both list format (new) and dict format (legacy)
        if isinstance(reflections, list):
            for i, question in enumerate(reflections, 1):
                story.append(Paragraph(
                    f"<b>{i}.</b> {self._safe(question)}",
                    self.styles["body"],
                ))
                story.append(Spacer(1, 4))
        elif isinstance(reflections, dict):
            # Legacy dict format with named keys
            for i, key in enumerate([
                "proud_moment_prompt", "reteach_prompt", "next_session_goal_prompt"
            ], 1):
                question = reflections.get(key, "")
                if question:
                    story.append(Paragraph(
                        f"<b>{i}.</b> {self._safe(question)}",
                        self.styles["body"],
                    ))
                    story.append(Spacer(1, 4))

    def _render_next_steps_from_json(self, story: list, data: dict):
        """Render Next Steps from JSON coaching_data."""
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph("Next Steps", self.styles["h2"]))

        next_steps = data.get("next_steps", {})

        # Handle both dict format (new) and legacy action_plan format
        if isinstance(next_steps, dict) and next_steps:
            labels = [
                ("keep_doing", "Keep doing"),
                ("start_doing", "Start doing"),
                ("adjust", "Adjust"),
            ]
            for key, label in labels:
                value = next_steps.get(key, "")
                if value:
                    story.append(Paragraph(
                        f"<b>{self._safe(label)}:</b> {self._safe(value)}",
                        self.styles["bullet"],
                    ))
                    story.append(Spacer(1, 4))

        # Also check for legacy action_plan format
        action_plan = data.get("action_plan", {})
        if action_plan and not next_steps:
            story.append(Paragraph(
                self._safe(action_plan.get("instructions", "")),
                self.styles["body_italic"],
            ))
            for key in ["action_1_label", "action_2_label", "action_3_label"]:
                label = action_plan.get(key, "")
                if label:
                    story.append(Paragraph(
                        f"<b>{self._safe(label)}</b>",
                        self.styles["bullet"],
                    ))
                    story.append(Spacer(1, 4))

    # ------------------------------------------------------------------
    # LEGACY SECTION RENDERERS — Fallback for older evaluation records
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
        """Extract text content between a ## heading and the next ## heading.

        Handles both plain headings ('## Executive Summary') and numbered
        headings ('## Section 1: Executive Summary') so the parser works
        with older and newer report formats. Also handles partial heading
        matches (e.g., 'Next Steps' matches 'Conclusion and Next Steps',
        'Coaching Reflections' matches 'Coaching Reflections for the Instructor',
        'Top 5 Prioritized' matches 'Top 3-5 Prioritized').
        """
        escaped = re.escape(heading)
        # Match optional "Section N: " prefix and allow extra words in the heading
        pattern = rf'##\s+(?:\*\*)?(?:Section\s+\d+:\s*)?(?:[\w\-]+\s+)?{escaped}[\w\s]*(?:\*\*)?\s*\n(.*?)(?=\n##\s|\Z)'
        match = re.search(pattern, markdown, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # Fallback: try a simpler substring match for the heading
        pattern2 = rf'##\s+(?:\*\*)?[^#\n]*{escaped}[^#\n]*(?:\*\*)?\s*\n(.*?)(?=\n##\s|\Z)'
        match2 = re.search(pattern2, markdown, re.DOTALL | re.IGNORECASE)
        return match2.group(1).strip() if match2 else ""

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

"""
PATHS — Decision Support packet PDF generator.

Reuses the same reportlab styles as the interview report so the visual
language of the platform stays consistent.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("dt", parent=base["Title"], fontSize=20, leading=24, spaceAfter=10),
        "h1": ParagraphStyle(
            "dh1", parent=base["Heading2"], fontSize=14, leading=18,
            spaceBefore=12, spaceAfter=6, textColor=colors.HexColor("#1f2937"),
        ),
        "h2": ParagraphStyle(
            "dh2", parent=base["Heading3"], fontSize=12, leading=16,
            spaceBefore=8, spaceAfter=4, textColor=colors.HexColor("#374151"),
        ),
        "body": ParagraphStyle(
            "db", parent=base["BodyText"], fontSize=10, leading=14,
            alignment=TA_LEFT, spaceAfter=4,
        ),
        "small": ParagraphStyle(
            "ds", parent=base["BodyText"], fontSize=9, leading=12,
            textColor=colors.HexColor("#6b7280"),
        ),
        "callout": ParagraphStyle(
            "dc", parent=base["BodyText"], fontSize=10, leading=14,
            textColor=colors.HexColor("#0f766e"),
            backColor=colors.HexColor("#ecfdf5"),
            borderPadding=6, spaceAfter=6,
        ),
        "warn": ParagraphStyle(
            "dw", parent=base["BodyText"], fontSize=10, leading=14,
            textColor=colors.HexColor("#9a3412"),
            backColor=colors.HexColor("#fff7ed"),
            borderPadding=6, spaceAfter=6,
        ),
    }


def _esc(value: Any) -> str:
    s = "—" if value is None or value == "" else str(value)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


def _bullets(items: Iterable[Any]) -> str:
    out = []
    for it in items or []:
        if not it:
            continue
        out.append(f"• {_esc(it)}")
    return "<br/>".join(out) or "—"


def _table(rows: list[tuple[str, Any]]) -> Table:
    data = [[k, _esc(v)] for k, v in rows]
    t = Table(data, colWidths=[1.6 * inch, 4.6 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f4f6")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def build_decision_report_pdf(
    *,
    candidate: dict[str, Any],
    job: dict[str, Any],
    organization: dict[str, Any],
    packet: dict[str, Any],
    development_plan: dict[str, Any] | None = None,
    decision_email: dict[str, Any] | None = None,
    per_stage_breakdown: list[dict[str, Any]] | None = None,
    hr_decision: dict[str, Any] | None = None,
) -> bytes:
    s = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        title=f"PATHS Decision Report — {candidate.get('full_name') or 'Candidate'}",
    )

    story: list[Any] = []
    story.append(Paragraph("PATHS — Decision Support Report", s["title"]))
    story.append(
        Paragraph(
            f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            s["small"],
        )
    )
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#cbd5f5")))
    story.append(Spacer(1, 6))

    idss = packet.get("idss_v2") or {}
    rec = idss.get("recommendation") or packet.get("recommendation") or "—"
    score = idss.get("final_score") or packet.get("final_journey_score")
    confidence = idss.get("confidence")
    story.append(Paragraph("Overview", s["h1"]))
    overview_rows: list[tuple[str, Any]] = [
        ("Candidate", candidate.get("full_name")),
        ("Current title", candidate.get("current_title")),
        ("Job", job.get("title")),
        ("Seniority", job.get("seniority_level")),
        ("Organization", organization.get("name")),
        ("Final score (0–100)", _fmt_score(score)),
        ("Recommendation", rec),
        ("Confidence", confidence),
        ("Recommended next action", idss.get("recommended_next_action")),
        ("Human review required", "Yes" if packet.get("human_review_required") else "No"),
    ]
    story.append(_table(overview_rows))
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            "<b>Decision support only.</b> Final hiring decisions are made by humans — the "
            "Hiring Manager must review the evidence below before acting.",
            s["callout"],
        )
    )

    if idss.get("bias_guardrail_notes"):
        story.append(
            Paragraph(
                "<b>Bias guardrail flags detected.</b> The following human notes were "
                "flagged and require review:<br/>" + _bullets(idss["bias_guardrail_notes"]),
                s["warn"],
            )
        )

    summary_text = idss.get("summary_for_hiring_manager") or packet.get("packet_json", {}).get(
        "executive_summary"
    )
    if summary_text:
        story.append(Paragraph("Summary for Hiring Manager", s["h1"]))
        story.append(Paragraph(_esc(summary_text), s["body"]))

    final_reasoning = idss.get("final_reasoning")
    if final_reasoning:
        story.append(Paragraph("Final reasoning", s["h2"]))
        story.append(Paragraph(_esc(final_reasoning), s["body"]))

    # ── 9-stage rubric ──────────────────────────────────────────────────
    breakdown = idss.get("score_breakdown") or {}
    if breakdown:
        story.append(Paragraph("9-Stage Weighted Rubric", s["h1"]))
        rubric_rows: list[list[str]] = [["Stage", "Weight", "Score", "Weighted", "Reasoning"]]
        for stage, payload in breakdown.items():
            if not isinstance(payload, dict):
                continue
            rubric_rows.append(
                [
                    stage.replace("_", " ").title(),
                    f"{payload.get('weight', '—')}",
                    _fmt_score(payload.get("score")) if not payload.get("missing") else "—",
                    f"{payload.get('weighted_score', 0):.2f}",
                    _esc((payload.get("reasoning") or ""))[:200],
                ]
            )
        rubric_table = Table(
            rubric_rows,
            colWidths=[1.5 * inch, 0.6 * inch, 0.6 * inch, 0.7 * inch, 2.8 * inch],
        )
        rubric_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(rubric_table)

    # ── Per-stage breakdown (this job's custom pipeline) ────────────────
    if per_stage_breakdown:
        story.append(Paragraph("Per-Stage Breakdown", s["h1"]))
        story.append(
            Paragraph(
                "Each stage of this job's hiring pipeline — the candidate's score, "
                "the AI explanation, and the hiring team's notes.",
                s["small"],
            )
        )
        for st in per_stage_breakdown:
            if not isinstance(st, dict):
                continue
            sc = st.get("score")
            sc_txt = f"{_fmt_score(sc)} / 100" if sc is not None else "Not scored yet"
            story.append(
                Paragraph(f"{_esc(st.get('label') or st.get('kind'))} — <b>{sc_txt}</b>", s["h2"])
            )
            if st.get("ai_explanation"):
                story.append(Paragraph(f"<b>AI explanation:</b> {_esc(st['ai_explanation'])}", s["body"]))
            if st.get("hr_notes"):
                story.append(Paragraph(f"<b>HR notes:</b> {_esc(st['hr_notes'])}", s["body"]))
            story.append(Spacer(1, 3))

    for label, key in (
        ("Strengths", "strengths"),
        ("Weaknesses", "weaknesses"),
        ("Risks", "risks"),
        ("Missing evidence", "missing_evidence"),
    ):
        items = idss.get(key)
        if isinstance(items, list) and items:
            story.append(Paragraph(label, s["h2"]))
            story.append(Paragraph(_bullets(items), s["body"]))

    # ── Hiring Manager final decision ───────────────────────────────────
    if hr_decision and hr_decision.get("final_hr_decision"):
        story.append(Paragraph("Hiring Manager Final Decision", s["h1"]))
        decision_label = str(hr_decision["final_hr_decision"]).replace("_", " ").title()
        story.append(Paragraph(f"<b>Decision:</b> {_esc(decision_label)}", s["body"]))
        if hr_decision.get("hr_notes"):
            story.append(Paragraph(f"<b>Notes:</b> {_esc(hr_decision['hr_notes'])}", s["body"]))
        if hr_decision.get("override_reason"):
            story.append(Paragraph(f"<b>Override reason:</b> {_esc(hr_decision['override_reason'])}", s["body"]))

    if development_plan:
        story.append(PageBreak())
        story.append(Paragraph("Development Plan", s["h1"]))
        story.append(
            Paragraph(
                f"Plan type: {_esc(development_plan.get('plan_type'))}",
                s["small"],
            )
        )
        if development_plan.get("executive_summary"):
            story.append(Paragraph(_esc(development_plan["executive_summary"]), s["body"]))
        for label, key in (
            ("Top strengths", "top_strengths"),
            ("Critical gaps", "critical_gaps"),
            ("Strengths to preserve", "strengths_to_preserve"),
            ("Main rejection reasons", "main_rejection_reasons"),
        ):
            items = development_plan.get(key)
            if isinstance(items, list) and items:
                story.append(Paragraph(label, s["h2"]))
                story.append(Paragraph(_bullets(items), s["body"]))
        for window in ("first_30_days", "first_60_days", "first_90_days"):
            block = development_plan.get(window)
            if isinstance(block, dict) and block:
                story.append(
                    Paragraph(window.replace("_", " ").title(), s["h2"]),
                )
                if block.get("focus"):
                    story.append(Paragraph(f"<b>Focus:</b> {_esc(', '.join(map(str, block.get('focus') or [])))}", s["body"]))
                if block.get("tasks"):
                    story.append(Paragraph("Tasks", s["body"]))
                    story.append(Paragraph(_bullets(block.get("tasks")), s["body"]))
                if block.get("success_metrics"):
                    story.append(Paragraph(f"<b>Success metrics:</b> {_esc(', '.join(map(str, block.get('success_metrics') or [])))}", s["body"]))
        if development_plan.get("candidate_facing_message"):
            story.append(Paragraph("Candidate-facing message", s["h2"]))
            story.append(Paragraph(_esc(development_plan["candidate_facing_message"]), s["body"]))

    if decision_email:
        story.append(PageBreak())
        story.append(Paragraph("Email Draft", s["h1"]))
        story.append(Paragraph(f"<b>Subject:</b> {_esc(decision_email.get('subject'))}", s["body"]))
        story.append(Paragraph(_esc(decision_email.get("body")), s["body"]))
        story.append(
            Paragraph(
                f"<i>Status:</i> {_esc(decision_email.get('status'))}",
                s["small"],
            )
        )

    doc.build(story)
    return buf.getvalue()


def _fmt_score(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "—"


__all__ = ["build_decision_report_pdf"]

"""
PATHS Backend — Interview report PDF generator.

Builds a polished, recruiter-friendly PDF directly from the JSON payloads
already persisted by the existing interview pipeline (summary, evaluation,
decision packet) plus the live transcript turns.

Pure ``reportlab`` — no system dependencies. The PDF bytes are returned
in-memory; the caller decides whether to stream them as the response or
also persist them somewhere.
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
    title = ParagraphStyle(
        "PathsTitle",
        parent=base["Title"],
        fontSize=20,
        leading=24,
        spaceAfter=10,
    )
    h1 = ParagraphStyle(
        "PathsH1",
        parent=base["Heading2"],
        fontSize=14,
        leading=18,
        spaceBefore=12,
        spaceAfter=6,
        textColor=colors.HexColor("#1f2937"),
    )
    h2 = ParagraphStyle(
        "PathsH2",
        parent=base["Heading3"],
        fontSize=12,
        leading=16,
        spaceBefore=8,
        spaceAfter=4,
        textColor=colors.HexColor("#374151"),
    )
    body = ParagraphStyle(
        "PathsBody",
        parent=base["BodyText"],
        fontSize=10,
        leading=14,
        alignment=TA_LEFT,
        spaceAfter=4,
    )
    small = ParagraphStyle(
        "PathsSmall",
        parent=base["BodyText"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#6b7280"),
    )
    callout = ParagraphStyle(
        "PathsCallout",
        parent=base["BodyText"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#0f766e"),
        backColor=colors.HexColor("#ecfdf5"),
        borderPadding=6,
        spaceAfter=6,
    )
    return {
        "title": title,
        "h1": h1,
        "h2": h2,
        "body": body,
        "small": small,
        "callout": callout,
    }


def _esc(text: Any) -> str:
    s = str(text or "—")
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


def _humanize(key: Any) -> str:
    return str(key or "").replace("_", " ").strip().title()


def _bullet(items: Iterable[Any]) -> str:
    out: list[str] = []
    for item in items or []:
        if not item:
            continue
        out.append(f"• {_esc(item)}")
    return "<br/>".join(out) or "—"


def _kv_table(rows: list[tuple[str, Any]]) -> Table:
    data = [[k, _esc(v)] for k, v in rows]
    table = Table(data, colWidths=[1.6 * inch, 4.6 * inch])
    table.setStyle(
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
    return table


def build_interview_report_pdf(
    *,
    candidate: dict[str, Any],
    job: dict[str, Any],
    interview: dict[str, Any],
    summary: dict[str, Any] | None,
    evaluations: list[dict[str, Any]],
    decision_packet: dict[str, Any] | None,
    transcript_turns: list[dict[str, Any]] | None = None,
    hr_notes: str | None = None,
    human_decision: dict[str, Any] | None = None,
    transcript_text: str | None = None,
) -> bytes:
    """Render the report and return the PDF bytes."""
    s = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        title=f"PATHS Interview Report — {candidate.get('full_name') or 'Candidate'}",
    )

    story: list[Any] = []
    story.append(Paragraph("PATHS Interview Report", s["title"]))
    story.append(
        Paragraph(
            f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            s["small"],
        )
    )
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#cbd5f5")))
    story.append(Spacer(1, 6))

    # ── Header summary ─────────────────────────────────────────────────
    overall_score = (decision_packet or {}).get("final_score")
    recommendation = (decision_packet or {}).get("recommendation")
    confidence = (decision_packet or {}).get("confidence")
    story.append(Paragraph("Overview", s["h1"]))
    overview_rows: list[tuple[str, Any]] = [
        ("Candidate", candidate.get("full_name") or "—"),
        ("Current title", candidate.get("current_title") or candidate.get("headline") or "—"),
        ("Job", job.get("title") or "—"),
        ("Job seniority", job.get("seniority_level") or "—"),
        ("Interview type", interview.get("interview_type") or "—"),
        ("Status", interview.get("status") or "—"),
        ("Overall score (0–100)", _fmt_score(overall_score)),
        ("Recommendation", recommendation or "needs_human_review"),
        ("Confidence", _fmt_pct(confidence)),
        ("Human review required",
            "Yes" if (decision_packet or {}).get("human_review_required") else "No"),
    ]
    story.append(_kv_table(overview_rows))
    story.append(Spacer(1, 6))

    # ── Disclosure callout ─────────────────────────────────────────────
    story.append(
        Paragraph(
            "<b>Decision support only.</b> This report is generated by the PATHS "
            "Interview Intelligence Agent. Final hiring decisions are made by "
            "humans — HR/managers must review the evidence below before acting.",
            s["callout"],
        )
    )

    # ── Summary ────────────────────────────────────────────────────────
    if summary:
        story.append(Paragraph("Interview Summary", s["h1"]))
        short = summary.get("short_summary")
        for label in (
            "short_summary",
            "summary",
            "candidate_summary",
            "interview_summary",
            "detailed_summary",
            "key_points",
        ):
            value = summary.get(label)
            if isinstance(value, str) and value.strip():
                story.append(Paragraph(_esc(value), s["body"]))
                break
        detailed = summary.get("detailed_summary")
        if (
            isinstance(detailed, str)
            and detailed.strip()
            and detailed.strip() != str(short or "").strip()
        ):
            story.append(Paragraph(_esc(detailed), s["body"]))

        key_answers = summary.get("key_answers")
        if isinstance(key_answers, dict) and key_answers:
            story.append(Paragraph("Key answers", s["h2"]))
            for k, v in key_answers.items():
                if v:
                    story.append(
                        Paragraph(f"<b>{_esc(_humanize(k))}:</b> {_esc(v)}", s["body"]),
                    )

        for label, keys in (
            ("Strengths", ("strengths_observed", "strengths")),
            ("Weaknesses", ("weaknesses_observed", "weaknesses")),
            ("Risks / Red Flags", ("risks",)),
            ("Missing Skills", ("missing_skills",)),
            ("Unclear / Missing Points", ("unclear_or_missing_points",)),
            ("CV Claims Verified", ("candidate_cv_claims_verified",)),
            ("CV Claims Not Verified", ("candidate_cv_claims_not_verified",)),
            ("Notable Quotes / Evidence", ("important_quotes_or_answer_evidence",)),
        ):
            items: Any = None
            for k in keys:
                v = summary.get(k)
                if isinstance(v, list) and v:
                    items = v
                    break
            if items:
                story.append(Paragraph(label, s["h2"]))
                story.append(Paragraph(_bullet(items), s["body"]))

        jra = summary.get("job_requirement_alignment")
        if isinstance(jra, str) and jra.strip():
            story.append(Paragraph("Job Requirement Alignment", s["h2"]))
            story.append(Paragraph(_esc(jra), s["body"]))
        elif isinstance(jra, dict) and jra:
            story.append(Paragraph("Job Requirement Alignment", s["h2"]))
            for k, v in jra.items():
                story.append(
                    Paragraph(f"<b>{_esc(_humanize(k))}:</b> {_esc(v)}", s["body"]),
                )

    # ── Evaluation scorecards ──────────────────────────────────────────
    if evaluations:
        story.append(Paragraph("Evaluation", s["h1"]))
        for i, ev in enumerate(evaluations, start=1):
            title = ev.get("title")
            score = ev.get("score")
            scale = ev.get("score_scale") or 10
            if title:
                head = (
                    f"<b>{_esc(title)}</b>  &nbsp;  "
                    f"<font color='#0f766e'><b>"
                    f"{_fmt_score(score)}{'' if score is None else f'/{int(scale)}'}"
                    f"</b></font>"
                )
            else:
                q = ev.get("question") or ev.get("text") or ev.get("category") or f"Question {i}"
                head = (
                    f"<b>Q{i}.</b> {_esc(q)}  &nbsp;  "
                    f"<font color='#0f766e'><b>{_fmt_score(score)}</b></font>"
                )
            story.append(Paragraph(head, s["h2"]))

            ans = ev.get("answer")
            if isinstance(ans, str) and ans.strip():
                story.append(Paragraph(f"<b>Answer:</b> {_esc(ans)}", s["body"]))
            reasoning = ev.get("reasoning")
            if reasoning:
                story.append(Paragraph(f"<b>Reasoning:</b> {_esc(reasoning)}", s["body"]))

            sub = ev.get("sub_scores")
            if isinstance(sub, dict) and sub:
                parts = ", ".join(f"{_humanize(k)} {v}/10" for k, v in sub.items())
                story.append(Paragraph(f"<b>Sub-scores:</b> {_esc(parts)}", s["body"]))
            skills = ev.get("skill_scores")
            if isinstance(skills, dict) and skills:
                parts = ", ".join(f"{_humanize(k)} {v}/10" for k, v in skills.items())
                story.append(Paragraph(f"<b>Skill scores:</b> {_esc(parts)}", s["body"]))

            evidence = ev.get("evidence")
            if isinstance(evidence, list) and evidence:
                story.append(
                    Paragraph(
                        f"<b>Evidence:</b> {_esc('; '.join(str(x) for x in evidence))}",
                        s["body"],
                    )
                )
            elif isinstance(evidence, str) and evidence.strip():
                story.append(Paragraph(f"<b>Evidence:</b> {_esc(evidence)}", s["body"]))

            for label, key in (
                ("Skills tested", "skills_tested"),
                ("Strengths", "strengths"),
                ("Weaknesses", "weaknesses"),
                ("Risks", "risks"),
                ("Development needs", "development_needs"),
            ):
                items = ev.get(key)
                if isinstance(items, list) and items:
                    story.append(
                        Paragraph(
                            f"<b>{label}:</b> {_esc(', '.join(str(x) for x in items))}",
                            s["body"],
                        )
                    )
            rec = ev.get("recommendation")
            if isinstance(rec, str) and rec.strip():
                story.append(Paragraph(f"<b>Recommendation:</b> {_esc(rec)}", s["body"]))

    # ── Recommendation + dev plan ──────────────────────────────────────
    dp = decision_packet or {}
    if dp:
        story.append(Paragraph("Recommendation & Next Steps", s["h1"]))
        story.append(
            Paragraph(
                f"<b>Recommendation:</b> {_esc(dp.get('recommendation') or 'needs_human_review')}",
                s["body"],
            )
        )
        if dp.get("rationale"):
            story.append(
                Paragraph(f"<b>Rationale:</b> {_esc(dp['rationale'])}", s["body"]),
            )
        plan = dp.get("development_plan") or (summary or {}).get("development_plan")
        if isinstance(plan, list) and plan:
            story.append(Paragraph("Development plan", s["h2"]))
            story.append(Paragraph(_bullet(plan), s["body"]))
        rejection = dp.get("rejection_feedback") or (summary or {}).get("rejection_feedback")
        if isinstance(rejection, str) and rejection.strip():
            story.append(Paragraph("Rejection feedback (draft)", s["h2"]))
            story.append(Paragraph(_esc(rejection), s["body"]))

    # ── HR notes (free text captured by the interviewer) ───────────────
    if isinstance(hr_notes, str) and hr_notes.strip():
        story.append(Paragraph("Interviewer Notes", s["h1"]))
        for line in hr_notes.strip().splitlines():
            if line.strip():
                story.append(Paragraph(_esc(line.strip()), s["body"]))

    # ── Human hiring decision ──────────────────────────────────────────
    hd = human_decision or {}
    if hd.get("final_decision"):
        story.append(Paragraph("HR Decision", s["h1"]))
        label = str(hd.get("final_decision")).replace("_", " ").title()
        story.append(Paragraph(f"<b>Decision:</b> {_esc(label)}", s["body"]))
        if hd.get("decided_by"):
            story.append(Paragraph(f"<b>Decided by:</b> {_esc(str(hd['decided_by']))}", s["body"]))
        if hd.get("hr_notes"):
            story.append(Paragraph(f"<b>Rationale:</b> {_esc(str(hd['hr_notes']))}", s["body"]))

    # ── Transcript appendix ────────────────────────────────────────────
    if transcript_turns:
        story.append(PageBreak())
        story.append(Paragraph("Transcript Appendix", s["h1"]))
        for t in transcript_turns:
            idx = t.get("index")
            q = t.get("question") or "—"
            a = t.get("answer") or "—"
            marker = " (follow-up)" if t.get("is_followup") else ""
            story.append(Paragraph(f"<b>Q{idx}{marker}.</b> {_esc(q)}", s["body"]))
            story.append(Paragraph(f"<i>Answer:</i> {_esc(a)}", s["body"]))
            story.append(Spacer(1, 4))
    elif isinstance(transcript_text, str) and transcript_text.strip():
        # Real-meeting recordings have no Q/A turns — render the flat
        # transcript text so the PDF still carries the conversation.
        story.append(PageBreak())
        story.append(Paragraph("Transcript Appendix", s["h1"]))
        for line in transcript_text.strip().splitlines():
            line = line.strip()
            if line:
                story.append(Paragraph(_esc(line), s["body"]))

    doc.build(story)
    return buf.getvalue()


def _fmt_score(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "—"


def _fmt_pct(value: Any) -> str:
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    if v <= 1:
        v *= 100
    return f"{v:.0f}%"


__all__ = ["build_interview_report_pdf"]

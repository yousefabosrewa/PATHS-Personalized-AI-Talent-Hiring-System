"""
PATHS Backend — Per-stage decision breakdown.

For the decision page + PDF, build one row per stage in the *job's own custom
pipeline* (the stages the recruiter chose when creating the job), each carrying:

  • score            — the candidate's concrete result at that stage
  • ai_explanation   — the IDSS agent's reasoning for that stage (reused; no new
                        LLM call) with a sensible fallback from the source data
  • hr_notes         — the human note captured at that stage (interview notes)
  • status           — done | pending

Sources, by stage kind:
  screening                         → CandidateJobScore.final_score
  assessment                        → latest graded Assessment attempt (% )
  technical/hr/mixed interview      → latest InterviewDecisionPacket.final_score
                                      + the matching Interview.hr_notes
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.assessment import Assessment
from app.db.models.interview import Interview, InterviewDecisionPacket
from app.db.models.job import Job
from app.db.models.scoring import CandidateJobScore
from app.services.hiring_pipeline import pipeline_for_job

# Map a custom-pipeline stage kind → the IDSS rubric key whose reasoning best
# explains it, so we can reuse the already-generated AI explanation.
_IDSS_KEY_FOR_KIND: dict[str, str] = {
    "screening": "cv_profile_fit",
    "assessment": "assessment",
    "technical_interview": "technical_interview",
    "hr_interview": "hr_interview",
    "mixed_interview": "technical_interview",
}

_INTERVIEW_KINDS = {"technical_interview", "hr_interview", "mixed_interview"}
_KIND_TO_ITYPE = {
    "technical_interview": "technical",
    "hr_interview": "hr",
    "mixed_interview": "mixed",
}


def _num(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def build_per_stage_breakdown(db: Session, packet: Any) -> list[dict[str, Any]]:
    """Return one breakdown row per stage of the job's custom pipeline."""
    job = db.get(Job, packet.job_id) if packet.job_id else None
    if job is None:
        return []

    idss = (packet.packet_json or {}).get("idss_v2") or {}
    breakdown = idss.get("score_breakdown") if isinstance(idss, dict) else {}
    breakdown = breakdown if isinstance(breakdown, dict) else {}

    def _reasoning(idss_key: str | None) -> str:
        if not idss_key:
            return ""
        node = breakdown.get(idss_key)
        if isinstance(node, dict):
            return str(node.get("reasoning") or "").strip()
        return ""

    rows: list[dict[str, Any]] = []
    for s in pipeline_for_job(job):
        kind = s["kind"]
        row: dict[str, Any] = {
            "key": s["key"],
            "kind": kind,
            "label": s["label"],
            "score": None,
            "ai_explanation": _reasoning(_IDSS_KEY_FOR_KIND.get(kind)),
            "hr_notes": "",
            "status": "pending",
        }

        if kind == "screening":
            cjs = db.execute(
                select(CandidateJobScore)
                .where(
                    CandidateJobScore.candidate_id == packet.candidate_id,
                    CandidateJobScore.job_id == packet.job_id,
                )
                .order_by(CandidateJobScore.updated_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            sc = _num(getattr(cjs, "final_score", None)) if cjs else None
            if sc is not None:
                row["score"] = round(sc, 1)
                row["status"] = "done"
                if not row["ai_explanation"]:
                    row["ai_explanation"] = (
                        getattr(cjs, "rationale", None)
                        or getattr(cjs, "reasoning", None)
                        or getattr(cjs, "explanation", None)
                        or "CV / profile fit scored against the job's required skills."
                    )

        elif kind == "assessment":
            att = db.execute(
                select(Assessment)
                .where(
                    Assessment.candidate_id == packet.candidate_id,
                    Assessment.job_id == packet.job_id,
                    Assessment.application_id.is_not(None),
                )
                .order_by(Assessment.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            pct = _num(getattr(att, "score_percent", None)) if att else None
            if pct is not None:
                row["score"] = round(pct, 1)
                row["status"] = "done"
                meta = att.agent_metadata if isinstance(getattr(att, "agent_metadata", None), dict) else {}
                if not row["ai_explanation"]:
                    row["ai_explanation"] = (
                        meta.get("summary") or att.reviewer_notes
                        or "Graded skills assessment result."
                    )

        elif kind in _INTERVIEW_KINDS:
            dp = db.execute(
                select(InterviewDecisionPacket)
                .where(
                    InterviewDecisionPacket.candidate_id == packet.candidate_id,
                    InterviewDecisionPacket.job_id == packet.job_id,
                )
                .order_by(InterviewDecisionPacket.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            fs = _num(getattr(dp, "final_score", None)) if dp else None
            if fs is not None:
                row["score"] = round(fs, 1)
                row["status"] = "done"
                if not row["ai_explanation"]:
                    dpj = dp.decision_packet_json if isinstance(dp.decision_packet_json, dict) else {}
                    ev = dpj.get("evidence_summary")
                    if isinstance(ev, list) and ev:
                        row["ai_explanation"] = "; ".join(
                            str(x.get("claim") if isinstance(x, dict) else x) for x in ev[:3]
                        )
                    else:
                        row["ai_explanation"] = str(dp.recommendation or "Interview evaluation.")
            # HR notes from the matching interview (fall back to any interview).
            itype = _KIND_TO_ITYPE.get(kind)
            iv = db.execute(
                select(Interview)
                .where(
                    Interview.candidate_id == packet.candidate_id,
                    Interview.job_id == packet.job_id,
                    Interview.interview_type == itype,
                )
                .order_by(Interview.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if iv is None:
                iv = db.execute(
                    select(Interview)
                    .where(
                        Interview.candidate_id == packet.candidate_id,
                        Interview.job_id == packet.job_id,
                    )
                    .order_by(Interview.created_at.desc())
                    .limit(1)
                ).scalar_one_or_none()
            if iv is not None and (iv.hr_notes or "").strip():
                row["hr_notes"] = iv.hr_notes.strip()

        rows.append(row)
    return rows

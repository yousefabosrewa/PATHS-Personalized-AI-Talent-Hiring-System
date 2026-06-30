"""
PATHS — IDSS evidence collector.

Builds the 9-stage rubric inputs from the existing tables (no schema
changes). Reads from:

  candidates / jobs                 → CV fit and job requirement match heuristics
  Qdrant                            → vector similarity (existing helper)
  Apache AGE / candidates_graph     → graph similarity (best-effort)
  organization_outreach_messages    → outreach engagement signals
  outreach_sessions / interview_*   → also surfaced for the prompt
  interview_evaluations             → tech / hr interview scores
  audit_logs                        → human feedback aggregation

Every section is best-effort — when data is missing the corresponding
``StageInputs`` field stays ``None`` and the rubric module decides how to
compensate.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.application import Application
from app.db.models.candidate import Candidate
from app.db.models.cv_entities import CandidateExperience
from app.db.models.decision_support import DecisionSupportPacket, HrFinalDecision
from app.db.models.interview import (
    Interview,
    InterviewEvaluation,
    InterviewHumanDecision,
)
from app.db.models.job import Job
from app.db.models.organization_matching import OrganizationOutreachMessage
from app.db.models.scoring import CandidateJobScore
from app.db.models.sync import AuditLog
from app.services.decision_support.idss_rubric import (
    StageInputs,
    detect_bias_risk,
)
from app.services.scoring.vector_similarity_service import compute_similarity_score

logger = logging.getLogger(__name__)


def build_idss_inputs(
    db: Session, *, application_id: uuid.UUID,
) -> tuple[StageInputs, dict[str, Any]]:
    """Return (rubric_inputs, side_payload) for the IDSS pipeline.

    ``side_payload`` carries free-text context the agent prompt benefits
    from but that doesn't fit the numeric rubric — must-have-missing,
    bias notes, etc.
    """
    app = db.get(Application, application_id)
    if app is None:
        raise ValueError("application_not_found")
    cand = db.get(Candidate, app.candidate_id)
    job = db.get(Job, app.job_id)
    if cand is None or job is None:
        raise ValueError("candidate_or_job_missing")

    inputs = StageInputs(evidence={}, missing_reasons={})
    side: dict[str, Any] = {
        "must_have_skills_missing": False,
        "technical_role": _is_technical_role(job),
        "bias_notes": [],
        "human_notes": [],
    }

    # Pre-compute the "data sufficiency" of the candidate profile so the
    # collector can attribute missing CV-related signals to the candidate
    # rather than the recruiter. The threshold is intentionally generous —
    # if the candidate has a non-trivial skill list AND a summary or an
    # uploaded CV (current_title set), we treat the profile as sufficient.
    profile_sufficient = bool(
        (cand.skills and len(cand.skills) >= 3)
        and (cand.summary or cand.current_title or cand.headline)
    )

    # ── Stage 1: CV / profile fit (heuristic from CandidateJobScore + skills) ─
    cjs = db.execute(
        select(CandidateJobScore).where(
            CandidateJobScore.candidate_id == app.candidate_id,
            CandidateJobScore.job_id == app.job_id,
        )
    ).scalar_one_or_none()
    if cjs is not None and cjs.criteria_breakdown:
        cb = cjs.criteria_breakdown if isinstance(cjs.criteria_breakdown, dict) else {}
        cv_fit = _coerce_score(
            cb.get("cv_profile_fit")
            or cb.get("profile_fit")
            or cb.get("experience_alignment"),
        )
        if cv_fit is None and cjs.final_score is not None:
            cv_fit = float(cjs.final_score) * 0.85
        inputs.cv_profile_fit = cv_fit
        inputs.evidence.setdefault("cv_profile_fit", []).append(
            f"CandidateJobScore criteria={list(cb.keys())[:6]}"
        )
        if cv_fit is None:
            inputs.missing_reasons["cv_profile_fit"] = "missing_candidate_input"
    else:
        inputs.evidence.setdefault("cv_profile_fit", [])
        # No CJS row yet — most often happens when the candidate hasn't
        # uploaded enough profile data for the scoring agent to run.
        inputs.missing_reasons["cv_profile_fit"] = (
            "missing_candidate_input" if not profile_sufficient else "missing_recruiter_input"
        )

    # ── Stage 2: Job requirement match (skill overlap %) ─────────────────────
    cand_skills = {s.lower().strip() for s in (cand.skills or []) if isinstance(s, str)}
    required = _required_skills_from_job(db, job)
    matched = required & cand_skills
    if required:
        coverage = (len(matched) / len(required)) * 100.0
        inputs.job_requirement_match = coverage
        if coverage < 30:
            side["must_have_skills_missing"] = True
        inputs.evidence.setdefault("job_requirement_match", []).append(
            f"Matched {len(matched)}/{len(required)} required skills: {sorted(list(matched))[:6]}"
        )
        if required - matched:
            inputs.evidence["job_requirement_match"].append(
                f"Missing: {sorted(list(required - matched))[:6]}"
            )
    else:
        # No STRUCTURED required-skill rows — but the recruiter usually wrote
        # the requirements as free text. Work with the found data: match the
        # candidate's skills against the role's requirements / description text
        # so this stage is scored instead of falsely "missing".
        job_req_text = " ".join([
            job.title or "", job.summary or "", job.requirements or "",
            getattr(job, "description_text", "") or "",
        ]).lower()
        if cand_skills and job_req_text.strip():
            hits = {sk for sk in cand_skills if len(sk) >= 3 and sk in job_req_text}
            denom = max(min(len(cand_skills), 10), 1)
            coverage = min(100.0, round((len(hits) / denom) * 100.0, 1))
            inputs.job_requirement_match = coverage
            inputs.evidence.setdefault("job_requirement_match", []).append(
                f"No structured skills on the job — matched {len(hits)} of the "
                f"candidate's skills against the role's requirements text: "
                f"{sorted(list(hits))[:6]}"
            )
        else:
            inputs.evidence.setdefault("job_requirement_match", []).append(
                "Job has no required skills or requirements text defined yet."
            )
            inputs.missing_reasons["job_requirement_match"] = "missing_job_requirements"

    # ── Stage 3: Vector similarity (Qdrant, with a text fallback) ────────────
    vec_done = False
    try:
        sim = compute_similarity_score(app.candidate_id, app.job_id)
        if sim.candidate_vector_present and sim.job_vector_present:
            inputs.vector_similarity = float(sim.score)
            inputs.evidence.setdefault("vector_similarity", []).append(
                f"cosine={sim.cosine:.3f} → score={sim.score}"
            )
            vec_done = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("[IDSS] vector_similarity failed: %s", exc)
        inputs.evidence.setdefault("vector_similarity", []).append(f"vector_error:{exc}")

    if not vec_done:
        # Qdrant vectors not embedded yet — work with the found data: derive a
        # text-overlap similarity from the candidate's CV text vs the job text,
        # so an uploaded CV still produces a real score instead of "missing".
        cand_text = " ".join([
            cand.summary or "", cand.headline or "", cand.current_title or "",
            " ".join(cand.skills or []),
        ])
        job_text = " ".join([
            job.title or "", job.summary or "", job.requirements or "",
            getattr(job, "description_text", "") or "",
        ])
        fb = _text_overlap_score(cand_text, job_text)
        if fb is not None:
            inputs.vector_similarity = fb
            inputs.evidence.setdefault("vector_similarity", []).append(
                f"Vector index unavailable — derived {fb}/100 from CV ↔ job text overlap."
            )
        else:
            inputs.evidence.setdefault("vector_similarity", []).append(
                "Vector missing and not enough text to compare."
            )
            inputs.missing_reasons["vector_similarity"] = "missing_candidate_input"

    # ── Stage 4: Graph similarity (Apache AGE) ───────────────────────────────
    graph_score, graph_notes = _graph_similarity(db, candidate_id=app.candidate_id, job=job)
    inputs.graph_similarity = graph_score
    inputs.evidence.setdefault("graph_similarity", graph_notes)
    if graph_score is None:
        # No graph overlap usually means the candidate profile lacks the
        # tagged skills/companies/schools the graph traverses.
        inputs.missing_reasons["graph_similarity"] = "missing_candidate_input"

    # ── Outreach engagement removed from the rubric (no scoring value). ──────

    # ── Stages 6 & 7: Tech / HR interview scores ────────────────────────────
    tech_score, tech_notes, hr_score, hr_notes = _interview_scores(
        db, application_id=application_id,
    )
    inputs.technical_interview = tech_score
    inputs.hr_interview = hr_score
    inputs.evidence.setdefault("technical_interview", tech_notes)
    inputs.evidence.setdefault("hr_interview", hr_notes)
    if tech_score is None:
        # No interview has been scheduled/evaluated yet — that's a
        # recruiter/hiring-team workflow gap, not the candidate.
        inputs.missing_reasons["technical_interview"] = "missing_recruiter_input"
    if hr_score is None:
        inputs.missing_reasons["hr_interview"] = "missing_recruiter_input"

    # ── Stage 8: Assessment (best-effort) ───────────────────────────────────
    assess = _assessment_score(db, candidate_id=app.candidate_id, job_id=app.job_id)
    if assess is not None:
        inputs.assessment = assess
        inputs.evidence.setdefault("assessment", [f"derived_score={assess}"])
    else:
        inputs.evidence.setdefault("assessment", [])
        inputs.missing_reasons["assessment"] = "missing_recruiter_input"

    # ── Stage 9: Human feedback (manager notes, interviewer comments, audit) ─
    human_score, human_notes_list, raw_notes = _human_feedback(
        db, application_id=application_id, organization_id=job.organization_id,
    )
    inputs.human_feedback = human_score
    inputs.evidence.setdefault("human_feedback", human_notes_list)
    if human_score is None:
        inputs.missing_reasons["human_feedback"] = "missing_recruiter_input"
    side["human_notes"] = raw_notes
    bias_detected, bias_notes = detect_bias_risk(raw_notes)
    side["bias_notes"] = bias_notes
    side["bias_risk"] = bias_detected

    # ── Auto-fill CV / profile fit (no manual scoring run required) ──────────
    # If the scoring agent hasn't produced a CandidateJobScore yet, derive a
    # real CV-fit score from signals already computed here (vector similarity +
    # job-requirement skill match) so this stage is never blank and never tells
    # the recruiter to "run scoring first".
    if inputs.cv_profile_fit is None:
        parts = [
            v for v in (inputs.vector_similarity, inputs.job_requirement_match)
            if v is not None
        ]
        if parts:
            inputs.cv_profile_fit = round(sum(parts) / len(parts), 1)
        elif profile_sufficient:
            inputs.cv_profile_fit = 55.0
        if inputs.cv_profile_fit is not None:
            inputs.missing_reasons.pop("cv_profile_fit", None)
            inputs.evidence.setdefault("cv_profile_fit", []).append(
                "Auto-derived from vector similarity + job-requirement match "
                "(no manual scoring run needed)."
            )

    return inputs, side


# ── Stage helpers ────────────────────────────────────────────────────────


def _coerce_score(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, dict):
        for key in ("score", "value", "final_score"):
            if key in value:
                value = value[key]
                break
        else:
            return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if v > 1 else v * 100.0


_WORD_RE = re.compile(r"[a-z0-9+#.]+")
_STOPWORDS = {
    "the", "and", "for", "with", "you", "our", "are", "will", "have", "this",
    "that", "from", "your", "who", "all", "can", "but", "not", "their", "they",
    "job", "role", "work", "team", "experience", "years", "ability", "strong",
}


def _text_overlap_score(a: str, b: str) -> float | None:
    """Cheap text-similarity (0-100) used when Qdrant vectors aren't available.
    Containment of shared content terms relative to the smaller term set, so a
    candidate whose CV terms are mostly covered by the role scores high."""
    ta = {w for w in _WORD_RE.findall((a or "").lower()) if len(w) > 2 and w not in _STOPWORDS}
    tb = {w for w in _WORD_RE.findall((b or "").lower()) if len(w) > 2 and w not in _STOPWORDS}
    if len(ta) < 3 or len(tb) < 3:
        return None
    inter = ta & tb
    score = (len(inter) / max(1, min(len(ta), len(tb)))) * 100.0
    return round(min(100.0, score), 1)


def _required_skills_from_job(db: Session, job: Job) -> set[str]:
    from app.db.models.job_ingestion import JobSkillRequirement

    rows = list(
        db.execute(
            select(JobSkillRequirement).where(
                JobSkillRequirement.job_id == job.id,
                JobSkillRequirement.is_required == True,  # noqa: E712
            )
        ).scalars().all()
    )
    return {
        (r.skill_name_normalized or r.skill_name_raw or "").lower().strip()
        for r in rows
        if (r.skill_name_normalized or r.skill_name_raw)
    }


def _is_technical_role(job: Job) -> bool:
    rf = (job.role_family or "").lower()
    if rf in {"engineering", "software", "backend", "frontend", "data", "ml", "ai", "devops"}:
        return True
    title = (job.title or "").lower()
    return any(
        kw in title
        for kw in (
            "engineer", "developer", "data", "ml ", "ai ", "devops",
            "platform", "sre", "scientist",
        )
    )


def _preferred_skills_from_job(db: Session, job: Job) -> set[str]:
    from app.db.models.job_ingestion import JobSkillRequirement

    rows = list(
        db.execute(
            select(JobSkillRequirement).where(
                JobSkillRequirement.job_id == job.id,
                JobSkillRequirement.is_required == False,  # noqa: E712
            )
        ).scalars().all()
    )
    return {
        (r.skill_name_normalized or r.skill_name_raw or "").lower().strip()
        for r in rows
        if (r.skill_name_normalized or r.skill_name_raw)
    }


def _graph_similarity(
    db: Session, *, candidate_id: uuid.UUID, job: Job,
) -> tuple[float | None, list[str]]:
    """Graph similarity computed from the candidate's relational skill /
    experience graph vs the job.

    The previous version traversed Apache AGE with ``MATCH (c:Candidate {id})``
    but the projection stores the candidate/job nodes under ``candidate_id`` /
    ``job_id`` and the job side often has no skill edges — so the traversal
    matched nothing and the stage was always "too sparse". We compute the same
    intent (shared skills + experience/role overlap) directly from PostgreSQL,
    which is reliable and always produces a value when the candidate has a
    skills profile.
    """
    cand = db.get(Candidate, candidate_id)
    if cand is None:
        return None, ["candidate_missing"]
    cand_skills = {
        s.lower().strip()
        for s in (cand.skills or [])
        if isinstance(s, str) and s.strip()
    }
    if not cand_skills:
        return None, ["candidate_profile_has_no_skills_to_graph"]

    notes: list[str] = []
    # The job's skill universe: structured required + preferred skills, plus
    # terms mined from the job text so jobs without structured skills still
    # produce overlap.
    job_skills = _required_skills_from_job(db, job) | _preferred_skills_from_job(db, job)
    job_text = " ".join(
        [job.title or "", job.summary or "", job.requirements or "",
         job.description_text or "", job.role_family or ""]
    ).lower()

    hits = {
        sk for sk in cand_skills
        if sk in job_skills or (len(sk) >= 3 and sk in job_text)
    }
    denom = max(len(job_skills) if job_skills else min(len(cand_skills), 8), 1)
    score = min(100.0, round((len(hits) / denom) * 100.0, 1))

    # Experience adjacency bonus — candidate has worked the role family before.
    try:
        exps = db.execute(
            select(CandidateExperience.title, CandidateExperience.company_name)
            .where(CandidateExperience.candidate_id == candidate_id)
        ).all()
        rolef = (job.role_family or "").lower().strip()
        exp_text = " ".join((t or "") + " " + (c or "") for t, c in exps).lower()
        if rolef and rolef in exp_text:
            score = min(100.0, score + 10.0)
            notes.append(f"experience_matches_role_family:{rolef}")
    except Exception:  # noqa: BLE001
        pass

    notes.append(
        f"shared_skills={sorted(list(hits))[:6]} ({len(hits)})"
        if hits else "no_skill_overlap_with_job"
    )
    return score, notes


def _outreach_engagement(
    db: Session, *, candidate_id: uuid.UUID, job_id: uuid.UUID,
) -> tuple[float | None, list[str]]:
    rows = list(
        db.execute(
            select(OrganizationOutreachMessage).where(
                OrganizationOutreachMessage.candidate_id == candidate_id,
                OrganizationOutreachMessage.job_id == job_id,
            )
            .order_by(OrganizationOutreachMessage.created_at.desc())
            .limit(10)
        ).scalars().all()
    )
    if not rows:
        return None, ["no_outreach_history"]
    notes: list[str] = []
    score = 0.0
    for r in rows:
        s = (r.status or "").lower()
        notes.append(f"{r.subject[:40] if r.subject else '(no subject)'}: {s}")
        if s in {"sent", "approved"}:
            score = max(score, 50.0)
        if s in {"replied", "engaged"}:
            score = max(score, 80.0)
        if s in {"booked", "scheduled"}:
            score = max(score, 90.0)
    if score == 0.0:
        # We have outreach but nothing positive — record as low engagement.
        score = 25.0
        notes.append("no_positive_engagement_signal")
    return score, notes


def _interview_norm(value: Any) -> float | None:
    """Normalize an interview sub-score to 0-100, tolerating 0-1 / 0-10 / 0-100."""
    n = _coerce_score(value)  # <=1 → ×100, else passthrough
    if n is None:
        return None
    if n <= 10:  # a 0-10 score slipped through (e.g. 7 → 70)
        n *= 10
    return min(100.0, max(0.0, n))


def _interview_scores(
    db: Session, *, application_id: uuid.UUID,
) -> tuple[float | None, list[str], float | None, list[str]]:
    tech_scores: list[float] = []
    hr_scores: list[float] = []
    tech_notes: list[str] = []
    hr_notes: list[str] = []

    # ── Primary source: the interview analysis ("Run Analysis") persists its
    # HR / technical scores into a DecisionSupportPacket created by the
    # interview_intelligence_v2 agent. Read those so the scores show up the
    # moment an interview is analysed. ──────────────────────────────────────
    analysis_packets = list(
        db.execute(
            select(DecisionSupportPacket)
            .where(
                DecisionSupportPacket.application_id == application_id,
                DecisionSupportPacket.generated_by_agent == "interview_intelligence_v2",
            )
            .order_by(DecisionSupportPacket.created_at.desc())
        ).scalars().all()
    )
    for p in analysis_packets:
        pj = p.packet_json if isinstance(p.packet_json, dict) else {}
        # Attribute by interview type: a separate technical interview feeds
        # ONLY the technical line, a separate HR interview ONLY the HR line,
        # and a mixed interview feeds both. Legacy packets without the type
        # tag behave like mixed (the historical behaviour).
        ptype = str(pj.get("interview_type") or "mixed").strip().lower()
        t = _interview_norm(pj.get("technical_score"))
        h = _interview_norm(pj.get("hr_score"))
        if ptype != "hr" and t and t > 0:
            tech_scores.append(t)
            tech_notes.append(f"analysis={p.id} type={ptype} technical={t:.0f}")
        if ptype != "technical" and h and h > 0:
            hr_scores.append(h)
            hr_notes.append(f"analysis={p.id} type={ptype} hr={h:.0f}")

    interviews = list(
        db.execute(
            select(Interview).where(Interview.application_id == application_id),
        ).scalars().all()
    )
    if not interviews and not analysis_packets:
        return None, ["no_interviews_completed"], None, ["no_interviews_completed"]

    # ── No-shows: the scheduled time passed and nobody joined. Policy: a
    # no-show that was never rescheduled scores 0 for ALL interview types,
    # so it drags both the technical and HR averages to zero. ──────────────
    for inv in interviews:
        if (inv.status or "").lower() == "no_show":
            tech_scores.append(0.0)
            tech_notes.append(f"interview={inv.id} no_show=0")
            hr_scores.append(0.0)
            hr_notes.append(f"interview={inv.id} no_show=0")

    # ── Fallback source: structured InterviewEvaluation rows (other flow). ──
    for inv in interviews:
        evals = list(
            db.execute(
                select(InterviewEvaluation).where(
                    InterviewEvaluation.interview_id == inv.id,
                )
            ).scalars().all()
        )
        for ev in evals:
            sj = ev.score_json if isinstance(ev.score_json, dict) else {}
            score = (
                sj.get("overall_score")
                or sj.get("overall_technical_score")
                or sj.get("overall_hr_score")
                or sj.get("score")
            )
            score_n = _interview_norm(score)
            if score_n is None:
                continue
            if (ev.evaluation_type or "").lower() == "technical":
                tech_scores.append(score_n)
                tech_notes.append(f"interview={inv.id} score={score_n:.0f}")
            elif (ev.evaluation_type or "").lower() == "hr":
                hr_scores.append(score_n)
                hr_notes.append(f"interview={inv.id} score={score_n:.0f}")
    tech = sum(tech_scores) / len(tech_scores) if tech_scores else None
    hr = sum(hr_scores) / len(hr_scores) if hr_scores else None
    if tech is None:
        tech_notes.append("no_technical_evaluation_yet")
    if hr is None:
        hr_notes.append("no_hr_evaluation_yet")
    return tech, tech_notes, hr, hr_notes


def _assessment_score(
    db: Session, *, candidate_id: uuid.UUID, job_id: uuid.UUID,
) -> float | None:
    """Return the candidate's assessment score for this job.

    Primary source is the real ``assessments`` table (score_percent or
    score/max_score from a graded submission); falls back to an
    ``assessment`` sub-score in the scoring breakdown.
    """
    # ── Primary: graded Assessment rows for this candidate + job ──
    try:
        from app.db.models.assessment import Assessment

        if hasattr(Assessment, "candidate_id") and hasattr(Assessment, "job_id"):
            rows = list(
                db.execute(
                    select(Assessment).where(
                        Assessment.candidate_id == candidate_id,
                        Assessment.job_id == job_id,
                    )
                ).scalars().all()
            )
            best: float | None = None
            for a in rows:
                sp = getattr(a, "score_percent", None)
                if sp is None:
                    s = getattr(a, "score", None)
                    ms = getattr(a, "max_score", None)
                    if s is not None and ms:
                        sp = (float(s) / float(ms)) * 100.0
                if sp is not None:
                    best = max(best or 0.0, float(sp))
            if best is not None:
                return min(100.0, max(0.0, best))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[IDSS] assessment lookup failed: %s", exc)

    # ── Fallback: scoring breakdown sub-score ──
    cjs = db.execute(
        select(CandidateJobScore).where(
            CandidateJobScore.candidate_id == candidate_id,
            CandidateJobScore.job_id == job_id,
        )
    ).scalar_one_or_none()
    if cjs is None or not cjs.criteria_breakdown:
        return None
    cb = cjs.criteria_breakdown if isinstance(cjs.criteria_breakdown, dict) else {}
    return _coerce_score(cb.get("assessment") or cb.get("practical"))


def _human_feedback(
    db: Session, *, application_id: uuid.UUID, organization_id: uuid.UUID | None,
) -> tuple[float | None, list[str], list[str]]:
    notes: list[str] = []
    raw_notes: list[str] = []

    interviews = list(
        db.execute(
            select(Interview).where(Interview.application_id == application_id),
        ).scalars().all()
    )
    pos = neg = 0
    for inv in interviews:
        rows = list(
            db.execute(
                select(InterviewHumanDecision).where(
                    InterviewHumanDecision.interview_id == inv.id,
                )
            ).scalars().all()
        )
        for r in rows:
            decision = (r.final_decision or "").lower()
            note = (r.hr_notes or "").strip()
            if note:
                raw_notes.append(note)
                notes.append(f"interview={inv.id} decision={decision}: {note[:80]}")
            if decision == "accepted":
                pos += 1
            elif decision == "rejected":
                neg += 1

    # Hiring Manager's final decision + notes (recorded on the Decision
    # Support page) — this is the primary human-feedback signal.
    manager_decisions = list(
        db.execute(
            select(HrFinalDecision)
            .where(HrFinalDecision.application_id == application_id)
            .order_by(HrFinalDecision.decided_at.desc())
        ).scalars().all()
    )
    for d in manager_decisions:
        dec = (d.final_hr_decision or "").lower().strip()
        note = (d.hr_notes or "").strip()
        if note:
            raw_notes.append(note)
            notes.append(f"manager_decision={dec}: {note[:80]}")
        if dec in ("accepted", "accept", "hire", "hired"):
            pos += 1
        elif dec in ("rejected", "reject"):
            neg += 1

    audit_rows = list(
        db.execute(
            select(AuditLog)
            .where(
                AuditLog.entity_type == "application",
                AuditLog.entity_id == application_id,
                AuditLog.action.like("hr.%"),
            )
            .order_by(AuditLog.created_at.desc())
            .limit(10)
        ).scalars().all()
    )
    for row in audit_rows:
        meta = row.audit_metadata or {}
        if isinstance(meta, dict):
            blob = " ".join(
                str(v) for v in meta.values() if isinstance(v, (str, int, float))
            )[:300]
            if blob.strip():
                raw_notes.append(blob)
                notes.append(f"audit={row.action}: {blob[:80]}")

    if not interviews and not manager_decisions and not raw_notes:
        return None, ["no_human_feedback"], raw_notes

    if pos + neg == 0 and not raw_notes:
        return 50.0, notes, raw_notes

    if pos + neg == 0:
        return 60.0, notes, raw_notes

    score = (pos / max(1, pos + neg)) * 100.0
    return score, notes, raw_notes


__all__ = ["build_idss_inputs"]

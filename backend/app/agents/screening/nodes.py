"""
PATHS Backend — Screening Agent LangGraph node functions.

Each node receives and returns a `ScreeningState` dict. The pipeline:

    discover_candidates → score_candidates → rank_and_persist

Reuses the existing scoring infrastructure:
- `organization_candidate_search_service` for DB candidate discovery
- `llama_scoring_agent` + `vector_similarity_service` for scoring
- `scoring_prompt_builder` for anonymization
- `scoring_criteria` for classification
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.agents.screening.state import ScreeningState
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.db.models.bias_fairness import BiasAuditLog, BiasFlag
from app.db.models.bias_reports import BiasReport
from app.db.models.candidate import Candidate
from app.db.models.fairness_rubric import FairnessRubric
from app.db.models.screening import ScreeningResult, ScreeningRun
from app.services.scoring.llama_scoring_agent import (
    AgentScoreError,
    score_candidate_for_job,
)
from app.services.scoring.relevance_filter_service import (
    assess_relevance,
    candidate_role_family,
)
from app.services.scoring.scoring_criteria import (
    classify_final_score,
    recommendation_for,
)
from app.services.scoring.scoring_prompt_builder import (
    anonymize_candidate,
    anonymize_job,
)
from app.services.scoring.scoring_service import combine_scores
from app.services.scoring.vector_similarity_service import compute_similarity_score

logger = logging.getLogger(__name__)
settings = get_settings()

# Letters for blind labels: Candidate A, Candidate B, …, Candidate Z, Candidate AA, …
_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _blind_label(index: int) -> str:
    """Generate a blind label like 'Candidate A', 'Candidate B', ..., 'Candidate AA'."""
    if index < 26:
        return f"Candidate {_ALPHABET[index]}"
    first = _ALPHABET[(index // 26) - 1]
    second = _ALPHABET[index % 26]
    return f"Candidate {first}{second}"


# ── Node 1: Discover candidates ─────────────────────────────────────────


def _deterministic_scored_entry(
    *,
    cand_id_str: str,
    decision: Any,
    sim_score: float,
    anon_c: dict[str, Any],
    anon_j: dict[str, Any],
    agent_weight: float,
    vector_weight: float,
    reason: str,
) -> dict[str, Any]:
    """Deterministic score for one candidate when the LLM rationale is
    unavailable (e.g. the provider returns 429). The screening tab's promise is
    "deterministic scoring · LLM provides rationale only", so a rate-limited LLM
    must NOT drop the candidate — we score from skill overlap + vector match.
    """
    cand_skills = {
        str(s.get("name") or "").strip().lower()
        for s in (anon_c.get("skills") or [])
        if isinstance(s, dict) and s.get("name")
    }
    cand_skills.discard("")
    req = [str(x).strip() for x in (anon_j.get("skills_required") or []) if str(x).strip()]
    pref = [str(x).strip() for x in (anon_j.get("skills_preferred") or []) if str(x).strip()]
    matched = [r for r in req if r.lower() in cand_skills]
    missing_req = [r for r in req if r.lower() not in cand_skills]
    missing_pref = [p for p in pref if p.lower() not in cand_skills]

    overlap = float(getattr(decision, "skill_overlap_ratio", 0.0) or 0.0)
    relevance = float(getattr(decision, "relevance_score", 0.0) or 0.0)
    det_agent = round(100.0 * (0.6 * overlap + 0.4 * relevance), 1)
    final = combine_scores(
        det_agent, sim_score, agent_weight=agent_weight, vector_weight=vector_weight,
    )
    return {
        "candidate_id": cand_id_str,
        "agent_score": float(det_agent),
        "vector_similarity_score": float(sim_score),
        "final_score": float(final),
        "relevance_score": relevance,
        "recommendation": recommendation_for(final),
        "match_classification": classify_final_score(final),
        "criteria_breakdown": {
            "skill_overlap": round(overlap * 100, 1),
            "vector_similarity": round(float(sim_score), 1),
            "method": "deterministic_fallback",
        },
        "matched_skills": matched,
        "missing_required_skills": missing_req,
        "missing_preferred_skills": missing_pref,
        "strengths": [f"Matches required skill: {m}" for m in matched[:5]],
        "weaknesses": [f"Missing required skill: {m}" for m in missing_req[:5]],
        "explanation": (
            "Scored deterministically from skill overlap and semantic similarity. "
            f"AI rationale was unavailable ({reason})."
        ),
    }


def discover_candidates(state: ScreeningState) -> dict[str, Any]:
    """Find relevant candidates for the job from the database or CSV import."""
    source = state.get("source", "database")
    job_id = UUID(state["job_id"])

    if source == "csv_upload":
        # CSV path — candidate IDs are already provided
        csv_ids = state.get("csv_candidate_ids") or []
        candidate_ids = csv_ids
        total_scanned = len(csv_ids)
        passed_filter = len(csv_ids)
        logger.info(
            "[ScreeningAgent] CSV source: %d candidates provided", len(csv_ids),
        )
    else:
        # Database path — use the existing Qdrant + PG discovery
        from app.services.organization_matching.organization_candidate_search_service import (
            discover_candidates_for_job,
        )

        db: Session = SessionLocal()
        try:
            cand_uuids, stats = discover_candidates_for_job(
                db, job_id, max_pool=settings.org_matching_max_candidates_per_run,
            )
            candidate_ids = [str(c) for c in cand_uuids]
            total_scanned = stats.get("pg_scanned", 0)
            passed_filter = stats.get("passed_filter", 0)
        finally:
            db.close()

        logger.info(
            "[ScreeningAgent] DB discovery: scanned=%d, passed=%d",
            total_scanned, passed_filter,
        )

    return {
        "discovered_candidate_ids": candidate_ids,
        "total_scanned": total_scanned,
        "passed_filter": passed_filter,
    }


# ── Node 2: Score candidates ────────────────────────────────────────────


async def score_candidates(state: ScreeningState) -> dict[str, Any]:
    """Score each discovered candidate against the job using LLM + vector."""
    job_id = UUID(state["job_id"])
    candidate_ids = state.get("discovered_candidate_ids") or []
    force = state.get("force_rescore", False)

    from app.db.repositories import scoring_repository as repo

    scored: list[dict[str, Any]] = []
    failed = 0

    # Load job profile once
    db: Session = SessionLocal()
    try:
        job_profile = repo.get_job_profile(db, job_id)
    finally:
        db.close()

    if job_profile is None:
        logger.error("[ScreeningAgent] job %s not found", job_id)
        return {
            "scored_candidates": [],
            "scored_count": 0,
            "failed_count": 0,
            "status": "failed",
            "error": f"Job {job_id} not found in database",
        }

    a_w = float(settings.scoring_agent_weight)
    v_w = float(settings.scoring_vector_weight)

    async with httpx.AsyncClient(
        timeout=settings.scoring_request_timeout_seconds,
    ) as client:
        for cand_id_str in candidate_ids:
            cand_id = UUID(cand_id_str)

            # Load candidate profile
            cs: Session = SessionLocal()
            try:
                cand_profile = repo.get_candidate_profile(cs, cand_id)
            finally:
                cs.close()

            if cand_profile is None:
                failed += 1
                logger.debug("[ScreeningAgent] candidate %s not found", cand_id)
                continue

            try:
                # Vector similarity
                sim = compute_similarity_score(cand_id, job_id)

                # Relevance check
                cand_family = candidate_role_family(cand_profile)
                decision = assess_relevance(
                    cand_profile,
                    job_profile,
                    candidate_family=cand_family,
                    vector_similarity_score=sim.score,
                )
                if not decision.is_relevant and not force:
                    continue

                # Anonymize and score
                anon_c = anonymize_candidate(cand_profile, candidate_id=cand_id_str)
                anon_j = anonymize_job(job_profile, job_id=str(job_id))

                outcome = await score_candidate_for_job(
                    anonymized_candidate=anon_c,
                    anonymized_job=anon_j,
                    client=client,
                )

                if isinstance(outcome, AgentScoreError):
                    # LLM unavailable / rate-limited → keep the candidate with a
                    # deterministic score instead of dropping them entirely.
                    logger.warning(
                        "[ScreeningAgent] agent error for %s: %s — scoring deterministically",
                        cand_id, outcome.error_message,
                    )
                    scored.append(
                        _deterministic_scored_entry(
                            cand_id_str=cand_id_str,
                            decision=decision,
                            sim_score=sim.score,
                            anon_c=anon_c,
                            anon_j=anon_j,
                            agent_weight=a_w,
                            vector_weight=v_w,
                            reason="AI model rate-limited or unavailable",
                        )
                    )
                    continue

                final = combine_scores(
                    outcome.agent_score, sim.score,
                    agent_weight=a_w, vector_weight=v_w,
                )

                scored.append({
                    "candidate_id": cand_id_str,
                    "agent_score": float(outcome.agent_score),
                    "vector_similarity_score": float(sim.score),
                    "final_score": float(final),
                    "relevance_score": float(decision.relevance_score),
                    "recommendation": outcome.recommendation
                    or recommendation_for(final),
                    "match_classification": classify_final_score(final),
                    "criteria_breakdown": outcome.criteria_breakdown,
                    "matched_skills": outcome.matched_skills,
                    "missing_required_skills": outcome.missing_required_skills,
                    "missing_preferred_skills": outcome.missing_preferred_skills,
                    "strengths": outcome.strengths,
                    "weaknesses": outcome.weaknesses,
                    "explanation": outcome.explanation,
                })

            except Exception as exc:  # noqa: BLE001
                failed += 1
                logger.exception(
                    "[ScreeningAgent] unexpected error scoring %s", cand_id,
                )

    logger.info(
        "[ScreeningAgent] scoring complete: scored=%d, failed=%d",
        len(scored), failed,
    )

    return {
        "scored_candidates": scored,
        "scored_count": len(scored),
        "failed_count": failed,
    }


# ── Node 3: Rank and persist ────────────────────────────────────────────


def rank_and_persist(state: ScreeningState) -> dict[str, Any]:
    """Sort by final_score, assign ranks, persist ScreeningRun + ScreeningResults."""
    scored = state.get("scored_candidates") or []
    top_k = state.get("top_k", 10)
    job_id = state["job_id"]
    org_id = state["organization_id"]
    source = state.get("source", "database")
    run_id = state.get("screening_run_id")

    # Sort descending by final_score
    scored.sort(key=lambda x: x["final_score"], reverse=True)

    db: Session = SessionLocal()
    try:
        # Update the screening run
        if run_id:
            run = db.get(ScreeningRun, UUID(run_id))
            if run:
                run.status = "completed"
                run.total_candidates_scanned = state.get("total_scanned", 0)
                run.candidates_passed_filter = state.get("passed_filter", 0)
                run.candidates_scored = state.get("scored_count", 0)
                run.candidates_failed = state.get("failed_count", 0)
                run.finished_at = datetime.now(timezone.utc)
                db.add(run)

        # Create screening results
        ranked_results: list[dict[str, Any]] = []
        for i, sc in enumerate(scored):
            rank = i + 1
            is_shortlisted = rank <= top_k
            label = _blind_label(i)

            result = ScreeningResult(
                screening_run_id=UUID(run_id) if run_id else None,
                candidate_id=UUID(sc["candidate_id"]),
                job_id=UUID(job_id),
                blind_label=label,
                rank_position=rank,
                agent_score=sc["agent_score"],
                vector_similarity_score=sc["vector_similarity_score"],
                final_score=sc["final_score"],
                relevance_score=sc.get("relevance_score"),
                recommendation=sc.get("recommendation"),
                match_classification=sc.get("match_classification"),
                criteria_breakdown=sc.get("criteria_breakdown"),
                matched_skills=sc.get("matched_skills"),
                missing_required_skills=sc.get("missing_required_skills"),
                missing_preferred_skills=sc.get("missing_preferred_skills"),
                strengths=sc.get("strengths"),
                weaknesses=sc.get("weaknesses"),
                explanation=sc.get("explanation"),
                status="shortlisted" if is_shortlisted else "ranked",
            )
            db.add(result)
            db.flush()

            ranked_results.append({
                "result_id": str(result.id),
                "blind_label": label,
                "rank_position": rank,
                "agent_score": sc["agent_score"],
                "vector_similarity_score": sc["vector_similarity_score"],
                "final_score": sc["final_score"],
                "relevance_score": sc.get("relevance_score"),
                "recommendation": sc.get("recommendation"),
                "match_classification": sc.get("match_classification"),
                "status": result.status,
            })

        db.commit()
        logger.info(
            "[ScreeningAgent] persisted %d results (top_k=%d shortlisted)",
            len(ranked_results), min(top_k, len(ranked_results)),
        )

    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("[ScreeningAgent] failed to persist results")
        return {
            "ranked_results": [],
            "status": "failed",
            "error": str(exc),
        }
    finally:
        db.close()

    return {
        "ranked_results": ranked_results,
        "status": "completed",
        "error": None,
    }


# -- Node 4: Bias Guardrail (Phase 2.1) -------------------------------------


def _years_exp_bucket(years: int | None) -> str:
    """Map years_experience to an age-proxy bucket label."""
    if years is None:
        return "unknown"
    if years <= 2:
        return "0-2 yrs"
    if years <= 5:
        return "3-5 yrs"
    if years <= 10:
        return "6-10 yrs"
    return "10+ yrs"


# Maps rubric attribute names to a callable (Candidate -> group_label string).
# Attributes with no stored demographic data map to None -- those will be
# recorded as "no_data" entries in the bias_reports table so there is an
# audit trail showing the check was attempted.
_ATTR_GETTERS: dict[str, Any] = {
    "gender":          None,   # not stored (privacy-preserving design)
    "race_ethnicity":  None,   # not stored
    "age":             lambda c: _years_exp_bucket(c.years_experience),  # proxy
    "disability":      None,   # not stored
    "veteran_status":  None,   # not stored
}


def bias_guardrail_node(state: ScreeningState) -> dict[str, Any]:
    """Phase 2.1 -- Bias Guardrail.

    After rank_and_persist, loads the job's FairnessRubric and checks each
    enabled protected attribute:

    * If a candidate field exists as a proxy  -> compute selection rates per
      group and the disparate-impact ratio against the highest-rate group.
    * If no candidate field maps to the attribute -> write a ``__no_data__``
      BiasReport entry so the audit trail shows the check was attempted.

    Persists rows to ``bias_reports``, raises ``BiasFlag`` entries for groups
    below threshold, and appends to ``bias_audit_log``.

    Returns ``bias_report`` (list of metric dicts) and ``bias_flags_raised``
    (list of "attr:group" strings) into the pipeline state.

    This node is a no-op when no enabled rubric exists for the job.
    """
    job_id_str = state["job_id"]
    org_id_str = state["organization_id"]
    run_id_str = state.get("screening_run_id")

    db: Session = SessionLocal()
    try:
        # ------------------------------------------------------------------ #
        # 1. Load the fairness rubric
        # ------------------------------------------------------------------ #
        rubric: FairnessRubric | None = (
            db.query(FairnessRubric)
            .filter(FairnessRubric.job_id == UUID(job_id_str))
            .first()
        )

        if rubric is None or not rubric.enabled:
            logger.info(
                "[BiasGuardrail] No active rubric for job %s -- skipping", job_id_str,
            )
            return {"bias_report": [], "bias_flags_raised": []}

        threshold: float = rubric.disparate_impact_threshold
        enabled_attrs: dict[str, bool] = rubric.protected_attrs or {}

        # ------------------------------------------------------------------ #
        # 2. Load all ScreeningResults for this run
        # ------------------------------------------------------------------ #
        if not run_id_str:
            logger.warning("[BiasGuardrail] No screening_run_id in state -- skipping")
            return {"bias_report": [], "bias_flags_raised": []}

        results: list[ScreeningResult] = (
            db.query(ScreeningResult)
            .filter(ScreeningResult.screening_run_id == UUID(run_id_str))
            .all()
        )

        if not results:
            return {"bias_report": [], "bias_flags_raised": []}

        # ------------------------------------------------------------------ #
        # 3. Build candidate map
        # ------------------------------------------------------------------ #
        candidate_ids = [r.candidate_id for r in results]
        candidates_map: dict[UUID, Candidate] = {
            c.id: c
            for c in db.query(Candidate)
            .filter(Candidate.id.in_(candidate_ids))
            .all()
        }

        # ------------------------------------------------------------------ #
        # 4. Per-attribute disparity computation
        # ------------------------------------------------------------------ #
        bias_report_entries: list[dict[str, Any]] = []
        flags_raised: list[str] = []

        for attr_name, is_enabled in enabled_attrs.items():
            if not is_enabled:
                continue

            getter = _ATTR_GETTERS.get(attr_name)

            if getter is None:
                # Attribute has no stored demographic data -- write audit entry
                logger.info(
                    "[BiasGuardrail] attr=%s has no candidate field; "
                    "writing no-data entry", attr_name,
                )
                db.add(BiasReport(
                    screening_run_id=UUID(run_id_str),
                    organization_id=UUID(org_id_str),
                    job_id=UUID(job_id_str),
                    attribute_name=attr_name,
                    group_label="__no_data__",
                    selection_count=0,
                    total_count=0,
                    selection_rate=0.0,
                    disparate_impact_ratio=None,
                    threshold=threshold,
                    passed=True,
                ))
                continue

            # Group results by attribute value --------------------------------
            groups: dict[str, dict[str, int]] = {}
            for result in results:
                cand = candidates_map.get(result.candidate_id)
                if cand is None:
                    continue
                label = getter(cand)
                if label not in groups:
                    groups[label] = {"total": 0, "selected": 0}
                groups[label]["total"] += 1
                if result.status == "shortlisted":
                    groups[label]["selected"] += 1

            if not groups:
                continue

            # Compute per-group selection rates
            rates: dict[str, float] = {
                lbl: (g["selected"] / g["total"]) if g["total"] > 0 else 0.0
                for lbl, g in groups.items()
            }
            reference_rate = max(rates.values(), default=0.0)
            reference_label = max(rates, key=lambda k: rates[k]) if rates else None

            # Persist BiasReport rows + raise flags ---------------------------
            for label, g in groups.items():
                rate = rates[label]
                is_reference = (label == reference_label)
                dir_ratio: float | None = (
                    None
                    if is_reference or reference_rate == 0
                    else rate / reference_rate
                )
                passed = is_reference or (dir_ratio is None) or (dir_ratio >= threshold)

                db.add(BiasReport(
                    screening_run_id=UUID(run_id_str),
                    organization_id=UUID(org_id_str),
                    job_id=UUID(job_id_str),
                    attribute_name=attr_name,
                    group_label=label,
                    selection_count=g["selected"],
                    total_count=g["total"],
                    selection_rate=rate,
                    disparate_impact_ratio=dir_ratio,
                    threshold=threshold,
                    passed=passed,
                ))

                bias_report_entries.append({
                    "attribute_name": attr_name,
                    "group_label": label,
                    "selection_count": g["selected"],
                    "total_count": g["total"],
                    "selection_rate": rate,
                    "disparate_impact_ratio": dir_ratio,
                    "threshold": threshold,
                    "passed": passed,
                })

                if not passed:
                    flag_key = f"{attr_name}:{label}"
                    flags_raised.append(flag_key)
                    db.add(BiasFlag(
                        org_id=UUID(org_id_str),
                        scope="screening_run",
                        scope_id=run_id_str,
                        rule="disparate_impact",
                        severity="high",
                        status="open",
                        detail={
                            "attribute": attr_name,
                            "group": label,
                            "selection_rate": rate,
                            "reference_group": reference_label,
                            "reference_rate": reference_rate,
                            "disparate_impact_ratio": dir_ratio,
                            "threshold": threshold,
                        },
                    ))
                    logger.warning(
                        "[BiasGuardrail] FLAG: attr=%s group=%s DIR=%.3f < threshold=%.2f",
                        attr_name, label, dir_ratio, threshold,
                    )

        # ------------------------------------------------------------------ #
        # 5. Write to BiasAuditLog
        # ------------------------------------------------------------------ #
        db.add(BiasAuditLog(
            org_id=org_id_str,
            event_type="bias_flag_raised" if flags_raised else "screening_bias_check_passed",
            job_id=job_id_str,
            detail_json={
                "screening_run_id": run_id_str,
                "flags_raised": flags_raised,
                "attributes_checked": [a for a, v in enabled_attrs.items() if v],
                "total_results": len(results),
            },
        ))

        db.commit()
        logger.info(
            "[BiasGuardrail] job=%s run=%s: %d groups checked, %d flags raised",
            job_id_str, run_id_str, len(bias_report_entries), len(flags_raised),
        )

    except Exception:
        db.rollback()
        logger.exception("[BiasGuardrail] failed for job %s", job_id_str)
        # Non-fatal: return empty report rather than failing the whole pipeline
        return {"bias_report": [], "bias_flags_raised": []}
    finally:
        db.close()

    return {
        "bias_report": bias_report_entries,
        "bias_flags_raised": flags_raised,
    }

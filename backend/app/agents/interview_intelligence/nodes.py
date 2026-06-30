"""LLM nodes for the interview intelligence pipeline.

Node order (Phase 2.2):
    transcript_capture_node          -- load transcript + context from DB,
                                        upsert to Qdrant for future RAG
    -> node_summarize                -- LLM: produce structured summary
    -> node_hr_evaluation            -- LLM + RAG: HR scorecard
    -> node_technical_evaluation     -- LLM + RAG: technical scorecard
    -> node_compliance               -- LLM: bias/legal guardrail
    -> node_decision_support         -- LLM + DB persist: decision packet
                                        + DevelopmentPlan row
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any
from uuid import UUID

from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.services.llm.openrouter_client import (
    OpenRouterClientError,
    generate_json_response,
)
from app.services.organization_matching.organization_llm_provider import (
    LLMProviderError,
    get_provider,
)

logger = get_logger(__name__)

# Qdrant collection that stores past-interview embeddings for RAG retrieval.
_INTERVIEW_COLLECTION = "interview_transcripts"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_json_object(text: str) -> dict[str, Any]:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    try:
        out = json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}\s*$", t)
        if not m:
            raise ValueError("no JSON object in model output")
        out = json.loads(m.group(0))
    if not isinstance(out, dict):
        raise ValueError("model JSON was not an object")
    return out


async def _llm_json(system: str, user: str) -> dict[str, Any]:
    """Run an LLM JSON call for interview analysis.

    Primary path: the OpenRouter client's free-model fallback chain — when a
    free model is rate-limited (429) it transparently falls through to the
    other configured free models (OPENROUTER_FREE_FALLBACK_MODELS), so the
    whole analysis stays on the free tier instead of failing on the first 429.

    ``generate_json_response`` is synchronous (httpx.Client) so it runs in a
    worker thread to avoid blocking the event loop. If the entire free-model
    chain is exhausted, we fall back once to the original org LLM provider.
    """
    # Free OpenRouter models share one upstream quota, so when it's hit every
    # model in the chain returns 429 at once and switching models can't help —
    # only waiting does. Retry the whole chain a few times with backoff so a
    # transient free-tier rate limit recovers instead of failing the run.
    last_exc: OpenRouterClientError | None = None
    backoffs = (6.0, 12.0, 20.0)
    for attempt in range(len(backoffs) + 1):
        try:
            return await asyncio.to_thread(
                generate_json_response,
                system,
                user,
                temperature=0.2,
                max_tokens=4000,
            )
        except OpenRouterClientError as exc:
            last_exc = exc
            if attempt < len(backoffs):
                wait = backoffs[attempt]
                logger.warning(
                    "[InterviewAnalysis] free-model chain rate-limited (%s) — "
                    "retrying in %.0fs (attempt %d/%d)",
                    exc, wait, attempt + 1, len(backoffs),
                )
                await asyncio.sleep(wait)
                continue
            logger.warning(
                "[InterviewAnalysis] OpenRouter free-model chain exhausted after "
                "%d attempts (%s) — falling back to the org LLM provider",
                len(backoffs) + 1, exc,
            )

    prov = get_provider()
    try:
        text = await prov.generate_text(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )
    except LLMProviderError as exc:
        logger.exception("LLM call failed (both providers): %s", exc)
        raise
    return _extract_json_object(text)


# Keep the old name for backward compat in tests
async def llm_json(system: str, user: str) -> dict[str, Any]:
    return await _llm_json(system, user)


def _rag_retrieve(org_id: str, query_text: str, limit: int = 3) -> list[dict[str, Any]]:
    """Retrieve similar past interview summaries from Qdrant.

    Returns an empty list if Qdrant is unavailable or the collection
    doesn't exist yet -- RAG is always best-effort / non-fatal.
    """
    try:
        from app.services.embedding_service import embed_query
        from app.services.qdrant_service import QdrantService

        q_vec = embed_query(query_text[:4096])
        svc = QdrantService()
        hits = svc.search_vectors(
            collection_name=_INTERVIEW_COLLECTION,
            query_vector=q_vec,
            limit=limit,
            filters={"organization_id": org_id},
        )
        return [h["payload"] for h in hits if h.get("payload")]
    except Exception:  # noqa: BLE001
        logger.debug("[InterviewRAG] retrieval skipped (Qdrant unavailable)", exc_info=True)
        return []


def _rag_upsert(
    interview_id: str,
    org_id: str,
    job_id: str,
    interview_type: str,
    text_to_embed: str,
    payload: dict[str, Any],
) -> None:
    """Upsert one interview summary into the Qdrant collection.

    Non-fatal: errors are logged at DEBUG level.
    """
    try:
        from app.services.embedding_service import embed_documents
        from app.services.qdrant_service import QdrantService

        svc = QdrantService()
        # Ensure collection exists (uses CV collection vector size setting)
        from app.core.config import get_settings
        settings = get_settings()
        try:
            svc.client.get_collection(_INTERVIEW_COLLECTION)
        except Exception:
            from qdrant_client.models import Distance, VectorParams
            svc.client.create_collection(
                collection_name=_INTERVIEW_COLLECTION,
                vectors_config=VectorParams(
                    size=settings.qdrant_collection_vector_size,
                    distance=Distance.COSINE,
                ),
            )

        vecs = embed_documents([text_to_embed[:4096]])
        svc.upsert_vectors(
            collection_name=_INTERVIEW_COLLECTION,
            vectors=vecs,
            payloads=[payload],
            ids=[interview_id],
        )
    except Exception:  # noqa: BLE001
        logger.debug("[InterviewRAG] upsert skipped", exc_info=True)


# ---------------------------------------------------------------------------
# Node 0: Transcript capture (Phase 2.2)
# ---------------------------------------------------------------------------

def transcript_capture_node(state: dict[str, Any]) -> dict[str, Any]:
    """Load the interview transcript and all related context from the database.

    Populates: transcript, transcript_quality, interview_type,
                job_context, candidate_context, application_context,
                question_packs, job_match_score.

    Also upserts the transcript text to Qdrant so future runs can use it
    for RAG retrieval.
    """
    interview_id_str = state.get("interview_id")
    if not interview_id_str:
        logger.warning("[TranscriptCapture] No interview_id in state")
        return {"transcript": "", "transcript_quality": "low", "interview_type": "mixed"}

    from app.db.models.application import Application
    from app.db.models.candidate import Candidate
    from app.db.models.interview import Interview, InterviewTranscript
    from app.db.models.job import Job

    db = SessionLocal()
    try:
        interview: Interview | None = db.get(Interview, UUID(interview_id_str))
        if interview is None:
            logger.error("[TranscriptCapture] Interview %s not found", interview_id_str)
            return {"transcript": "", "transcript_quality": "low", "interview_type": "mixed",
                    "error": f"Interview {interview_id_str} not found"}

        # Transcript (most recent)
        transcript_row: InterviewTranscript | None = (
            db.query(InterviewTranscript)
            .filter(InterviewTranscript.interview_id == interview.id)
            .order_by(InterviewTranscript.created_at.desc())
            .first()
        )
        transcript_text = transcript_row.transcript_text if transcript_row else ""
        quality = (transcript_row.quality_hint or "medium") if transcript_row else "low"

        # INST.md §10 — fold HR Notes into the evidence the agent analyses.
        # Kept clearly delimited so the model treats it as recruiter
        # observations, not interview dialogue.
        hr_notes = (getattr(interview, "hr_notes", None) or "").strip()
        if hr_notes and transcript_text:
            transcript_text = (
                f"{transcript_text}\n\n"
                "=== HR NOTES (recruiter observations, not interview dialogue) ===\n"
                f"{hr_notes}"
            )

        # Application context
        app_row: Application | None = db.get(Application, interview.application_id)
        application_context: dict[str, Any] = {}
        if app_row:
            application_context = {
                "id": str(app_row.id),
                "job_id": str(app_row.job_id),
                "candidate_id": str(app_row.candidate_id),
                # Application has no ``status`` column — it's ``overall_status``
                # (plus current_stage_code / pipeline_stage). Reading ``status``
                # raised AttributeError and crashed the whole analysis run.
                "status": getattr(app_row, "overall_status", None),
                "current_stage_code": getattr(app_row, "current_stage_code", None),
                "pipeline_stage": getattr(app_row, "pipeline_stage", None),
            }

        # Job context
        job_row: Job | None = db.get(Job, interview.job_id)
        job_context: dict[str, Any] = {}
        if job_row:
            job_context = {
                "id": str(job_row.id),
                "title": job_row.title,
                # The Job column is ``description_text`` (not ``description``);
                # also surface the explicit requirements so analysis is
                # grounded in the role (INST.md §10/§16).
                "description": getattr(job_row, "description_text", None)
                or getattr(job_row, "description", None),
                "requirements": getattr(job_row, "requirements", None),
                "summary": getattr(job_row, "summary", None),
                "employment_type": getattr(job_row, "employment_type", None),
                "seniority_level": getattr(job_row, "seniority_level", None),
            }

        # Candidate context (anonymized — no PII)
        cand_row: Candidate | None = db.get(Candidate, interview.candidate_id)
        candidate_context: dict[str, Any] = {}
        if cand_row:
            candidate_context = {
                "id": str(cand_row.id),
                "current_title": cand_row.current_title,
                "career_level": cand_row.career_level,
                "years_experience": cand_row.years_experience,
                "skills": cand_row.skills or [],
                "headline": cand_row.headline,
                # Intentionally omit: name, email, phone, location (PII)
            }

        # Question packs
        question_packs = [
            {
                "type": qp.question_pack_type,
                "questions": qp.questions_json,
            }
            for qp in (interview.question_packs or [])
        ]

    finally:
        db.close()

    # Upsert to Qdrant for future RAG (best-effort)
    if transcript_text:
        snippet = (transcript_text[:300] + "...") if len(transcript_text) > 300 else transcript_text
        _rag_upsert(
            interview_id=interview_id_str,
            org_id=state.get("organization_id", ""),
            job_id=str(interview.job_id),
            interview_type=interview.interview_type,
            text_to_embed=transcript_text[:4096],
            payload={
                "interview_id": interview_id_str,
                "organization_id": state.get("organization_id", ""),
                "job_id": str(interview.job_id),
                "interview_type": interview.interview_type,
                "transcript_snippet": snippet,
                "quality": quality,
            },
        )

    logger.info(
        "[TranscriptCapture] interview=%s type=%s transcript_len=%d",
        interview_id_str, interview.interview_type, len(transcript_text),
    )

    return {
        "transcript": transcript_text,
        "transcript_quality": quality,
        "interview_type": interview.interview_type,
        "job_context": job_context,
        "candidate_context": candidate_context,
        "application_context": application_context,
        "question_packs": question_packs,
        "rag_context": [],
    }


# ---------------------------------------------------------------------------
# Node 1: Summarize transcript
# ---------------------------------------------------------------------------

async def node_summarize(state: dict[str, Any]) -> dict[str, Any]:
    tr = (state.get("transcript") or "").strip()
    job = state.get("job_context") or {}
    cand = state.get("candidate_context") or {}
    packs = state.get("question_packs") or []
    system = (
        "You are a careful interview analyst. Do not invent facts. "
        "If the transcript lacks evidence, write exactly: 'Not enough evidence in transcript.' "
        "Return ONLY valid JSON with keys: short_summary, detailed_summary, key_answers, "
        "strengths_observed, weaknesses_observed, unclear_or_missing_points, job_requirement_alignment, "
        "candidate_cv_claims_verified, candidate_cv_claims_not_verified, important_quotes_or_answer_evidence."
    )
    user = json.dumps(
        {
            "job": job,
            "candidate": cand,
            "question_packs": packs,
            "transcript": tr[:80000],
        },
        default=str,
    )
    if len(tr) < 80:
        return {
            "interview_summary": {
                "short_summary": "Not enough evidence in transcript.",
                "detailed_summary": "Not enough evidence in transcript.",
                "strengths_observed": [],
                "weaknesses_observed": [],
                "unclear_or_missing_points": ["Transcript too short or empty."],
            }
        }
    out = await _llm_json(system, user)
    return {"interview_summary": out}


# ---------------------------------------------------------------------------
# Node 2: HR Evaluation (+ RAG, Phase 2.2)
# ---------------------------------------------------------------------------

async def node_hr_evaluation(state: dict[str, Any]) -> dict[str, Any]:
    summary = state.get("interview_summary") or {}
    org_id = state.get("organization_id", "")

    # RAG: retrieve similar past HR outcomes for calibration context
    short_summary = summary.get("short_summary", "")
    rag_hits = _rag_retrieve(org_id, short_summary, limit=3) if short_summary else []
    rag_context_text = ""
    if rag_hits:
        snippets = [
            f"Past interview ({h.get('interview_type','?')}): {h.get('transcript_snippet','')}"
            for h in rag_hits
        ]
        rag_context_text = "\n\n".join(snippets)

    system = (
        "You are an HR evaluator. Be fair, job-related, and avoid protected attributes. "
        "Output ONLY JSON: communication_score, motivation_score, culture_alignment_score, "
        "role_understanding_score, teamwork_score, ownership_score, adaptability_score, overall_hr_score, "
        "strengths, weaknesses, risks, development_needs, evidence, "
        "recommendation_from_hr_perspective (a short sentence — recommendation, not a hiring decision)"
    )
    user_payload: dict[str, Any] = {
        "summary": summary,
        "transcript": (state.get("transcript") or "")[:80000],
    }
    if rag_context_text:
        user_payload["rag_similar_past_interviews"] = rag_context_text

    out = await _llm_json(system, json.dumps(user_payload, default=str))
    return {"hr_scorecard": out, "rag_context": rag_hits}


# ---------------------------------------------------------------------------
# Node 3: Technical Evaluation (+ RAG, Phase 2.2)
# ---------------------------------------------------------------------------

async def node_technical_evaluation(state: dict[str, Any]) -> dict[str, Any]:
    job = state.get("job_context") or {}
    summary = state.get("interview_summary") or {}
    org_id = state.get("organization_id", "")
    itype = (state.get("interview_type") or "mixed").lower()

    if itype == "hr":
        return {
            "technical_scorecard": {
                "skill_scores": {},
                "overall_technical_score": None,
                "strongest_skills": [],
                "weakest_skills": [],
                "evidence": "No technical interview in this event.",
            }
        }

    # RAG: retrieve similar past technical evaluations for skill benchmarking
    job_title = job.get("title", "")
    rag_query = f"technical interview {job_title} {summary.get('short_summary','')}"
    rag_hits = _rag_retrieve(org_id, rag_query.strip(), limit=3)
    rag_context_text = ""
    if rag_hits:
        snippets = [
            f"Past technical interview ({h.get('interview_type','?')}): {h.get('transcript_snippet','')}"
            for h in rag_hits
        ]
        rag_context_text = "\n\n".join(snippets)

    system = (
        "You are a technical evaluator. Map answers to job skills; compare to CV. "
        "Output ONLY JSON: skill_scores (object skill->1-5), strongest_skills, weakest_skills, "
        "verified_cv_claims, unverified_cv_claims, incorrect_or_weak_answers, "
        "practical_task_result_if_any, overall_technical_score, evidence, "
        "recommendation_from_technical_perspective"
    )
    user_payload: dict[str, Any] = {
        "job": job,
        "summary": summary,
        "transcript": (state.get("transcript") or "")[:80000],
    }
    if rag_context_text:
        user_payload["rag_similar_past_technical_interviews"] = rag_context_text

    out = await _llm_json(system, json.dumps(user_payload, default=str))
    return {"technical_scorecard": out}


# ---------------------------------------------------------------------------
# Node 4: Compliance guardrail
# ---------------------------------------------------------------------------

async def node_compliance(state: dict[str, Any]) -> dict[str, Any]:
    hr = state.get("hr_scorecard") or {}
    tech = state.get("technical_scorecard") or {}
    dp = {
        "hr_recommendation": (hr or {}).get("recommendation_from_hr_perspective", ""),
        "technical_recommendation": (tech or {}).get("recommendation_from_technical_perspective", ""),
    }
    system = (
        "You are a compliance guardrail. Detect biased or illegal interview patterns in TEXT outputs only. "
        "Output JSON: compliance_status (pass|warning|fail), detected_issues (list of strings), "
        "corrected_output (or null), audit_notes"
    )
    out = await _llm_json(system, json.dumps({"artifacts": dp}, default=str))
    return {"compliance": out}


# ---------------------------------------------------------------------------
# Node 5: Decision support (+ DB persist, Phase 2.2)
# ---------------------------------------------------------------------------

async def node_decision_support(state: dict[str, Any]) -> dict[str, Any]:
    hr = state.get("hr_scorecard") or {}
    tech = state.get("technical_scorecard") or {}
    comp = state.get("compliance") or {}
    jm = state.get("job_match_score")
    tq = state.get("transcript_quality") or "medium"
    itype = (state.get("interview_type") or "mixed").lower()
    org_id = state.get("organization_id")
    app_ctx = state.get("application_context") or {}
    job_ctx = state.get("job_context") or {}
    cand_ctx = state.get("candidate_context") or {}
    interview_id = state.get("interview_id")

    def _f(v: Any, default: float = 0.0) -> float:
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    def _norm01(v: Any, default: float = 0.0) -> float:
        """Coerce a model score to 0..1, tolerating 0-1, 0-10, or 0-100 inputs.

        The LLM is inconsistent about scale (it may return 7, 7.0, 70, or 0.7
        for "70%"), which previously made the final score collapse to single
        digits and render as e.g. 580%. Detect the scale and normalise.
        """
        x = _f(v, default)
        if x <= 1.0:
            return min(max(x, 0.0), 1.0)
        if x <= 10.0:
            return min(x, 10.0) / 10.0
        return min(x, 100.0) / 100.0

    hr_s = _f(hr.get("overall_hr_score"), 0.0)
    tech_s = _f(tech.get("overall_technical_score"), 0.0) if itype != "hr" else 0.0
    match_s: float | None
    if jm is None:
        match_s = None
    else:
        jmf = _f(jm, 0.0)
        match_s = jmf * 100.0 if jmf <= 1.0 else jmf

    def _present(v: Any) -> bool:
        if v is None:
            return False
        try:
            float(v)
            return True
        except (TypeError, ValueError):
            return False

    # Headline score = the interview's OWN performance, weighted STRICTLY by
    # interview type:
    #   HR        → 100% HR scorecard
    #   technical → 100% technical scorecard
    #   mixed     → 50% HR + 50% technical
    # Job-match and transcript-confidence are pre-interview / meta signals and
    # are intentionally NOT folded into this number (they're surfaced
    # separately as job_match_score).
    hr_present = _present(hr.get("overall_hr_score"))
    tech_present = _present(tech.get("overall_technical_score"))
    norm_hr = _norm01(hr_s)
    norm_tech = _norm01(tech_s) if itype != "hr" else 0.0

    if itype == "hr":
        final_unit = norm_hr
    elif itype == "technical":
        final_unit = norm_tech
    else:  # mixed → even 50/50 split; if only one track was actually scored,
           # use that side so a partial interview isn't unfairly halved.
        if hr_present and tech_present:
            final_unit = 0.5 * norm_hr + 0.5 * norm_tech
        elif hr_present:
            final_unit = norm_hr
        elif tech_present:
            final_unit = norm_tech
        else:
            final_unit = 0.0
    # Guarantee an out-of-100 value regardless of upstream scale quirks.
    final_score_100 = round(min(max(final_unit * 100.0, 0.0), 100.0), 1)

    system = (
        "You are a decision-support assistant for HR. Never make autonomous hiring decisions. "
        "The final hire/no-hire is always with HR. "
        "Return ONLY JSON: overall_recommendation, confidence, main_strengths, main_weaknesses, risk_flags, "
        "missing_information, evidence_summary (list of {claim, evidence}), suggested_next_step, "
        "suggested_growth_plan_if_rejected, human_review_required (always true). "
        "overall_recommendation must be one of: "
        "Accept, Reject, Hold, Needs another technical interview, Needs another HR interview, "
        "Needs manager review, Needs another interview"
    )
    user = json.dumps(
        {
            "hr": hr,
            "technical": tech,
            "compliance": comp,
            "computed_final_score": final_score_100,
            "interview_type": itype,
        },
        default=str,
    )
    out = await _llm_json(system, user)
    out["final_score"] = final_score_100
    out["hr_score"] = hr_s
    out["technical_score"] = tech_s
    # Self-describe the packet so downstream consumers (the IDSS rubric) can
    # attribute scores by interview type: a separate technical interview feeds
    # only the technical line, a separate HR interview only the HR line, and a
    # mixed interview feeds both.
    out["interview_type"] = itype
    out["job_match_score"] = round(match_s, 2) if match_s is not None else None
    out["human_review_required"] = True
    cstatus = (comp.get("compliance_status") or "pass").lower()
    if cstatus == "fail":
        out["overall_recommendation"] = "Hold"
        out["suggested_next_step"] = "Compliance review required before proceeding."

    # ------------------------------------------------------------------ #
    # Persist to decision_support_packets + development_plans (Phase 2.2) #
    # ------------------------------------------------------------------ #
    packet_id_str: str | None = None
    plan_id_str: str | None = None

    app_id_str = app_ctx.get("id")
    job_id_str = job_ctx.get("id")
    cand_id_str = cand_ctx.get("id")

    if org_id and app_id_str and job_id_str and cand_id_str:
        try:
            from app.db.models.decision_support import DecisionSupportPacket, DevelopmentPlan

            db = SessionLocal()
            try:
                packet = DecisionSupportPacket(
                    organization_id=UUID(org_id),
                    job_id=UUID(job_id_str),
                    candidate_id=UUID(cand_id_str),
                    application_id=UUID(app_id_str),
                    generated_by_agent="interview_intelligence_v2",
                    final_journey_score=final_score_100,
                    recommendation=out.get("overall_recommendation"),
                    confidence=_f(out.get("confidence"), 0.0),
                    packet_json=out,
                    evidence_json={"evidence_summary": out.get("evidence_summary", [])},
                    compliance_status=comp.get("compliance_status", "pass"),
                    human_review_required=True,
                )
                db.add(packet)
                db.flush()
                packet_id_str = str(packet.id)

                # DevelopmentPlan: create when there's a growth suggestion
                growth_plan = out.get("suggested_growth_plan_if_rejected")
                recommendation = (out.get("overall_recommendation") or "").lower()
                if growth_plan:
                    plan_type = (
                        "rejected_improvement_plan"
                        if "reject" in recommendation
                        else "accepted_internal_growth"
                    )
                    plan = DevelopmentPlan(
                        decision_packet_id=packet.id,
                        organization_id=UUID(org_id),
                        job_id=UUID(job_id_str),
                        candidate_id=UUID(cand_id_str),
                        application_id=UUID(app_id_str),
                        plan_type=plan_type,
                        generated_by_agent="interview_intelligence_v2",
                        plan_json={
                            "growth_plan": growth_plan,
                            "interview_type": itype,
                            "recommendation": out.get("overall_recommendation"),
                        },
                        summary=(
                            growth_plan
                            if isinstance(growth_plan, str)
                            else str(growth_plan)[:500]
                        ),
                    )
                    db.add(plan)
                    db.flush()
                    plan_id_str = str(plan.id)

                db.commit()
                logger.info(
                    "[DecisionSupport] persisted packet=%s plan=%s",
                    packet_id_str, plan_id_str,
                )
            except Exception:
                db.rollback()
                logger.exception("[DecisionSupport] DB persist failed")
            finally:
                db.close()

        except ImportError:
            logger.warning("[DecisionSupport] DB models not importable; skipping persist")

    return {
        "decision_packet": out,
        "decision_support_packet_id": packet_id_str,
        "development_plan_id": plan_id_str,
    }

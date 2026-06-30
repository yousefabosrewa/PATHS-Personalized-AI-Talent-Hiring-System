"""Decision Support agent nodes (4-node pipeline).

gather_signals → synthesize → generate_growth_plan → persist_decision → END

This is the standalone version extracted from interview_intelligence/graph.py.
It can be triggered independently after any hiring decision.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.db.models import (
    Job,
    Candidate,
    Application,
    InterviewDecisionPacket,
    ScreeningResult,
    DecisionSupportPacket,
    BiasFlag,
)
from app.db.models.agent_runs import AgentRun
from app.db.models.growth_plans import GrowthPlan
from app.agents.decision_support.state import DecisionSupportState
from app.services.llm_provider import get_llm

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_db() -> Session:
    return SessionLocal()


def _advance_run(db: Session, run_id: str | None, node: str) -> None:
    if not run_id:
        return
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if run:
        run.current_node = node
        db.commit()


# ── Node 1: gather_signals ────────────────────────────────────────────────────

def gather_signals_node(state: DecisionSupportState) -> dict[str, Any]:
    """Load all relevant signals: job, candidate, interview results, screening."""
    db = _get_db()
    try:
        _advance_run(db, state.get("agent_run_id"), "gather_signals")

        job_id       = state["job_id"]
        candidate_id = state["candidate_id"]
        app_id       = state.get("application_id")
        org_id       = state["organization_id"]

        # Job context
        job = db.query(Job).filter(Job.id == job_id).first()
        job_context = {
            "job_id": str(job.id) if job else job_id,
            "title": getattr(job, "title", "Unknown") if job else "Unknown",
            "requirements": [],
        }

        # Candidate context
        cand = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        cand_context = {
            "candidate_id": candidate_id,
            "full_name": getattr(cand, "full_name", "Unknown") if cand else "Unknown",
            "years_experience": getattr(cand, "years_experience", None) if cand else None,
        }

        # Interview results — all decision packets for this candidate + job
        packets = (
            db.query(InterviewDecisionPacket)
            .filter(
                InterviewDecisionPacket.candidate_id == candidate_id,
            )
            .order_by(InterviewDecisionPacket.created_at.desc())
            .limit(5)
            .all()
        )
        interview_results = []
        for p in packets:
            packet_data = p.decision_packet_json or {}
            if isinstance(packet_data, str):
                try:
                    packet_data = json.loads(packet_data)
                except Exception:
                    packet_data = {}
            interview_results.append({
                "recommendation": p.recommendation,
                "final_score": float(p.final_score or 0),
                "packet": packet_data,
            })

        # Screening result
        sr = (
            db.query(ScreeningResult)
            .filter(
                ScreeningResult.candidate_id == candidate_id,
            )
            .order_by(ScreeningResult.created_at.desc())
            .first()
        ) if hasattr(ScreeningResult, "candidate_id") else None

        screening_result = None
        if sr:
            screening_result = {
                "agent_score": float(sr.agent_score or 0),
                "recommendation": sr.recommendation,
                "final_score": float(sr.final_score or 0),
            }

        # Bias flags for this candidate
        flags = (
            db.query(BiasFlag)
            .filter(BiasFlag.candidate_id == candidate_id)
            .all()
        )
        bias_flags = [f"{f.attribute}:{f.group_label}" for f in flags if hasattr(f, "attribute")]

        return {
            "job_context": job_context,
            "candidate_context": cand_context,
            "interview_results": interview_results,
            "screening_result": screening_result,
            "bias_flags": bias_flags,
        }
    except Exception as exc:
        logger.exception("gather_signals_node failed")
        return {"status": "failed", "error": str(exc)}
    finally:
        db.close()


# ── Node 2: synthesize ────────────────────────────────────────────────────────

def synthesize_node(state: DecisionSupportState) -> dict[str, Any]:
    """Call the LLM to synthesise all signals into a final recommendation."""
    db = _get_db()
    try:
        _advance_run(db, state.get("agent_run_id"), "synthesize")

        job_ctx   = state.get("job_context", {})
        cand_ctx  = state.get("candidate_context", {})
        interviews = state.get("interview_results", [])
        screening = state.get("screening_result")
        bias_flags = state.get("bias_flags", [])

        # Build LLM prompt
        avg_interview_score = (
            sum(r["final_score"] for r in interviews) / len(interviews)
            if interviews else 0
        )
        prompt = f"""You are a senior hiring decision advisor for PATHS.

Job: {job_ctx.get("title")}
Candidate: {cand_ctx.get("full_name")}, {cand_ctx.get("years_experience")} years experience.

Interview results ({len(interviews)} session(s)):
  - Average interview score: {avg_interview_score:.1f}/100
  - Recommendations: {[r.get("recommendation") for r in interviews]}

Screening result: {screening or "Not screened"}

Bias flags raised: {bias_flags or "None"}

Provide a JSON object with:
{{
  "recommendation": "hire" | "reject" | "hold",
  "confidence": 0.0-1.0,
  "reasoning": "2-3 sentence explanation",
  "key_strengths": ["..."],
  "key_concerns": ["..."],
  "hr_score": 0-100,
  "technical_score": 0-100
}}"""

        llm = get_llm(temperature=0.1)
        try:
            response = llm.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            # Extract JSON from the response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                synthesis = json.loads(content[start:end])
            else:
                raise ValueError("No JSON found in LLM response")
        except Exception as llm_exc:
            logger.warning("LLM synthesis failed, using heuristic: %s", llm_exc)
            # Fallback heuristic
            rec = "hire" if avg_interview_score >= 70 else ("hold" if avg_interview_score >= 55 else "reject")
            synthesis = {
                "recommendation": rec,
                "confidence": round(avg_interview_score / 100, 2),
                "reasoning": f"Based on average interview score of {avg_interview_score:.0f}/100.",
                "key_strengths": [],
                "key_concerns": bias_flags,
                "hr_score": avg_interview_score,
                "technical_score": avg_interview_score,
            }

        return {
            "synthesis": synthesis,
            "recommendation": synthesis.get("recommendation", "hold"),
            "confidence": synthesis.get("confidence", 0.5),
            "reasoning": synthesis.get("reasoning", ""),
        }
    except Exception as exc:
        logger.exception("synthesize_node failed")
        return {"status": "failed", "error": str(exc)}
    finally:
        db.close()


# ── Node 3: generate_growth_plan ──────────────────────────────────────────────

def generate_growth_plan_node(state: DecisionSupportState) -> dict[str, Any]:
    """Generate a personalised growth plan — only for hire decisions."""
    db = _get_db()
    try:
        _advance_run(db, state.get("agent_run_id"), "generate_growth_plan")

        recommendation = state.get("recommendation", "hold")
        if recommendation != "hire":
            # Skip for non-hire decisions
            return {"growth_plan": None}

        cand_ctx = state.get("candidate_context", {})
        job_ctx  = state.get("job_context", {})
        synthesis = state.get("synthesis", {})

        concerns = synthesis.get("key_concerns", [])

        # Build a structured growth plan
        growth_plan = {
            "candidate_id": state.get("candidate_id"),
            "job_id": state.get("job_id"),
            "skill_gaps": [
                {"skill": concern, "gap_level": "medium", "priority": i + 1}
                for i, concern in enumerate(concerns[:3])
            ],
            "learning_resources": [
                {
                    "title": f"Udemy: Advanced {job_ctx.get('title', 'Skills')}",
                    "type": "course",
                    "estimated_hours": 10,
                },
                {
                    "title": "O'Reilly Learning Platform — 6-month access",
                    "type": "platform",
                    "estimated_hours": 40,
                },
            ],
            "milestones": [
                {
                    "label": "30-day",
                    "goals": ["Complete onboarding", "Meet team", "Shadow key processes"],
                    "success_criteria": "Onboarding checklist 100% complete",
                },
                {
                    "label": "60-day",
                    "goals": ["Own first deliverable", "Resolve first ticket independently"],
                    "success_criteria": "First PR merged with < 2 revisions",
                },
                {
                    "label": "90-day",
                    "goals": ["Full autonomy on role scope", "Present team retrospective"],
                    "success_criteria": "Peer review score >= 4/5",
                },
            ],
            "candidate_facing_message": (
                f"Welcome aboard! We're excited to have you join us as {job_ctx.get('title')}. "
                "Your growth plan below outlines your first 90 days and the resources we've prepared for you."
            ),
        }

        return {"growth_plan": growth_plan}
    except Exception as exc:
        logger.exception("generate_growth_plan_node failed")
        return {"growth_plan": None}  # Non-fatal
    finally:
        db.close()


# ── Node 4: persist_decision ──────────────────────────────────────────────────

def persist_decision_node(state: DecisionSupportState) -> dict[str, Any]:
    """Persist the decision packet and (optionally) the growth plan to DB."""
    db = _get_db()
    try:
        _advance_run(db, state.get("agent_run_id"), "persist_decision")

        org_id       = state["organization_id"]
        candidate_id = state["candidate_id"]
        job_id       = state["job_id"]
        app_id       = state.get("application_id")
        synthesis    = state.get("synthesis", {})
        growth_plan_data = state.get("growth_plan")

        # Persist DecisionSupportPacket
        packet = DecisionSupportPacket(
            id=str(uuid.uuid4()),
            organization_id=org_id,
            candidate_id=candidate_id,
            job_id=job_id,
            application_id=app_id,
            recommendation=state.get("recommendation", "hold"),
            overall_score=synthesis.get("confidence", 0.5) * 100,
            hr_score=synthesis.get("hr_score"),
            technical_score=synthesis.get("technical_score"),
            reasoning=state.get("reasoning", ""),
            generated_at=datetime.now(timezone.utc),
        )
        db.add(packet)
        db.flush()

        packet_id = str(packet.id)
        growth_plan_id = None

        # Persist GrowthPlan for hire decisions
        if growth_plan_data:
            gp = GrowthPlan(
                organization_id=org_id,
                candidate_id=candidate_id,
                job_id=job_id,
                decision_id=packet_id,
                skill_gaps=growth_plan_data.get("skill_gaps"),
                learning_resources=growth_plan_data.get("learning_resources"),
                milestones=growth_plan_data.get("milestones"),
                candidate_facing_message=growth_plan_data.get("candidate_facing_message"),
                status="active",
            )
            db.add(gp)
            db.flush()
            growth_plan_id = str(gp.id)

        # Complete the agent run
        run_id = state.get("agent_run_id")
        if run_id:
            run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
            if run:
                run.status = "completed"
                run.current_node = None
                run.finished_at = datetime.now(timezone.utc)
                run.result_ref = {
                    "decision_support_packet_id": packet_id,
                    "growth_plan_id": growth_plan_id,
                    "recommendation": state.get("recommendation"),
                }
                db.commit()
        else:
            db.commit()

        return {
            "decision_support_packet_id": packet_id,
            "growth_plan_id": growth_plan_id,
            "status": "completed",
        }
    except Exception as exc:
        db.rollback()
        logger.exception("persist_decision_node failed")
        return {"status": "failed", "error": str(exc)}
    finally:
        db.close()

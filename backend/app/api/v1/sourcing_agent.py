"""Sourcing Agent API endpoints.

POST /jobs/{job_id}/candidate-pool/preview   — dry-run, returns top-K matches
POST /jobs/{job_id}/candidate-pool/build     — triggers sourcing graph via BackgroundTasks
GET  /jobs/{job_id}/candidate-pool/runs      — list CandidatePoolRun history
POST /jobs/{job_id}/decisions/recompute      — re-run decision support for a candidate
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.db.models.agent_runs import AgentRun
from app.db.models import CandidatePoolRun, CandidatePoolMember
from app.services.agent_runs import AgentRunService

router = APIRouter(tags=["sourcing-agent"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Schemas ───────────────────────────────────────────────────────────────────

class BuildPoolRequest(BaseModel):
    organization_id: str
    top_k: int = Field(20, ge=1, le=200)
    min_score: float = Field(0.6, ge=0.0, le=1.0)
    provider: str = "mock"
    location_filter: str | None = None
    workplace_filter: list[str] = []


class BuildPoolResponse(BaseModel):
    run_id: str
    agent_run_id: str
    message: str


class PoolRunOut(BaseModel):
    pool_run_id: str
    job_id: str
    status: str
    candidates_found: int
    created_at: str


class DecisionRecomputeRequest(BaseModel):
    organization_id: str
    candidate_id: str
    application_id: str | None = None


class DecisionRecomputeResponse(BaseModel):
    agent_run_id: str
    message: str


# ── Background task ───────────────────────────────────────────────────────────

async def _run_sourcing_graph(job_id: str, agent_run_id: str, payload: dict[str, Any]) -> None:
    """Execute the sourcing agent graph in the background."""
    try:
        from app.agents.sourcing.graph import build_sourcing_graph
        graph = build_sourcing_graph()
        await graph.ainvoke({**payload, "agent_run_id": agent_run_id})
    except Exception as exc:
        # Mark run as failed
        db = SessionLocal()
        try:
            svc = AgentRunService(db)
            svc.fail(agent_run_id, str(exc))
        finally:
            db.close()


async def _run_decision_support_graph(agent_run_id: str, payload: dict[str, Any]) -> None:
    """Execute the decision support agent graph in the background."""
    try:
        from app.agents.decision_support.graph import build_decision_support_graph
        graph = build_decision_support_graph()
        await graph.ainvoke({**payload, "agent_run_id": agent_run_id})
    except Exception as exc:
        db = SessionLocal()
        try:
            svc = AgentRunService(db)
            svc.fail(agent_run_id, str(exc))
        finally:
            db.close()


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/jobs/{job_id}/candidate-pool/build", response_model=BuildPoolResponse)
def build_candidate_pool(
    job_id: str,
    body: BuildPoolRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Trigger the sourcing agent to build the candidate pool for a job.

    Returns immediately with a run_id; poll GET /api/v1/agent-runs/{run_id}
    for live status.
    """
    svc = AgentRunService(db)
    run = svc.create(
        org_id=body.organization_id,
        run_type="sourcing",
        entity_type="job",
        entity_id=job_id,
        input_ref={
            "top_k": body.top_k,
            "min_score": body.min_score,
            "provider": body.provider,
        },
    )
    svc.start(run.id, current_node="search_query")

    payload = {
        "job_id": job_id,
        "organization_id": body.organization_id,
        "top_k": body.top_k,
        "min_score": body.min_score,
        "provider": body.provider,
        "location_filter": body.location_filter,
        "workplace_filter": body.workplace_filter,
    }

    background_tasks.add_task(_run_sourcing_graph, job_id, str(run.id), payload)

    return BuildPoolResponse(
        run_id=str(run.id),
        agent_run_id=str(run.id),
        message="Sourcing agent started. Poll /api/v1/agent-runs/{run_id} for progress.",
    )


@router.get("/jobs/{job_id}/candidate-pool/runs", response_model=list[PoolRunOut])
def list_pool_runs(
    job_id: str,
    org_id: str = Query(...),
    limit: int = Query(10, le=50),
    db: Session = Depends(get_db),
):
    """Return the sourcing run history for a job."""
    runs = (
        db.query(CandidatePoolRun)
        .filter(
            CandidatePoolRun.job_id == job_id,
            CandidatePoolRun.organization_id == org_id,
        )
        .order_by(CandidatePoolRun.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        PoolRunOut(
            pool_run_id=str(r.id),
            job_id=str(r.job_id),
            status=r.status or "completed",
            candidates_found=r.candidates_found or 0,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in runs
    ]


@router.post("/jobs/{job_id}/decisions/recompute", response_model=DecisionRecomputeResponse)
def recompute_decision(
    job_id: str,
    body: DecisionRecomputeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Re-run the Decision Support agent for a candidate on a specific job.

    Use this when new interview results are available or when HR wants to
    refresh the AI recommendation.
    """
    svc = AgentRunService(db)
    run = svc.create(
        org_id=body.organization_id,
        run_type="decision_support",
        entity_type="candidate",
        entity_id=body.candidate_id,
        input_ref={"job_id": job_id, "candidate_id": body.candidate_id},
    )
    svc.start(run.id, current_node="gather_signals")

    payload = {
        "job_id": job_id,
        "candidate_id": body.candidate_id,
        "application_id": body.application_id,
        "organization_id": body.organization_id,
    }
    background_tasks.add_task(_run_decision_support_graph, str(run.id), payload)

    return DecisionRecomputeResponse(
        agent_run_id=str(run.id),
        message="Decision Support agent started. Poll /api/v1/agent-runs/{run_id} for progress.",
    )

"""Agent-run polling endpoint.

GET /api/v1/agent-runs/{run_id}          — poll a single run (2 s interval)
GET /api/v1/agent-runs?org_id=…&type=…  — list recent runs for an org
"""

from __future__ import annotations

from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.db.models.agent_runs import AgentRun
from app.services.agent_runs import AgentRunService

router = APIRouter(tags=["agent-runs"])


# ── Dependency ────────────────────────────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Schemas ───────────────────────────────────────────────────────────────────

class AgentRunOut(BaseModel):
    run_id: str
    run_type: str
    status: str
    current_node: str | None
    entity_type: str | None
    entity_id: str | None
    result_ref: dict[str, Any] | None
    error: str | None
    started_at: str | None
    finished_at: str | None
    created_at: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_obj(cls, run: AgentRun) -> "AgentRunOut":
        return cls(
            run_id=str(run.id),
            run_type=run.run_type,
            status=run.status,
            current_node=run.current_node,
            entity_type=run.entity_type,
            entity_id=run.entity_id,
            result_ref=run.result_ref,
            error=run.error,
            started_at=run.started_at.isoformat() if run.started_at else None,
            finished_at=run.finished_at.isoformat() if run.finished_at else None,
            created_at=run.created_at.isoformat(),
        )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/agent-runs/{run_id}", response_model=AgentRunOut)
def get_agent_run(
    run_id: str,
    db: Session = Depends(get_db),
):
    """Poll the status of a single agent run.

    The frontend calls this every 2 seconds while status is queued/running.
    Returns 404 when the run_id does not exist (caller should stop polling).
    """
    svc = AgentRunService(db)
    run = svc.get(run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found")
    return AgentRunOut.from_orm_obj(run)


@router.get("/agent-runs", response_model=list[AgentRunOut])
def list_agent_runs(
    org_id: str = Query(..., description="Organisation ID (tenant filter)"),
    run_type: str | None = Query(None, description="Filter by agent type"),
    run_status: str | None = Query(None, alias="status", description="Filter by status"),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    """List recent agent runs for an organisation.

    Used by the global AgentRunsListener to surface toast notifications
    when a run completes or fails.
    """
    svc = AgentRunService(db)
    runs = svc.list_for_org(org_id, run_type=run_type, status=run_status, limit=limit)
    return [AgentRunOut.from_orm_obj(r) for r in runs]

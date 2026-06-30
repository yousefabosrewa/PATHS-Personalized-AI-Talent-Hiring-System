"""Generic agent-run tracking service.

Every long-running LangGraph invocation creates an AgentRun record before
starting and updates it as it progresses.  The frontend polls
GET /api/v1/agent-runs/{run_id} for live status.

Usage inside an agent node:
    from app.services.agent_runs import AgentRunService

    svc = AgentRunService(db)
    run = svc.create(org_id="...", run_type="screening", entity_type="job", entity_id=job_id)
    svc.start(run.id, current_node="fetch_candidates")
    # … work …
    svc.advance(run.id, "score_candidates")
    svc.complete(run.id, result_ref={"top_k": 10})
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.agent_runs import AgentRun


class AgentRunService:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def create(
        self,
        org_id: str,
        run_type: str,
        entity_type: str | None = None,
        entity_id: str | None = None,
        triggered_by: str | None = None,
        input_ref: dict[str, Any] | None = None,
    ) -> AgentRun:
        run = AgentRun(
            organization_id=org_id,
            run_type=run_type,
            status="queued",
            entity_type=entity_type,
            entity_id=entity_id,
            triggered_by=triggered_by,
            input_ref=input_ref,
        )
        self._db.add(run)
        self._db.commit()
        self._db.refresh(run)
        return run

    def get(self, run_id: str | uuid.UUID) -> AgentRun | None:
        return self._db.query(AgentRun).filter(AgentRun.id == str(run_id)).first()

    def list_for_org(
        self,
        org_id: str,
        run_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[AgentRun]:
        q = self._db.query(AgentRun).filter(AgentRun.organization_id == org_id)
        if run_type:
            q = q.filter(AgentRun.run_type == run_type)
        if status:
            q = q.filter(AgentRun.status == status)
        return q.order_by(AgentRun.created_at.desc()).limit(limit).all()

    # ── State transitions ─────────────────────────────────────────────────────

    def start(self, run_id: str | uuid.UUID, current_node: str | None = None) -> None:
        run = self.get(run_id)
        if run:
            run.status = "running"
            run.started_at = datetime.now(timezone.utc)
            if current_node:
                run.current_node = current_node
            self._db.commit()

    def advance(self, run_id: str | uuid.UUID, current_node: str) -> None:
        run = self.get(run_id)
        if run:
            run.current_node = current_node
            self._db.commit()

    def complete(
        self,
        run_id: str | uuid.UUID,
        result_ref: dict[str, Any] | None = None,
    ) -> None:
        run = self.get(run_id)
        if run:
            run.status = "completed"
            run.finished_at = datetime.now(timezone.utc)
            run.current_node = None
            if result_ref is not None:
                run.result_ref = result_ref
            self._db.commit()

    def fail(self, run_id: str | uuid.UUID, error: str) -> None:
        run = self.get(run_id)
        if run:
            run.status = "failed"
            run.finished_at = datetime.now(timezone.utc)
            run.error = error
            self._db.commit()

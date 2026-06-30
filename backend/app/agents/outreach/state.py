"""LangGraph state for the Outreach Agent pipeline."""

from __future__ import annotations

from typing import Any, TypedDict


class OutreachState(TypedDict, total=False):
    # -- Required inputs -------------------------------------------------------
    job_id: str
    organization_id: str
    hr_user_id: str
    candidate_ids: list[str]        # shortlisted candidate IDs to outreach

    # -- Node 1 output: compose_emails ----------------------------------------
    composed_sessions: list[dict[str, Any]]  # [{session_id, candidate_id, status}]
    compose_errors: list[str]

    # -- Node 2 output: send_emails -------------------------------------------
    sent_count: int
    failed_count: int
    session_results: list[dict[str, Any]]   # [{session_id, candidate_id, status, error?}]

    # -- Node 3 output: track_sends -------------------------------------------
    tracked: bool
    analytics_event_id: str | None

    # -- Final status ---------------------------------------------------------
    status: str          # "completed" | "partial" | "failed"
    error: str | None

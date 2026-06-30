"""Decision Support agent state."""

from __future__ import annotations

from typing import Any
from typing_extensions import TypedDict


class DecisionSupportState(TypedDict, total=False):
    # ── Inputs ───────────────────────────────────────────────────────────────
    job_id: str
    candidate_id: str
    application_id: str
    organization_id: str
    agent_run_id: str | None      # tracks progress in agent_runs table

    # ── Gathered signals ─────────────────────────────────────────────────────
    job_context: dict[str, Any]
    candidate_context: dict[str, Any]
    interview_results: list[dict[str, Any]]  # from interview_decision_packets
    screening_result: dict[str, Any] | None  # from screening_results
    bias_flags: list[str]                    # flagged attribute:group strings

    # ── Node outputs ─────────────────────────────────────────────────────────
    synthesis: dict[str, Any]        # LLM-synthesised recommendation
    growth_plan: dict[str, Any] | None  # Only for hire decisions

    # ── Persisted IDs ────────────────────────────────────────────────────────
    decision_support_packet_id: str | None
    growth_plan_id: str | None

    # ── Final ────────────────────────────────────────────────────────────────
    recommendation: str   # "hire" | "reject" | "hold"
    confidence: float
    reasoning: str
    status: str
    error: str | None

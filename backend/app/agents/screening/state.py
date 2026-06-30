"""
PATHS Backend -- Screening Agent LangGraph state definition.
"""

from typing import TypedDict


class ScreeningState(TypedDict, total=False):
    """Typed state flowing through the screening LangGraph pipeline."""

    # -- Input ----------------------------------------------------------------
    job_id: str
    organization_id: str
    source: str                     # "database" | "csv_upload"
    top_k: int
    force_rescore: bool

    # For CSV path -- pre-imported candidate IDs
    csv_candidate_ids: list[str]

    # -- Pipeline state -------------------------------------------------------
    discovered_candidate_ids: list[str]
    scored_candidates: list[dict]   # [{candidate_id, agent_score, ...}, ...]

    # -- Counters -------------------------------------------------------------
    total_scanned: int
    passed_filter: int
    scored_count: int
    failed_count: int

    # -- Output ---------------------------------------------------------------
    screening_run_id: str
    ranked_results: list[dict]      # Final ranked list
    status: str                     # "completed" | "failed"
    error: str | None

    # -- Bias Guardrail (Phase 2.1) -------------------------------------------
    bias_report: list[dict]         # Per-attribute group metrics (from bias_reports table)
    bias_flags_raised: list[str]    # "attr:group" strings for groups that failed threshold

"""Sourcing agent state definition."""

from __future__ import annotations

from typing import Any
from typing_extensions import TypedDict


class SourcingState(TypedDict, total=False):
    # ── Inputs ───────────────────────────────────────────────────────────────
    job_id: str
    organization_id: str
    agent_run_id: str          # ID in agent_runs table for progress tracking

    # ── Configuration ────────────────────────────────────────────────────────
    top_k: int                  # How many candidates to return
    min_score: float            # Minimum match score threshold (0-1)
    location_filter: str | None
    workplace_filter: list[str]  # ["remote", "hybrid", "onsite"]
    provider: str               # "mock" | "internal_pool" | "linkedin" | ...

    # ── Node outputs ─────────────────────────────────────────────────────────
    job_context: dict[str, Any]          # Job requirements loaded from DB
    raw_candidates: list[dict[str, Any]] # Results from source provider
    filtered_candidates: list[dict[str, Any]]   # After min_score filter
    deduplicated_candidates: list[dict[str, Any]] # After dedup against existing pool
    enriched_candidates: list[dict[str, Any]]    # After contact enrichment

    # ── Results ──────────────────────────────────────────────────────────────
    persisted_count: int         # How many new candidates were saved
    pool_run_id: str             # ID of the CandidatePoolRun record
    status: str                  # "completed" | "failed"
    error: str | None

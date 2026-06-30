"""
PATHS Backend — Pydantic schemas for the Screening Agent API.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Request bodies ───────────────────────────────────────────────────────


class ScreenJobRequest(BaseModel):
    """Body for POST /screening/jobs/{job_id}/screen."""

    organization_id: str
    top_k: int = Field(default=10, ge=1, le=100)
    force_rescore: bool = False


# ── Response objects ─────────────────────────────────────────────────────


class ScreeningRunResponse(BaseModel):
    """Summary of a screening run."""

    screening_run_id: str
    organization_id: str
    job_id: str
    source: str
    top_k: int
    status: str
    total_candidates_scanned: int = 0
    candidates_passed_filter: int = 0
    candidates_scored: int = 0
    candidates_failed: int = 0
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ScreeningResultItem(BaseModel):
    """One candidate's anonymized result within a screening run."""

    result_id: str
    blind_label: str
    rank_position: int | None = None
    agent_score: float
    vector_similarity_score: float
    final_score: float
    relevance_score: float | None = None
    recommendation: str | None = None
    match_classification: str | None = None
    status: str = "ranked"


class ScreeningResultDetail(ScreeningResultItem):
    """Full detail view of one candidate's screening result."""

    criteria_breakdown: dict[str, Any] | None = None
    matched_skills: list[str] = Field(default_factory=list)
    missing_required_skills: list[str] = Field(default_factory=list)
    missing_preferred_skills: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    explanation: str | None = None


class ScreeningRunWithResults(ScreeningRunResponse):
    """Full screening run response including the ranked results list."""

    results: list[ScreeningResultItem] = Field(default_factory=list)


class ScreeningResultsListResponse(BaseModel):
    """List of ranked results for a screening run."""

    screening_run_id: str
    job_id: str
    results: list[ScreeningResultItem] = Field(default_factory=list)


# -- Bias Report schemas (Phase 2.1) -----------------------------------------


class BiasReportEntry(BaseModel):
    """Per-group disparity metric for one protected attribute."""

    attribute_name: str
    group_label: str
    selection_count: int = 0
    total_count: int = 0
    selection_rate: float = 0.0
    # NULL for the reference (highest-rate) group
    disparate_impact_ratio: float | None = None
    threshold: float = 0.8
    passed: bool = True


class BiasReportResponse(BaseModel):
    """Bias guardrail report for one screening run."""

    screening_run_id: str
    job_id: str
    organization_id: str
    has_flags: bool
    flagged_attributes: list[str] = Field(default_factory=list)
    entries: list[BiasReportEntry] = Field(default_factory=list)


__all__ = [
    "ScreenJobRequest",
    "ScreeningRunResponse",
    "ScreeningResultItem",
    "ScreeningResultDetail",
    "ScreeningRunWithResults",
    "ScreeningResultsListResponse",
    "BiasReportEntry",
    "BiasReportResponse",
]

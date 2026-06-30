"""Shared LangGraph / pipeline state for interview post-processing."""

from __future__ import annotations

from typing import Any, TypedDict


class InterviewGraphState(TypedDict, total=False):
    # -- Required inputs -------------------------------------------------------
    interview_id: str
    organization_id: str
    error: str

    # -- Loaded context (populated by transcript_capture_node) ----------------
    interview_type: str             # "hr" | "technical" | "mixed"
    job_context: dict[str, Any]
    candidate_context: dict[str, Any]
    application_context: dict[str, Any]
    question_packs: list[dict[str, Any]]
    transcript: str
    transcript_quality: str         # "high" | "medium" | "low"
    job_match_score: float | None

    # -- RAG context (populated by hr/tech evaluation nodes) ------------------
    rag_context: list[dict[str, Any]]   # top-k similar past interview snippets

    # -- Agent outputs --------------------------------------------------------
    interview_summary: dict[str, Any]
    hr_scorecard: dict[str, Any]
    technical_scorecard: dict[str, Any]
    compliance: dict[str, Any]
    decision_packet: dict[str, Any]

    # -- Persisted IDs (set by node_decision_support) -------------------------
    decision_support_packet_id: str | None
    development_plan_id: str | None

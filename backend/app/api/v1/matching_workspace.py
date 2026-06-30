"""PATHS Backend — Matching workspace routes (fix7.md).

Two recruiter-facing endpoints used by the new Outreach sub-tabs:

  POST /api/v1/matching/semantic-search
  POST /api/v1/matching/rag-test

Both return strictly anonymized data, are scoped to the caller's org,
and degrade gracefully when Qdrant / Ollama / OpenRouter is down.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import (
    OrgContext,
    require_active_org_status,
)
from app.services.matching_workspace import run_rag_test, semantic_search

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/matching", tags=["Matching workspace"])


# ── Schemas ──────────────────────────────────────────────────────────────────


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., description="Natural-language candidate search query")
    source: Literal["database", "outbound", "imported_csv", "all"] = "all"
    limit: int = Field(10, ge=1, le=50)


class SemanticSearchResultRow(BaseModel):
    candidate_id: str
    anonymized_label: str
    source: str
    source_display: str
    headline: str | None
    current_title: str | None
    semantic_score: int
    confidence: int
    matched_evidence: list[str]
    missing_signals: list[str]
    agent_explanation: str


class SemanticSearchResponse(BaseModel):
    query: str
    source: str
    limit: int
    semantic_search_used: bool
    agent_available: bool
    results: list[SemanticSearchResultRow]


class RagTestRequest(BaseModel):
    candidate_ids: list[str] = Field(..., min_length=1, max_length=25)
    job_id: str | None = None
    custom_requirements: str | None = None
    top_k_chunks: int = Field(5, ge=1, le=10)


class RagRubric(BaseModel):
    technical_fit: int
    experience_fit: int
    skill_evidence: int
    project_portfolio_evidence: int
    missing_requirements: int
    risk_factors: int


class RagEvidenceItem(BaseModel):
    field: str
    label: str
    excerpt: str
    relevance: float


class RagTestResultRow(BaseModel):
    candidate_id: str
    anonymized_label: str
    job_title: str | None
    requirement_label: str
    final_score: int
    confidence: int
    next_action: str
    rubric: RagRubric
    agent_explanation: str
    candidate_evidence_used: list[RagEvidenceItem]
    requirement_evidence_used: list[str]
    missing_data: list[str]
    used_agent_fallback: bool


class RagTestResponse(BaseModel):
    tests: list[RagTestResultRow]
    agent_available: bool
    retrieval_used: bool
    requirement_label: str
    job_title: str | None


# ── Routes ───────────────────────────────────────────────────────────────────


@router.post("/semantic-search", response_model=SemanticSearchResponse)
def semantic_search_route(
    body: SemanticSearchRequest,
    ctx: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
) -> SemanticSearchResponse:
    """Anonymized semantic candidate search (fix7.md §1)."""
    if not (body.query or "").strip():
        raise HTTPException(status_code=400, detail="query_required")
    try:
        result: dict[str, Any] = semantic_search(
            db,
            org_id=ctx.organization_id,
            query=body.query,
            source=body.source,
            limit=body.limit,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("semantic_search failed: %s", exc)
        raise HTTPException(status_code=500, detail="semantic_search_failed") from exc
    return SemanticSearchResponse(**result)


@router.post("/rag-test", response_model=RagTestResponse)
def rag_test_route(
    body: RagTestRequest,
    ctx: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
) -> RagTestResponse:
    """RAG-grounded candidate vs job/custom-requirement test (fix7.md §2)."""
    # Validate exactly one of job_id / custom_requirements is provided
    has_job = bool(body.job_id)
    has_req = bool((body.custom_requirements or "").strip())
    if has_job == has_req:
        raise HTTPException(
            status_code=400,
            detail="provide_exactly_one_of_job_id_or_custom_requirements",
        )

    job_uuid: uuid.UUID | None = None
    if body.job_id:
        try:
            job_uuid = uuid.UUID(body.job_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid_job_id") from exc

    cand_uuids: list[uuid.UUID] = []
    for cid in body.candidate_ids:
        try:
            cand_uuids.append(uuid.UUID(cid))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"invalid_candidate_id: {cid}") from exc

    try:
        result: dict[str, Any] = run_rag_test(
            db,
            org_id=ctx.organization_id,
            candidate_ids=cand_uuids,
            job_id=job_uuid,
            custom_requirements=body.custom_requirements,
            top_k_chunks=body.top_k_chunks,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("rag_test failed: %s", exc)
        raise HTTPException(status_code=500, detail="rag_test_failed") from exc

    return RagTestResponse(**result)

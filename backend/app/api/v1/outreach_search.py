"""PATHS Backend — Outreach search route (fix4.md).

Single endpoint:

    POST /api/v1/outreach/search

Returns an anonymized shortlist plus a per-candidate explanation generated
by the OpenRouter-backed agent. No real candidate identifiers (name,
email, phone, photo, LinkedIn URL, GitHub URL, portfolio URL) are
returned in the shortlist.
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
from app.services.outreach import run_outreach_search

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/outreach", tags=["Outreach"])


# ── Schemas ──────────────────────────────────────────────────────────────────


class OutreachSearchRequest(BaseModel):
    mode: Literal["database", "outbound"] = "database"
    query: str = Field("", description="Free-text recruiter query / role description")
    top_k: int = Field(8, ge=1, le=20)
    job_id: str | None = Field(
        default=None,
        description="Optional internal job UUID — used as agent context only.",
    )
    required_skills: list[str] = Field(default_factory=list)
    seniority_level: str | None = None
    workplace_type: str | None = None


class OutreachShortlistRow(BaseModel):
    candidate_id: str
    alias: str
    source: Literal["database", "outbound"]
    match_score: int
    confidence: Literal["high", "medium", "low"]
    matched_skills: list[str]
    missing_skills: list[str]
    agent_explanation: str
    confidence_rationale: str
    risks_or_missing_evidence: str
    used_fallback: bool


class OutreachSearchResponse(BaseModel):
    source_mode: Literal["database", "outbound"]
    query: str
    shortlist: list[OutreachShortlistRow]
    agent_available: bool


# ── Route ────────────────────────────────────────────────────────────────────


@router.post("/search", response_model=OutreachSearchResponse)
def outreach_search(
    body: OutreachSearchRequest,
    ctx: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
) -> OutreachSearchResponse:
    """Search candidates and return an anonymized shortlist with explanations.

    Mode ``"database"`` searches candidates already on the platform; mode
    ``"outbound"`` searches the LinkedIn Open-to-Work / outbound pool. Both
    return the same anonymized shape — the UI displays only alias + agent
    explanation by default.
    """
    job_uuid: uuid.UUID | None = None
    if body.job_id:
        try:
            job_uuid = uuid.UUID(body.job_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid job_id") from exc

    try:
        result: dict[str, Any] = run_outreach_search(
            db,
            org_id=ctx.organization_id,
            mode=body.mode,
            query=body.query,
            top_k=body.top_k,
            job_id=job_uuid,
            required_skills=list(body.required_skills),
            seniority_level=body.seniority_level,
            workplace_type=body.workplace_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("outreach_search failed: %s", exc)
        raise HTTPException(status_code=500, detail="outreach_search_failed") from exc

    return OutreachSearchResponse(**result)

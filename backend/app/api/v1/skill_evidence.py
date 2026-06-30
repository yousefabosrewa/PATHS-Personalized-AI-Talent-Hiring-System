"""
Per-skill evidence endpoints.

  GET    /candidates/{candidate_id}/skills/evidence
         Persisted per-skill evidence + scores. Lightweight — no LLM
         calls; just reads ``evidence_items`` rows.

  POST   /candidates/{candidate_id}/skills/evidence/refresh
         Re-runs the three MCP-style tools (CV / GitHub / LinkedIn) and
         the LLM scorer for every skill on the candidate (or a filtered
         subset). Slow: up to ~30s per skill in the worst case.

  GET    /candidates/{candidate_id}/skills/evidence/profile-urls
  PUT    /candidates/{candidate_id}/skills/evidence/profile-urls
         Recruiter sets / updates the candidate's LinkedIn + GitHub URLs
         when they weren't extracted from the CV.

All routes are gated behind the same access predicate used elsewhere
for recruiter-facing candidate data (``org_can_view_candidate``).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.candidate_access import org_can_view_candidate
from app.core.database import get_db
from app.core.dependencies import OrgContext, get_current_hiring_org_context
from app.services.skill_evidence.service import (
    SkillEvidenceReport,
    list_profile_urls,
    load_persisted_evidence,
    refresh_candidate_skill_evidence,
    upsert_profile_url,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/candidates", tags=["Candidate · Skill Evidence"])


# ── Schemas ──────────────────────────────────────────────────────────


class SkillEvidenceSourceOut(BaseModel):
    source: Literal["cv", "github", "linkedin"]
    status: str
    score: int | None
    reasoning: str
    snippets: list[dict[str, Any]]
    source_url: str | None
    weight: float
    fallback: bool = False


class SkillEvidenceItemOut(BaseModel):
    skill: str
    aggregate_score: int
    confidence: str
    summary: str
    last_refreshed_at: str | None
    sources: list[SkillEvidenceSourceOut]


class SkillEvidenceListOut(BaseModel):
    candidate_id: uuid.UUID
    items: list[SkillEvidenceItemOut]


class RefreshRequest(BaseModel):
    skills: list[str] | None = Field(
        default=None,
        description=(
            "Optional whitelist — when present, only these skill names "
            "are refreshed. Otherwise every known skill on the candidate "
            "is re-scored."
        ),
    )
    max_skills: int = Field(default=25, ge=1, le=50)


class ProfileUrlsOut(BaseModel):
    candidate_id: uuid.UUID
    github: str | None = None
    linkedin: str | None = None
    portfolio: str | None = None


class ProfileUrlsBody(BaseModel):
    github: str | None = None
    linkedin: str | None = None
    portfolio: str | None = None


# ── Helpers ──────────────────────────────────────────────────────────


def _require_access(
    db: Session, ctx: OrgContext, candidate_id: uuid.UUID,
) -> None:
    if not org_can_view_candidate(db, ctx.organization_id, candidate_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found.",
        )


def _report_to_schema(r: SkillEvidenceReport) -> SkillEvidenceItemOut:
    return SkillEvidenceItemOut(
        skill=r.skill,
        aggregate_score=r.aggregate_score,
        confidence=r.confidence,
        summary=r.summary,
        last_refreshed_at=r.last_refreshed_at,
        sources=[
            SkillEvidenceSourceOut(
                source=s.source,  # type: ignore[arg-type]
                status=s.status,
                score=s.score,
                reasoning=s.reasoning,
                snippets=s.snippets,
                source_url=s.source_url,
                weight=s.weight,
                fallback=s.fallback,
            )
            for s in r.sources
        ],
    )


# ── Endpoints ────────────────────────────────────────────────────────


@router.get(
    "/{candidate_id}/skills/evidence",
    response_model=SkillEvidenceListOut,
    summary="Return persisted per-skill evidence + scores.",
)
def get_skill_evidence(
    candidate_id: uuid.UUID,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
) -> SkillEvidenceListOut:
    _require_access(db, ctx, candidate_id)
    reports = load_persisted_evidence(db, candidate_id=candidate_id)
    return SkillEvidenceListOut(
        candidate_id=candidate_id,
        items=[_report_to_schema(r) for r in reports],
    )


@router.post(
    "/{candidate_id}/skills/evidence/refresh",
    response_model=SkillEvidenceListOut,
    summary="Re-run the MCP tools + LLM scorer for every skill on the candidate.",
)
def refresh_skill_evidence(
    candidate_id: uuid.UUID,
    body: RefreshRequest | None = Body(default=None),
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
) -> SkillEvidenceListOut:
    _require_access(db, ctx, candidate_id)
    try:
        reports = refresh_candidate_skill_evidence(
            db,
            candidate_id=candidate_id,
            skill_filter=(body.skills if body else None),
            max_skills=(body.max_skills if body else 25),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SkillEvidenceListOut(
        candidate_id=candidate_id,
        items=[_report_to_schema(r) for r in reports],
    )


@router.get(
    "/{candidate_id}/skills/evidence/profile-urls",
    response_model=ProfileUrlsOut,
    summary="Return the candidate's stored LinkedIn / GitHub / portfolio URLs.",
)
def get_profile_urls(
    candidate_id: uuid.UUID,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
) -> ProfileUrlsOut:
    _require_access(db, ctx, candidate_id)
    urls = list_profile_urls(db, candidate_id=candidate_id)
    return ProfileUrlsOut(
        candidate_id=candidate_id,
        github=urls.get("github"),
        linkedin=urls.get("linkedin"),
        portfolio=urls.get("portfolio"),
    )


@router.put(
    "/{candidate_id}/skills/evidence/profile-urls",
    response_model=ProfileUrlsOut,
    summary="Set the candidate's LinkedIn / GitHub / portfolio URLs so the agent can read them.",
)
def put_profile_urls(
    candidate_id: uuid.UUID,
    body: ProfileUrlsBody,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
) -> ProfileUrlsOut:
    _require_access(db, ctx, candidate_id)
    # Only update the URLs the caller actually sent. This lets the skill panel
    # manage just GitHub (Candidate.md §4 dropped LinkedIn from the rubric)
    # without wiping a stored LinkedIn URL it no longer displays.
    provided = body.model_fields_set
    try:
        if "github" in provided:
            upsert_profile_url(db, candidate_id=candidate_id, source="github", url=body.github)
        if "linkedin" in provided:
            upsert_profile_url(db, candidate_id=candidate_id, source="linkedin", url=body.linkedin)
        if "portfolio" in provided:
            upsert_profile_url(db, candidate_id=candidate_id, source="portfolio", url=body.portfolio)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    urls = list_profile_urls(db, candidate_id=candidate_id)
    return ProfileUrlsOut(
        candidate_id=candidate_id,
        github=urls.get("github"),
        linkedin=urls.get("linkedin"),
        portfolio=urls.get("portfolio"),
    )

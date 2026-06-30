"""
PATHS Backend — Organization Candidate Sourcing endpoints.

Routes (all under `/api/v1` via app.main):

  GET  /organization-candidate-sourcing/status
  GET  /organization-candidate-sourcing/candidates
  GET  /organization-candidate-sourcing/jobs/{job_id}/match
  POST /organization-candidate-sourcing/jobs/{job_id}/match/{candidate_id}/explain
  POST /organization-candidate-sourcing/jobs/{job_id}/shortlist

  POST /admin/candidate-sourcing/run-once

The org-facing routes are gated by ``get_current_hiring_org_context`` so
candidates and other non-hiring users never see other sourced
candidates.

Existing flows are not modified — this router is purely additive.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import OrgContext, get_current_hiring_org_context
from app.db.models.application import Application
from app.db.models.candidate import Candidate
from app.db.models.evidence import CandidateSource
from app.db.models.job import Job
from app.db.models.sync import CandidateJobMatch
from app.schemas.candidate_sourcing import (
    CandidateJobReasoningSchema,
    CandidateSourcingRunRequest,
    CandidateSourcingRunResultSchema,
    CandidateSourcingStatus,
    ShortlistRequest,
    ShortlistResponse,
    SourcedCandidateListResponse,
    SourcedCandidateMatchListResponse,
    SourcedCandidateMatchSchema,
    SourcedCandidateSummary,
)
from app.services.sourcing.agents import explain_candidate_job_match
from app.services.sourcing.candidate_sourcing_service import (
    CandidateSourcingService,
)
from app.services.sourcing.matchers import rank_sourced_candidates_for_job

logger = logging.getLogger(__name__)
settings = get_settings()


router = APIRouter(tags=["Organization Candidate Sourcing"])


# ── Constants ────────────────────────────────────────────────────────────


# Names of the providers used for sourced candidates. Used as the
# ``CandidateSource.source`` filter so a regular CV-imported applicant
# never shows up in the "sourced" list.
SOURCED_PLATFORMS: frozenset[str] = frozenset(
    {"mock", "linkedin_open_to_work", "openresume_open_to_work"},
)


# Candidate.source_type values that count as the platform's "open sourcing
# pool" — recruiters can shortlist them straight from the Sourcing page even
# though they are not LinkedIn-sourced. Matches `_OPEN_POOL_SOURCE_TYPES` in
# ``app.core.candidate_access`` and ``_INTERNAL_SOURCE_TYPES`` in
# ``app.api.v1.sourcing``; kept local to avoid a cross-module import cycle.
_INTERNAL_POOL_SOURCE_TYPES: frozenset[str] = frozenset(
    {"paths_profile", "imported", "uploaded", "manual"},
)


def _candidate_in_sourcing_pool(
    db: Session, *, candidate: Candidate, organization_id: UUID,
) -> bool:
    """True when this candidate is sourceable by *this* organization.

    The Sourcing page mixes two pools — the LinkedIn / external sourced
    pool (``CandidateSource.source IN SOURCED_PLATFORMS``) and the platform's
    internal pool (everything the ``/sourcing/database-candidates`` endpoint
    returns). Both are shown side-by-side; both must be shortlistable.

    This predicate is the *union* of those two list queries, so any
    candidate visible on the Sourcing page resolves to True here. Org
    scoping is preserved: a candidate privately owned by *another* org
    (``owner_organization_id`` set to a different org *and* not in the
    open pool) is rejected.
    """
    # 1) External sourced platforms — original guard.
    is_sourced = db.execute(
        select(CandidateSource.id).where(
            CandidateSource.candidate_id == candidate.id,
            CandidateSource.source.in_(list(SOURCED_PLATFORMS)),
        ).limit(1)
    ).scalar_one_or_none()
    if is_sourced is not None:
        return True

    # 2) Org already owns this candidate row (sourced into its pool).
    owner_id = getattr(candidate, "owner_organization_id", None)
    if owner_id is not None and owner_id == organization_id:
        return True

    # 3) Platform's open candidate pool — mirrors the
    #    ``/api/v1/sourcing/database-candidates`` query exactly so anything
    #    rendered there is automatically shortlistable. That query keeps a
    #    candidate when:
    #      ( source_type IS NULL  OR  source_type IN <internal types> )
    #      AND ( status = 'active' OR status IS NULL )
    raw_source_type = getattr(candidate, "source_type", None)
    source_type = (raw_source_type or "").strip()
    is_internal_source = (
        raw_source_type is None
        or source_type == ""
        or source_type in _INTERNAL_POOL_SOURCE_TYPES
    )
    cand_status_raw = getattr(candidate, "status", None)
    cand_status = (cand_status_raw or "active").strip().lower()
    is_active = cand_status_raw is None or cand_status == "active"

    # The internal pool is open across organizations *only* when the
    # candidate has no private owner. A candidate whose owner is some
    # *other* org and who isn't in the LinkedIn-sourced pool stays
    # private and is rejected above (branch 2 already returned for
    # same-org owners).
    if is_internal_source and is_active and owner_id is None:
        return True

    return False


# ── Helpers ──────────────────────────────────────────────────────────────


def _candidate_to_summary(
    c: Candidate, source: CandidateSource | None = None,
) -> SourcedCandidateSummary:
    return SourcedCandidateSummary(
        candidate_id=c.id,
        full_name=c.full_name,
        headline=c.headline,
        current_title=c.current_title,
        location_text=c.location_text,
        years_experience=c.years_experience,
        skills=list(c.skills or []),
        open_to_job_types=list(c.open_to_job_types or []),
        open_to_workplace_settings=list(c.open_to_workplace_settings or []),
        desired_job_titles=list(c.desired_job_titles or []),
        summary=c.summary,
        status=c.status,
        source={
            "source": source.source,
            "url": source.url,
            "fetched_at": source.fetched_at.isoformat() if source.fetched_at else None,
        } if source is not None else None,
        open_to_work=True,
    )


def _list_sourced_candidate_ids(
    db: Session, *, limit: int = 500,
) -> list[UUID]:
    rows = db.execute(
        select(Candidate.id)
        .join(CandidateSource, CandidateSource.candidate_id == Candidate.id)
        .where(
            Candidate.status == "active",
            CandidateSource.source.in_(list(SOURCED_PLATFORMS)),
        )
        .group_by(Candidate.id)
        .limit(limit)
    ).all()
    return [r[0] for r in rows]


def _ensure_org_owns_job(db: Session, job_id: UUID, organization_id: UUID) -> Job:
    job = db.get(Job, job_id)
    if job is None or job.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found",
        )
    return job


# ── Status ───────────────────────────────────────────────────────────────


@router.get(
    "/organization-candidate-sourcing/status",
    response_model=CandidateSourcingStatus,
)
def get_status(
    ctx: OrgContext = Depends(get_current_hiring_org_context),
):
    return CandidateSourcingStatus(
        enabled=bool(settings.candidate_sourcing_enabled),
        provider=settings.candidate_sourcing_provider,
        interval_minutes=int(settings.candidate_sourcing_interval_minutes),
        max_per_run=int(settings.candidate_sourcing_max_per_run),
        reasoning_enabled=bool(settings.candidate_sourcing_reasoning_enabled),
        reasoning_model=settings.candidate_sourcing_reasoning_model,
        metadata={
            "openrouter_configured": bool(settings.openrouter_api_key),
            "linkedin_provider_stub": bool(settings.linkedin_candidate_provider_stub),
            "default_keywords": settings.candidate_sourcing_default_keywords or "",
            "organization_id": str(ctx.organization_id),
        },
    )


# ── List sourced candidates available to this organization ───────────────


@router.get(
    "/organization-candidate-sourcing/candidates",
    response_model=SourcedCandidateListResponse,
)
def list_sourced_candidates(
    title: str | None = Query(None, description="Match against current_title / desired titles / headline."),
    skill: list[str] | None = Query(
        None, description="Repeat to filter by multiple skills.",
    ),
    location: str | None = Query(None),
    workplace: str | None = Query(None, description="remote | hybrid | onsite"),
    employment_type: str | None = Query(None),
    min_years_experience: int | None = Query(None, ge=0),
    max_years_experience: int | None = Query(None, ge=0),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
) -> SourcedCandidateListResponse:
    base = (
        select(Candidate, CandidateSource)
        .join(CandidateSource, CandidateSource.candidate_id == Candidate.id)
        .where(
            Candidate.status == "active",
            CandidateSource.source.in_(list(SOURCED_PLATFORMS)),
        )
    )
    if title:
        like = f"%{title.strip().lower()}%"
        base = base.where(
            or_(
                Candidate.current_title.ilike(like),
                Candidate.headline.ilike(like),
            )
        )
    if location:
        base = base.where(Candidate.location_text.ilike(f"%{location.strip()}%"))
    if min_years_experience is not None:
        base = base.where(
            or_(
                Candidate.years_experience.is_(None),
                Candidate.years_experience >= int(min_years_experience),
            )
        )
    if max_years_experience is not None:
        base = base.where(
            or_(
                Candidate.years_experience.is_(None),
                Candidate.years_experience <= int(max_years_experience),
            )
        )

    rows = db.execute(base.limit(limit + offset)).all()
    # Deduplicate by candidate id (CandidateSource may yield 1+ rows per candidate)
    seen: set[UUID] = set()
    pairs: list[tuple[Candidate, CandidateSource]] = []
    for row in rows:
        c, src = row[0], row[1]
        if c.id in seen:
            continue
        seen.add(c.id)
        pairs.append((c, src))

    # Apply Python-side filters that depend on ARRAY semantics.
    skill_set = {s.strip().lower() for s in (skill or []) if s and s.strip()}
    workplace_norm = (workplace or "").strip().lower() or None
    employment_norm = (employment_type or "").strip().lower() or None

    filtered: list[tuple[Candidate, CandidateSource]] = []
    for c, src in pairs:
        if skill_set:
            cand_skills = {s.lower() for s in (c.skills or []) if isinstance(s, str)}
            if not (skill_set & cand_skills):
                continue
        if workplace_norm:
            cand_wp = {w.lower() for w in (c.open_to_workplace_settings or []) if isinstance(w, str)}
            if cand_wp and workplace_norm not in cand_wp:
                continue
        if employment_norm:
            cand_et = {e.lower() for e in (c.open_to_job_types or []) if isinstance(e, str)}
            if cand_et and employment_norm not in cand_et:
                continue
        filtered.append((c, src))

    paginated = filtered[offset : offset + limit]
    items = [_candidate_to_summary(c, src) for c, src in paginated]
    return SourcedCandidateListResponse(
        organization_id=ctx.organization_id,
        total=len(filtered),
        items=items,
        filters={
            "title": title,
            "skills": list(skill or []),
            "location": location,
            "workplace": workplace,
            "employment_type": employment_type,
            "min_years_experience": min_years_experience,
            "max_years_experience": max_years_experience,
        },
    )


# ── Job-aware match endpoint (per-organization, per-job) ─────────────────


@router.get(
    "/organization-candidate-sourcing/jobs/{job_id}/match",
    response_model=SourcedCandidateMatchListResponse,
)
def match_sourced_candidates_for_job(
    job_id: UUID,
    top_k: int = Query(10, ge=1, le=50),
    location: str | None = Query(None),
    workplace: list[str] | None = Query(None),
    employment_type: list[str] | None = Query(None),
    min_score: float = Query(0.0, ge=0.0, le=100.0),
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
) -> SourcedCandidateMatchListResponse:
    _ensure_org_owns_job(db, job_id, ctx.organization_id)

    pool = _list_sourced_candidate_ids(db, limit=500)
    if not pool:
        return SourcedCandidateMatchListResponse(
            organization_id=ctx.organization_id,
            job_id=job_id,
            total=0,
            top_k=top_k,
            items=[],
            filters={
                "location": location,
                "workplace": list(workplace or []),
                "employment_type": list(employment_type or []),
                "min_score": min_score,
            },
        )

    matches = rank_sourced_candidates_for_job(
        db,
        job_id=job_id,
        candidate_ids=pool,
        top_k=top_k,
        workplace_settings=list(workplace or []),
        location=location,
        employment_types=list(employment_type or []),
        min_score=float(min_score),
    )

    items = [
        SourcedCandidateMatchSchema(
            candidate_id=m.candidate_id,
            score=m.score,
            vector_score=m.vector_score,
            skill_overlap_score=m.skill_overlap_score,
            matched_skills=m.matched_skills,
            missing_required_skills=m.missing_required_skills,
            workplace_match=m.workplace_match,
            location_match=m.location_match,
            candidate=SourcedCandidateSummary(
                candidate_id=m.candidate_id,
                **{
                    k: v for k, v in m.candidate.items()
                    if k in {
                        "full_name", "headline", "current_title",
                        "location_text", "years_experience", "skills",
                        "open_to_job_types", "open_to_workplace_settings",
                        "desired_job_titles", "summary", "status",
                    }
                },
                source=m.source,
                open_to_work=True,
            ),
            source=m.source,
        )
        for m in matches
    ]
    return SourcedCandidateMatchListResponse(
        organization_id=ctx.organization_id,
        job_id=job_id,
        total=len(items),
        top_k=top_k,
        items=items,
        filters={
            "location": location,
            "workplace": list(workplace or []),
            "employment_type": list(employment_type or []),
            "min_score": min_score,
        },
    )


# ── Reasoning explanation ────────────────────────────────────────────────


@router.post(
    "/organization-candidate-sourcing/jobs/{job_id}/match/{candidate_id}/explain",
    response_model=CandidateJobReasoningSchema,
)
def explain_match(
    job_id: UUID,
    candidate_id: UUID,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
) -> CandidateJobReasoningSchema:
    _ensure_org_owns_job(db, job_id, ctx.organization_id)

    # Compute the same score the listing endpoint produces, on demand.
    matches = rank_sourced_candidates_for_job(
        db,
        job_id=job_id,
        candidate_ids=[candidate_id],
        top_k=1,
    )
    if not matches:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate is not available to your organization.",
        )
    m = matches[0]

    reasoning = explain_candidate_job_match(
        db,
        candidate_id=candidate_id,
        job_id=job_id,
        overall_score=m.score,
        matched_skills=m.matched_skills,
        missing_required_skills=m.missing_required_skills,
    )

    # Persist (best-effort) into the existing CandidateJobMatch table.
    try:
        existing = db.execute(
            select(CandidateJobMatch).where(
                CandidateJobMatch.candidate_id == candidate_id,
                CandidateJobMatch.job_id == job_id,
                CandidateJobMatch.model_version == "candidate_sourcing_v1",
            ).limit(1)
        ).scalar_one_or_none()
        evidence_payload: dict[str, Any] = {
            "matched_skills": m.matched_skills,
            "missing_required_skills": m.missing_required_skills,
            "decision": reasoning.decision,
            "vector_score": m.vector_score,
            "skill_overlap_score": m.skill_overlap_score,
            "fallback": reasoning.fallback,
            "model": reasoning.model,
            "strengths": reasoning.strengths,
            "gaps": reasoning.gaps,
            "red_flags": reasoning.red_flags,
        }
        if existing is None:
            db.add(
                CandidateJobMatch(
                    candidate_id=candidate_id,
                    job_id=job_id,
                    overall_score=m.score,
                    semantic_score=m.vector_score,
                    skill_score=m.skill_overlap_score,
                    explanation=reasoning.summary,
                    evidence=evidence_payload,
                    model_version="candidate_sourcing_v1",
                )
            )
        else:
            existing.overall_score = m.score
            existing.semantic_score = m.vector_score
            existing.skill_score = m.skill_overlap_score
            existing.explanation = reasoning.summary
            existing.evidence = evidence_payload
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("[CandidateSourcing] could not persist reasoning")

    return CandidateJobReasoningSchema(**reasoning.to_dict())


# ── Shortlist (add sourced candidate to a job pipeline) ──────────────────


@router.post(
    "/organization-candidate-sourcing/jobs/{job_id}/shortlist",
    response_model=ShortlistResponse,
)
def shortlist_sourced_candidate(
    job_id: UUID,
    body: ShortlistRequest,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
) -> ShortlistResponse:
    if body.job_id != job_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="job_id mismatch",
        )
    _ensure_org_owns_job(db, job_id, ctx.organization_id)

    candidate = db.get(Candidate, body.candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Every candidate the Sourcing page renders must be shortlistable: both
    # LinkedIn/external sourced profiles and the platform's open candidate
    # pool (signed-up / imported / uploaded / manual). Org scoping is
    # enforced inside `_candidate_in_sourcing_pool`.
    if not _candidate_in_sourcing_pool(
        db, candidate=candidate, organization_id=ctx.organization_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Candidate is not part of the sourcing pool for your organization.",
        )

    stage_code = (body.stage_code or "sourced").strip()

    application = db.execute(
        select(Application).where(
            Application.candidate_id == body.candidate_id,
            Application.job_id == job_id,
        ).limit(1)
    ).scalar_one_or_none()
    created = False
    if application is None:
        application = Application(
            candidate_id=body.candidate_id,
            job_id=job_id,
            application_type="sourced",
            source_channel="open_to_work_sourcing",
            current_stage_code=stage_code,
            overall_status="active",
        )
        db.add(application)
        created = True
    else:
        application.current_stage_code = stage_code
        application.overall_status = "active"
    db.flush()
    db.commit()

    return ShortlistResponse(
        candidate_id=body.candidate_id,
        job_id=job_id,
        application_id=application.id,
        stage_code=application.current_stage_code,
        overall_status=application.overall_status,
        note=body.note,
        created=created,
    )


# ── Admin: trigger one sourcing run ──────────────────────────────────────


from app.core.dependencies import require_platform_admin  # noqa: E402

admin_router = APIRouter(
    tags=["Admin — Candidate Sourcing"],
    dependencies=[Depends(require_platform_admin)],
)


@admin_router.post(
    "/admin/candidate-sourcing/run-once",
    response_model=CandidateSourcingRunResultSchema,
    summary="Trigger one immediate Open-to-Work sourcing run.",
)
async def admin_run_once(
    body: CandidateSourcingRunRequest = Body(default_factory=CandidateSourcingRunRequest),
):
    service = CandidateSourcingService()
    try:
        result = await service.run_sourcing(
            limit=body.limit,
            provider_name=body.provider,
            keywords=body.keywords,
            location=body.location,
            admin_override=False,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("[CandidateSourcing] admin run failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"sourcing_failed: {exc}",
        ) from exc
    return CandidateSourcingRunResultSchema(
        source_platform=result.source_platform,
        requested_limit=result.requested_limit,
        started_at=result.started_at or datetime.now(timezone.utc),
        finished_at=result.finished_at,
        fetched_count=result.fetched_count,
        valid_count=result.valid_count,
        inserted_count=result.inserted_count,
        updated_count=result.updated_count,
        skipped_count=result.skipped_count,
        failed_count=result.failed_count,
        graph_synced_count=result.graph_synced_count,
        vector_synced_count=result.vector_synced_count,
        candidate_ids=list(result.candidate_ids),
        errors=list(result.errors),
        status=result.status,
    )


@admin_router.get(
    "/admin/candidate-sourcing/status",
    response_model=CandidateSourcingStatus,
)
def admin_status() -> CandidateSourcingStatus:
    return CandidateSourcingStatus(
        enabled=bool(settings.candidate_sourcing_enabled),
        provider=settings.candidate_sourcing_provider,
        interval_minutes=int(settings.candidate_sourcing_interval_minutes),
        max_per_run=int(settings.candidate_sourcing_max_per_run),
        reasoning_enabled=bool(settings.candidate_sourcing_reasoning_enabled),
        reasoning_model=settings.candidate_sourcing_reasoning_model,
        metadata={
            "openrouter_configured": bool(settings.openrouter_api_key),
            "linkedin_provider_stub": bool(settings.linkedin_candidate_provider_stub),
            "default_keywords": settings.candidate_sourcing_default_keywords or "",
        },
    )

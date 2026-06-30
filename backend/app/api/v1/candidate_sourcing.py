"""
PATHS Backend — Candidate Sourcing & Pool API surface.

All routes require an authenticated organization_member with an org in
status='active'. Tenant isolation is enforced at the JWT level:
`require_active_org_status` resolves the caller's organization_id; routes
never accept it from the body or path. Pool/config records are then
double-checked against ctx.organization_id before any read or write.

Endpoints:

  Settings (org-level defaults)
    GET    /api/v1/organization/candidate-source-settings
    PUT    /api/v1/organization/candidate-source-settings
    GET    /api/v1/organization/candidate-source-counts
    GET    /api/v1/candidate-source-catalog        (static labels/descriptions)

  Per-job
    GET    /api/v1/jobs/{job_id}/candidate-pool/config
    PUT    /api/v1/jobs/{job_id}/candidate-pool/config
    POST   /api/v1/jobs/{job_id}/candidate-pool/preview
    POST   /api/v1/jobs/{job_id}/candidate-pool/build
    GET    /api/v1/jobs/{job_id}/candidate-pool/runs           (audit list)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.candidate_sources import (
    SOURCE_DESCRIPTIONS,
    SOURCE_LABELS,
    SourceType,
)
from app.core.database import get_db
from app.core.dependencies import OrgContext, require_active_org_status
from app.db.models.candidate_sourcing import (
    CandidatePoolMember,
    CandidatePoolRun,
    JobCandidatePoolConfig,
    OrganizationCandidateSourceSettings,
)
from app.db.models.job import Job
from app.services.candidate_pool import CandidatePoolBuilderService

router = APIRouter(tags=["candidate-sourcing"])


# ── Pydantic schemas ─────────────────────────────────────────────────────


class SourceCatalogEntry(BaseModel):
    source_type: str
    label: str
    description: str


class SourceCatalogResponse(BaseModel):
    sources: list[SourceCatalogEntry]


class OrgSourceSettingsOut(BaseModel):
    organization_id: UUID
    use_paths_profiles_default: bool
    use_sourced_candidates_default: bool
    use_uploaded_candidates_default: bool
    use_job_fair_candidates_default: bool
    use_ats_candidates_default: bool
    default_top_k: int
    default_min_profile_completeness: int
    default_min_evidence_confidence: int
    updated_at: Optional[datetime] = None
    updated_by_user_id: Optional[UUID] = None


class OrgSourceSettingsUpdate(BaseModel):
    use_paths_profiles_default: Optional[bool] = None
    use_sourced_candidates_default: Optional[bool] = None
    use_uploaded_candidates_default: Optional[bool] = None
    use_job_fair_candidates_default: Optional[bool] = None
    use_ats_candidates_default: Optional[bool] = None
    default_top_k: Optional[int] = Field(None, ge=1, le=500)
    default_min_profile_completeness: Optional[int] = Field(None, ge=0, le=100)
    default_min_evidence_confidence: Optional[int] = Field(None, ge=0, le=100)


class SourceCountEntry(BaseModel):
    source_type: str
    label: str
    count: int


class SourceCountsResponse(BaseModel):
    organization_id: UUID
    counts: list[SourceCountEntry]
    total: int


class JobPoolConfigOut(BaseModel):
    job_id: UUID
    organization_id: UUID
    use_paths_profiles: bool
    use_sourced_candidates: bool
    use_uploaded_candidates: bool
    use_job_fair_candidates: bool
    use_ats_candidates: bool
    top_k: int
    min_profile_completeness: int
    min_evidence_confidence: int
    filters_json: Optional[dict] = None
    updated_at: Optional[datetime] = None


class JobPoolConfigUpdate(BaseModel):
    use_paths_profiles: Optional[bool] = None
    use_sourced_candidates: Optional[bool] = None
    use_uploaded_candidates: Optional[bool] = None
    use_job_fair_candidates: Optional[bool] = None
    use_ats_candidates: Optional[bool] = None
    top_k: Optional[int] = Field(None, ge=1, le=500)
    min_profile_completeness: Optional[int] = Field(None, ge=0, le=100)
    min_evidence_confidence: Optional[int] = Field(None, ge=0, le=100)
    filters_json: Optional[dict] = None


class PoolPreviewOut(BaseModel):
    job_id: UUID
    organization_id: UUID
    config_snapshot: dict
    source_breakdown: dict[str, int]
    total_candidates_found: int
    duplicates_removed: int
    excluded_incomplete_profile: int
    excluded_low_evidence: int
    eligible_candidates: int


class PoolBuildOut(BaseModel):
    pool_run_id: UUID
    job_id: UUID
    organization_id: UUID
    eligible_candidates: int
    excluded_candidates: int
    duplicates_removed: int
    source_breakdown: dict[str, int]
    status: str


class PoolRunSummary(BaseModel):
    pool_run_id: UUID
    job_id: UUID
    eligible_candidates: int
    excluded_candidates: int
    duplicates_removed: int
    source_breakdown: Optional[dict[str, int]] = None
    status: str
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class PoolRunListResponse(BaseModel):
    runs: list[PoolRunSummary]


# ── Helpers ──────────────────────────────────────────────────────────────


def _settings_to_dto(row: OrganizationCandidateSourceSettings) -> OrgSourceSettingsOut:
    return OrgSourceSettingsOut(
        organization_id=row.organization_id,
        use_paths_profiles_default=row.use_paths_profiles_default,
        use_sourced_candidates_default=row.use_sourced_candidates_default,
        use_uploaded_candidates_default=row.use_uploaded_candidates_default,
        use_job_fair_candidates_default=row.use_job_fair_candidates_default,
        use_ats_candidates_default=row.use_ats_candidates_default,
        default_top_k=row.default_top_k,
        default_min_profile_completeness=row.default_min_profile_completeness,
        default_min_evidence_confidence=row.default_min_evidence_confidence,
        updated_at=row.updated_at,
        updated_by_user_id=row.updated_by_user_id,
    )


def _config_to_dto(row: JobCandidatePoolConfig) -> JobPoolConfigOut:
    return JobPoolConfigOut(
        job_id=row.job_id,
        organization_id=row.organization_id,
        use_paths_profiles=row.use_paths_profiles,
        use_sourced_candidates=row.use_sourced_candidates,
        use_uploaded_candidates=row.use_uploaded_candidates,
        use_job_fair_candidates=row.use_job_fair_candidates,
        use_ats_candidates=row.use_ats_candidates,
        top_k=row.top_k,
        min_profile_completeness=row.min_profile_completeness,
        min_evidence_confidence=row.min_evidence_confidence,
        filters_json=row.filters_json,
        updated_at=row.updated_at,
    )


def _ensure_job_in_org(db: Session, job_id: UUID, org_id: UUID) -> Job:
    job = db.query(Job).filter(Job.id == job_id).one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if getattr(job, "organization_id", None) != org_id:
        # Tenant isolation: never reveal that the job exists in another org.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


# ── Catalog (static) ─────────────────────────────────────────────────────


@router.get(
    "/candidate-source-catalog",
    response_model=SourceCatalogResponse,
)
def get_source_catalog():
    """Static labels + descriptions for every source type. The frontend
    pulls this so source labels are not duplicated across the codebase."""
    return SourceCatalogResponse(
        sources=[
            SourceCatalogEntry(
                source_type=s.value,
                label=SOURCE_LABELS[s],
                description=SOURCE_DESCRIPTIONS[s],
            )
            for s in SourceType
        ]
    )


# ── Org-level settings ──────────────────────────────────────────────────


@router.get(
    "/organization/candidate-source-settings",
    response_model=OrgSourceSettingsOut,
)
def get_org_source_settings(
    ctx: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
):
    svc = CandidatePoolBuilderService(db)
    row = svc.get_or_create_org_settings(ctx.organization_id)
    return _settings_to_dto(row)


@router.put(
    "/organization/candidate-source-settings",
    response_model=OrgSourceSettingsOut,
)
def update_org_source_settings(
    body: OrgSourceSettingsUpdate,
    ctx: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
):
    svc = CandidatePoolBuilderService(db)
    row = svc.get_or_create_org_settings(ctx.organization_id)
    payload = body.model_dump(exclude_unset=True)
    for field_name, value in payload.items():
        setattr(row, field_name, value)
    row.updated_by_user_id = ctx.user.id
    db.commit()
    db.refresh(row)
    return _settings_to_dto(row)


@router.get(
    "/organization/candidate-source-counts",
    response_model=SourceCountsResponse,
)
def get_source_counts(
    ctx: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
):
    svc = CandidatePoolBuilderService(db)
    counts = svc.source_counts_for_org(ctx.organization_id)
    entries = [
        SourceCountEntry(
            source_type=s.value,
            label=SOURCE_LABELS[s],
            count=counts.get(s.value, 0),
        )
        for s in SourceType
    ]
    return SourceCountsResponse(
        organization_id=ctx.organization_id,
        counts=entries,
        total=sum(c.count for c in entries),
    )


# ── Per-job pool config ─────────────────────────────────────────────────


@router.get(
    "/jobs/{job_id}/candidate-pool/config",
    response_model=JobPoolConfigOut,
)
def get_job_pool_config(
    job_id: UUID,
    ctx: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
):
    _ensure_job_in_org(db, job_id, ctx.organization_id)
    svc = CandidatePoolBuilderService(db)
    config = svc.get_or_create_job_config(job_id, ctx.organization_id)
    return _config_to_dto(config)


@router.put(
    "/jobs/{job_id}/candidate-pool/config",
    response_model=JobPoolConfigOut,
)
def update_job_pool_config(
    job_id: UUID,
    body: JobPoolConfigUpdate,
    ctx: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
):
    _ensure_job_in_org(db, job_id, ctx.organization_id)
    svc = CandidatePoolBuilderService(db)
    config = svc.get_or_create_job_config(job_id, ctx.organization_id)
    payload = body.model_dump(exclude_unset=True)
    for field_name, value in payload.items():
        setattr(config, field_name, value)
    config.created_by_user_id = config.created_by_user_id or ctx.user.id
    db.commit()
    db.refresh(config)
    return _config_to_dto(config)


@router.post(
    "/jobs/{job_id}/candidate-pool/preview",
    response_model=PoolPreviewOut,
)
def preview_job_pool(
    job_id: UUID,
    ctx: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
):
    _ensure_job_in_org(db, job_id, ctx.organization_id)
    svc = CandidatePoolBuilderService(db)
    preview = svc.preview(job_id, ctx.organization_id)
    return PoolPreviewOut(
        job_id=preview.job_id,
        organization_id=preview.organization_id,
        config_snapshot=preview.config_snapshot,
        source_breakdown=preview.source_breakdown,
        total_candidates_found=preview.total_candidates_found,
        duplicates_removed=preview.duplicates_removed,
        excluded_incomplete_profile=preview.excluded_incomplete_profile,
        excluded_low_evidence=preview.excluded_low_evidence,
        eligible_candidates=preview.eligible_candidates,
    )


@router.post(
    "/jobs/{job_id}/candidate-pool/build",
    response_model=PoolBuildOut,
    status_code=status.HTTP_201_CREATED,
)
def build_job_pool(
    job_id: UUID,
    ctx: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
):
    _ensure_job_in_org(db, job_id, ctx.organization_id)
    svc = CandidatePoolBuilderService(db)
    result = svc.build(
        job_id=job_id,
        organization_id=ctx.organization_id,
        created_by_user_id=ctx.user.id,
    )
    return PoolBuildOut(
        pool_run_id=result.pool_run_id,
        job_id=result.job_id,
        organization_id=result.organization_id,
        eligible_candidates=result.eligible_candidates,
        excluded_candidates=result.excluded_candidates,
        duplicates_removed=result.duplicates_removed,
        source_breakdown=result.source_breakdown,
        status=result.status,
    )


@router.get(
    "/jobs/{job_id}/candidate-pool/runs",
    response_model=PoolRunListResponse,
)
def list_pool_runs(
    job_id: UUID,
    ctx: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
):
    _ensure_job_in_org(db, job_id, ctx.organization_id)
    runs = (
        db.query(CandidatePoolRun)
        .filter(CandidatePoolRun.job_id == job_id)
        .filter(CandidatePoolRun.organization_id == ctx.organization_id)
        .order_by(CandidatePoolRun.created_at.desc())
        .limit(20)
        .all()
    )
    return PoolRunListResponse(
        runs=[
            PoolRunSummary(
                pool_run_id=r.id,
                job_id=r.job_id,
                eligible_candidates=r.eligible_candidates,
                excluded_candidates=r.excluded_candidates,
                duplicates_removed=r.duplicates_removed,
                source_breakdown=r.source_breakdown,
                status=r.status,
                created_at=r.created_at,
                completed_at=r.completed_at,
            )
            for r in runs
        ]
    )

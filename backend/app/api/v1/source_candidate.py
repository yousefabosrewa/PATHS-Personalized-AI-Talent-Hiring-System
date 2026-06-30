"""
PATHS Backend — Recruiter "Source Candidate" endpoints (fix6.md).

Mounted under ``/api/v1`` so all routes live at
``/api/v1/recruiter/source-candidate/...``. Every endpoint is gated by
``require_active_org_status`` and ``get_current_hiring_org_context`` so
only recruiters/admins/hiring managers in an active org may fetch or
import external candidates.

Routes:

  POST /recruiter/source-candidate/external/fetch
       Fetch up to 5 external technical open-to-work candidates and
       persist them as preview rows.

  POST /recruiter/source-candidate/external/{external_candidate_id}/import
       Import a fetched candidate into the candidate database.

  POST /recruiter/source-candidate/external/import-batch
       Import multiple candidates from a single batch in one call.

  GET  /recruiter/source-candidate/database
       List real candidates already in the database (scoped to org pool).

  GET  /recruiter/source-candidate/external/batches
       Past fetch batches — most-recent first.
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import (
    OrgContext,
    get_current_hiring_org_context,
    require_active_org_status,
)
from app.db.models.candidate import Candidate
from app.db.models.evidence import CandidateSource
from app.db.models.external_candidate import (
    ExternalCandidate,
    ExternalCandidateBatch,
)
from app.services.source_candidate import (
    SourceCandidateService,
    SourcingProviderError,
)
from app.db.models.job import Job
from app.services.matching_workspace.semantic import semantic_search
from app.services.source_candidate.find_talent_ranker import (
    TalentCandidate,
    distill_search_query,
    rank_candidates,
)
from app.services.source_candidate.providers import get_sourcing_provider

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/recruiter/source-candidate",
    tags=["Source Candidate"],
)


# ── Pydantic schemas ─────────────────────────────────────────────────────


class ExternalFetchRequest(BaseModel):
    source: Literal[
        "linkedin_mcp", "csv_export", "external_recruitment_platform"
    ] = "linkedin_mcp"
    count: int = Field(default=5, ge=1, le=5)
    role_category: Literal["technical"] = "technical"
    keywords: list[str] | None = None
    location: str | None = None


class ExternalCandidateOut(BaseModel):
    id: str
    full_name: str | None = None
    headline: str | None = None
    current_title: str | None = None
    current_company: str | None = None
    location: str | None = None
    profile_url: str | None = None
    email: str | None = None
    skills: list[str] = Field(default_factory=list)
    open_to_work_signal: bool | None = None
    open_to_work_evidence: str | None = None
    technical_role_evidence: str | None = None
    import_status: str = "ready_to_import"
    imported_candidate_id: str | None = None
    provider: str
    created_at: datetime


class ExternalFetchResponse(BaseModel):
    batch_id: str
    provider: str
    candidates: list[ExternalCandidateOut]


class FindTalentRequest(BaseModel):
    # Long briefs are welcome — paste the role, requirements and skills. The
    # agent distills a concise LinkedIn search query from this and uses the
    # full text for semantic/RAG ranking.
    query: str = Field(min_length=1, max_length=6000)
    source: Literal["linkedin", "all"] = "linkedin"
    job_id: str | None = None
    count: int = Field(default=8, ge=1, le=10)
    location: str | None = None
    # Verify each LinkedIn candidate's public "Open to work" badge (and pull
    # real skills) by reading their profile. Slower, but labels + sorts OTW.
    verify_open_to_work: bool = True


class FindTalentCandidateOut(BaseModel):
    rank: int
    score: float
    source: Literal["linkedin", "database"]
    external_candidate_id: str | None = None
    candidate_id: str | None = None
    full_name: str | None = None
    headline: str | None = None
    current_title: str | None = None
    current_company: str | None = None
    location: str | None = None
    profile_url: str | None = None
    skills: list[str] = Field(default_factory=list)
    explanation: str = ""
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    open_to_work: bool = False
    open_to_work_status: Literal["verified", "not_detected", "unverified"] = "unverified"
    open_to_work_evidence: str | None = None
    import_status: str = "ready_to_import"
    imported_candidate_id: str | None = None


class FindTalentResponse(BaseModel):
    batch_id: str | None = None
    job_id: str | None = None
    provider_available: bool = True
    message: str | None = None
    results: list[FindTalentCandidateOut] = Field(default_factory=list)


class ImportResponseOut(BaseModel):
    status: Literal["imported", "duplicate", "already_imported"]
    candidate_id: str
    created_account: bool
    duplicate_detected: bool
    message: str


class ImportBatchRequest(BaseModel):
    batch_id: str | None = None
    candidate_ids: list[str]


class ImportBatchResultItem(BaseModel):
    external_candidate_id: str
    status: Literal["imported", "duplicate", "already_imported", "error"]
    candidate_id: str | None = None
    message: str


class ImportBatchResponse(BaseModel):
    results: list[ImportBatchResultItem]


class DatabaseCandidateOut(BaseModel):
    candidate_id: str
    full_name: str
    current_title: str | None = None
    location_text: str | None = None
    headline: str | None = None
    summary: str | None = None
    years_experience: int | None = None
    skills: list[str] = Field(default_factory=list)
    source_type: str | None = None
    source_platform: str | None = None
    status: str | None = None
    profile_completion_status: str | None = None
    created_at: datetime | None = None


class DatabaseCandidateListOut(BaseModel):
    total: int
    items: list[DatabaseCandidateOut]


class BatchOut(BaseModel):
    id: str
    provider: str
    requested_count: int
    fetched_count: int
    status: str
    location: str | None = None
    error_message: str | None = None
    created_at: datetime


class BatchListOut(BaseModel):
    items: list[BatchOut]


# ── Helpers ──────────────────────────────────────────────────────────────


def _serialize_external(row: ExternalCandidate) -> ExternalCandidateOut:
    return ExternalCandidateOut(
        id=str(row.id),
        full_name=row.full_name,
        headline=row.headline,
        current_title=row.current_title,
        current_company=row.current_company,
        location=row.location,
        profile_url=row.profile_url,
        email=row.email,
        skills=list(row.skills or []),
        open_to_work_signal=row.open_to_work_signal,
        open_to_work_evidence=row.open_to_work_evidence,
        technical_role_evidence=row.technical_role_evidence,
        import_status=row.import_status,
        imported_candidate_id=str(row.imported_candidate_id) if row.imported_candidate_id else None,
        provider=row.provider,
        created_at=row.created_at,
    )


def _username_from_url(url: str | None) -> str | None:
    """Extract the LinkedIn vanity/username from a /in/<username>/ profile URL."""
    if not url or "/in/" not in url:
        return None
    tail = url.rstrip("/").split("/in/", 1)[-1].split("/")[0]
    if not tail:
        return None
    try:
        from urllib.parse import unquote

        return unquote(tail)
    except Exception:  # noqa: BLE001
        return tail


def _profile_completion(cand: Candidate) -> str:
    has_skills = bool(cand.skills)
    has_title = bool(cand.current_title or cand.headline)
    if has_skills and has_title and cand.email:
        return "complete"
    if has_title or has_skills:
        return "partial"
    return "incomplete"


def _serialize_database(cand: Candidate) -> DatabaseCandidateOut:
    return DatabaseCandidateOut(
        candidate_id=str(cand.id),
        full_name=cand.full_name or "—",
        current_title=cand.current_title,
        location_text=cand.location_text,
        headline=cand.headline,
        summary=cand.summary,
        years_experience=cand.years_experience,
        skills=list(cand.skills or [])[:30],
        source_type=cand.source_type,
        source_platform=cand.source_platform,
        status=cand.status,
        profile_completion_status=_profile_completion(cand),
        created_at=cand.created_at,
    )


# ── Routes ───────────────────────────────────────────────────────────────


@router.post(
    "/external/fetch",
    response_model=ExternalFetchResponse,
    status_code=status.HTTP_200_OK,
)
async def fetch_external_candidates(
    body: ExternalFetchRequest,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    _: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
) -> ExternalFetchResponse:
    """Fetch up to 5 external open-to-work technical candidates (preview)."""
    service = SourceCandidateService()
    try:
        result = await service.fetch_batch(
            db,
            organization_id=ctx.organization_id,
            requested_by_user_id=ctx.user.id,
            provider_name=body.source,
            count=body.count,
            keywords=body.keywords,
            location=body.location,
        )
    except SourcingProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return ExternalFetchResponse(
        batch_id=str(result.batch_id),
        provider=body.source,
        candidates=[_serialize_external(c) for c in result.items],
    )


@router.post(
    "/find-talent",
    response_model=FindTalentResponse,
    status_code=status.HTTP_200_OK,
)
async def find_talent(
    body: FindTalentRequest,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    _: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
) -> FindTalentResponse:
    """Source candidates from LinkedIn (and optionally the DB), then rank them
    against the target job / requirements with the sourcing agent.

    Agentic RAG: an agent distills a concise LinkedIn query from the (possibly
    long) requirements brief, candidates are retrieved from LinkedIn and — for
    "All sources" — from the candidate vector index via semantic search, then
    the agent ranks the merged pool against the full requirements."""
    job_uuid: uuid.UUID | None = None
    if body.job_id:
        try:
            job_uuid = uuid.UUID(body.job_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid job_id") from exc

    try:
        return await _run_find_talent(db, ctx=ctx, body=body, job_uuid=job_uuid)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        # Never let an unhandled 500 escape — its response carries no CORS
        # headers, which the browser surfaces as "Failed to fetch". Convert to
        # a clean, CORS-safe error instead.
        logger.exception("[FindTalent] unexpected error")
        raise HTTPException(
            status_code=500,
            detail="Find Talent hit an unexpected error. Please try again.",
        ) from exc


# Generic place words that shouldn't, on their own, make two locations "match"
# (e.g. "Greater Cairo Area" vs "York Area").
_LOC_STOPWORDS = {
    "area", "greater", "metropolitan", "metro", "region", "city", "town",
    "district", "province", "state", "county", "of", "the", "and", "el",
}


def _loc_tokens(value: str | None) -> set[str]:
    return {
        t
        for t in re.split(r"[^a-z0-9]+", (value or "").lower())
        if len(t) > 1
    }


def _location_matches(candidate_location: str | None, query_location: str) -> bool:
    """True when a candidate is "from" the requested location.

    Matching is token-based and fuzzy so "Cairo" matches "Greater Cairo Area,
    Egypt" and vice-versa. A candidate with no known location cannot be
    confirmed to be there, so it is excluded while a location filter is active.
    """
    q = _loc_tokens(query_location)
    if not q:
        return True  # no location specified → no filter
    cand = _loc_tokens(candidate_location)
    if not cand:
        return False  # unknown location: can't confirm "from there"
    significant = q - _LOC_STOPWORDS or q
    return bool(significant & cand)


async def _run_find_talent(
    db: Session,
    *,
    ctx: OrgContext,
    body: FindTalentRequest,
    job_uuid: uuid.UUID | None,
) -> FindTalentResponse:
    service = SourceCandidateService()
    ext_by_key: dict[str, ExternalCandidate] = {}
    db_by_key: dict[str, Candidate] = {}
    pool: list[TalentCandidate] = []
    batch_id: str | None = None
    provider_available = True
    message: str | None = None

    # Agentic retrieval: distill a concise LinkedIn search query from the
    # (possibly long) requirements brief — LinkedIn search needs keywords,
    # not paragraphs.
    job_title: str | None = None
    if job_uuid is not None:
        job = db.get(Job, job_uuid)
        if job is not None and job.organization_id == ctx.organization_id:
            job_title = job.title
    search_keywords = distill_search_query(body.query, job_title=job_title)

    # ── 1. LinkedIn outbound (both "linkedin" and "all" hit the MCP) ──
    try:
        result = await service.fetch_batch(
            db,
            organization_id=ctx.organization_id,
            requested_by_user_id=ctx.user.id,
            provider_name="linkedin_mcp",
            count=body.count,
            keywords=[search_keywords] if search_keywords else [body.query],
            location=body.location,
            apply_technical_filter=False,
            max_count=10,
        )
        batch_id = str(result.batch_id)
        for row in result.items:
            ext_by_key[f"ext:{row.id}"] = row
    except SourcingProviderError as exc:
        provider_available = False
        message = str(exc)
        logger.warning("[FindTalent] LinkedIn provider unavailable: %s", exc)

    # ── 1b. Verify public Open-to-Work badge + enrich skills (per profile) ──
    # Reading each profile is the slow part, so fan out with bounded
    # concurrency (each call uses its own MCP session) instead of serially.
    if body.verify_open_to_work and ext_by_key:
        provider = get_sourcing_provider("linkedin_mcp")
        targets = [
            (row, _username_from_url(row.profile_url))
            for row in ext_by_key.values()
        ]
        targets = [(row, user) for row, user in targets if user]
        if targets:
            sem = asyncio.Semaphore(3)

            async def _verify(row: ExternalCandidate, username: str):
                async with sem:
                    return row, await provider.fetch_profile_details(username=username)

            outcomes = await asyncio.gather(
                *[_verify(row, user) for row, user in targets],
                return_exceptions=True,
            )
            for outcome in outcomes:
                if isinstance(outcome, BaseException):
                    continue
                row, details = outcome
                if not details:
                    continue
                row.open_to_work_signal = bool(details.get("open_to_work"))
                evidence = details.get("open_to_work_evidence")
                if evidence:
                    row.open_to_work_evidence = str(evidence)[:250]
                if details.get("skills"):
                    row.skills = list(details["skills"])[:30]
            try:
                db.commit()
            except Exception:  # noqa: BLE001
                db.rollback()

    # Build the LinkedIn pool (with enriched skills where available).
    for key, row in ext_by_key.items():
        pool.append(
            TalentCandidate(
                key=key,
                full_name=row.full_name,
                headline=row.headline,
                current_title=row.current_title,
                current_company=row.current_company,
                location=row.location,
                skills=list(row.skills or []),
                source="linkedin",
            )
        )

    # ── 2. Database candidates via SEMANTIC (vector) search — "All sources" ──
    if body.source == "all":
        try:
            sem = semantic_search(
                db,
                org_id=ctx.organization_id,
                query=body.query,
                source="all",
                limit=15,
            )
            for item in sem.get("results", []):
                cid = item.get("candidate_id")
                if not cid:
                    continue
                try:
                    cand = db.get(Candidate, uuid.UUID(str(cid)))
                except ValueError:
                    cand = None
                if cand is None:
                    continue
                key = f"db:{cand.id}"
                if key in db_by_key:
                    continue
                db_by_key[key] = cand
                pool.append(
                    TalentCandidate(
                        key=key,
                        full_name=cand.full_name,
                        headline=cand.headline,
                        current_title=cand.current_title,
                        current_company=None,
                        location=cand.location_text,
                        skills=list(cand.skills or []),
                        source="database",
                    )
                )
        except Exception:  # noqa: BLE001
            logger.exception("[FindTalent] semantic DB search failed")

    if not pool:
        return FindTalentResponse(
            batch_id=batch_id,
            job_id=body.job_id,
            provider_available=provider_available,
            message=message
            or "No candidates were returned for this search. Try a broader query.",
            results=[],
        )

    # ── 3. Rank the whole pool against the job / query ──
    ranked = rank_candidates(db, candidates=pool, query=body.query, job_id=job_uuid)

    results: list[FindTalentCandidateOut] = []
    for r in ranked:
        if r.key in ext_by_key:
            row = ext_by_key[r.key]
            otw = bool(row.open_to_work_signal)
            otw_status = (
                ("verified" if otw else "not_detected")
                if body.verify_open_to_work
                else "unverified"
            )
            results.append(
                FindTalentCandidateOut(
                    rank=0,
                    score=r.score,
                    source="linkedin",
                    external_candidate_id=str(row.id),
                    candidate_id=str(row.imported_candidate_id) if row.imported_candidate_id else None,
                    full_name=row.full_name,
                    headline=row.headline,
                    current_title=row.current_title,
                    current_company=row.current_company,
                    location=row.location,
                    profile_url=row.profile_url,
                    skills=list(row.skills or []),
                    explanation=r.explanation,
                    matched_skills=r.matched_skills,
                    missing_skills=r.missing_skills,
                    open_to_work=otw,
                    open_to_work_status=otw_status,
                    open_to_work_evidence=row.open_to_work_evidence,
                    import_status=row.import_status,
                    imported_candidate_id=str(row.imported_candidate_id) if row.imported_candidate_id else None,
                )
            )
        elif r.key in db_by_key:
            cand = db_by_key[r.key]
            results.append(
                FindTalentCandidateOut(
                    rank=0,
                    score=r.score,
                    source="database",
                    candidate_id=str(cand.id),
                    full_name=cand.full_name,
                    headline=cand.headline,
                    current_title=cand.current_title,
                    location=cand.location_text,
                    skills=list(cand.skills or [])[:30],
                    explanation=r.explanation,
                    matched_skills=r.matched_skills,
                    missing_skills=r.missing_skills,
                    open_to_work=False,
                    open_to_work_status="unverified",
                    import_status="in_database",
                    imported_candidate_id=str(cand.id),
                )
            )

    # ── 4. Top-K highest match · drop zero fits · enforce location ──────────
    # (a) Exclude candidates that don't fit the role at all (zero match score).
    results = [x for x in results if x.score > 0]
    fit_count = len(results)  # candidates with a real fit, before location gate

    # (b) When a location is specified, keep only candidates from there; with no
    #     location the search spans all locations.
    location_filter = (body.location or "").strip()
    if location_filter:
        results = [
            x for x in results if _location_matches(x.location, location_filter)
        ]

    # (c) Rank strictly by match score (highest first). A verified Open-to-Work
    #     badge only breaks ties between equally-matched candidates.
    results.sort(key=lambda x: (-x.score, 0 if x.open_to_work else 1))

    # (d) Keep only the top-K best matches.
    results = results[: max(1, int(body.count))]

    for i, x in enumerate(results, start=1):
        x.rank = i

    if not results and message is None:
        if location_filter and fit_count > 0:
            # Candidates were found and fit the role, but none are in the
            # requested location — explain rather than look "broken".
            message = (
                f"Found {fit_count} matching candidate(s), but none are located in "
                f"“{location_filter}”. The selected source returned profiles from "
                f"other regions — switch to “All sources” to include your database, "
                f"or clear the location to search everywhere."
            )
        elif location_filter:
            message = (
                f"No candidates found in “{location_filter}”. Try a broader location, "
                f"or clear it to search everywhere."
            )
        else:
            message = "No candidates fit this role. Try broadening your requirements."

    return FindTalentResponse(
        batch_id=batch_id,
        job_id=body.job_id,
        provider_available=provider_available,
        message=message,
        results=results,
    )


@router.post(
    "/external/{external_candidate_id}/import",
    response_model=ImportResponseOut,
    status_code=status.HTTP_200_OK,
)
async def import_external_candidate(
    external_candidate_id: uuid.UUID,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    _: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
) -> ImportResponseOut:
    """Create a candidate account from an external preview row.

    Best-effort skills enrichment first: LinkedIn search snippets carry no
    skills, so when the preview row has none we read the person's profile via
    the MCP and copy the real "Top skills" before the import creates the
    Candidate — otherwise the new profile shows an empty skills section."""
    row = db.get(ExternalCandidate, external_candidate_id)
    if (
        row is not None
        and row.organization_id == ctx.organization_id
        and not (row.skills or [])
    ):
        username = _username_from_url(row.profile_url)
        if username:
            try:
                provider = get_sourcing_provider("linkedin_mcp")
                details = await provider.fetch_profile_details(username=username)
                if details.get("skills"):
                    row.skills = list(details["skills"])[:30]
                    if details.get("open_to_work") is not None:
                        row.open_to_work_signal = bool(details.get("open_to_work"))
                    db.commit()
            except Exception:  # noqa: BLE001 — enrichment is best-effort
                logger.warning(
                    "[SourceCandidate] skills enrichment failed for %s — "
                    "importing without skills", external_candidate_id,
                )
                db.rollback()

    service = SourceCandidateService()
    try:
        result = service.import_candidate(
            db,
            external_candidate_id=external_candidate_id,
            organization_id=ctx.organization_id,
            actor_user_id=ctx.user.id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if result.duplicate_detected:
        status_str: Literal["imported", "duplicate", "already_imported"] = "duplicate"
    elif not result.created_account:
        status_str = "already_imported"
    else:
        status_str = "imported"
    return ImportResponseOut(
        status=status_str,
        candidate_id=str(result.candidate_id),
        created_account=result.created_account,
        duplicate_detected=result.duplicate_detected,
        message=result.message,
    )


@router.post(
    "/external/import-batch",
    response_model=ImportBatchResponse,
    status_code=status.HTTP_200_OK,
)
def import_external_batch(
    body: ImportBatchRequest,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    _: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
) -> ImportBatchResponse:
    """Import multiple preview candidates in one call (optional "Import All")."""
    service = SourceCandidateService()
    results: list[ImportBatchResultItem] = []
    for raw_id in body.candidate_ids:
        try:
            ext_id = uuid.UUID(raw_id)
        except ValueError:
            results.append(
                ImportBatchResultItem(
                    external_candidate_id=raw_id,
                    status="error",
                    message="Invalid external_candidate_id",
                )
            )
            continue
        try:
            res = service.import_candidate(
                db,
                external_candidate_id=ext_id,
                organization_id=ctx.organization_id,
                actor_user_id=ctx.user.id,
            )
        except LookupError as exc:
            results.append(
                ImportBatchResultItem(
                    external_candidate_id=str(ext_id),
                    status="error",
                    message=str(exc),
                )
            )
            continue
        if res.duplicate_detected:
            tag: Literal["imported", "duplicate", "already_imported", "error"] = "duplicate"
        elif not res.created_account:
            tag = "already_imported"
        else:
            tag = "imported"
        results.append(
            ImportBatchResultItem(
                external_candidate_id=str(ext_id),
                status=tag,
                candidate_id=str(res.candidate_id),
                message=res.message,
            )
        )
    return ImportBatchResponse(results=results)


@router.get(
    "/database",
    response_model=DatabaseCandidateListOut,
)
def list_database_candidates(
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    _: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
    q: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> DatabaseCandidateListOut:
    """List real candidates in the database for the Source Candidate page."""
    service = SourceCandidateService()
    rows = service.list_database_candidates(
        db,
        organization_id=ctx.organization_id,
        q=q,
        limit=limit,
    )
    return DatabaseCandidateListOut(
        total=len(rows),
        items=[_serialize_database(c) for c in rows],
    )


@router.get(
    "/external/batches",
    response_model=BatchListOut,
)
def list_batches(
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    _: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
) -> BatchListOut:
    """Past Add-to-Process batches for this organization."""
    rows = db.execute(
        select(ExternalCandidateBatch)
        .where(ExternalCandidateBatch.organization_id == ctx.organization_id)
        .order_by(ExternalCandidateBatch.created_at.desc())
        .limit(limit)
    ).scalars().all()
    return BatchListOut(
        items=[
            BatchOut(
                id=str(b.id),
                provider=b.provider,
                requested_count=b.requested_count,
                fetched_count=b.fetched_count,
                status=b.status,
                location=b.location,
                error_message=b.error_message,
                created_at=b.created_at,
            )
            for b in rows
        ]
    )


@router.get(
    "/external/batches/{batch_id}",
    response_model=list[ExternalCandidateOut],
)
def list_batch_candidates(
    batch_id: uuid.UUID,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    _: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
) -> list[ExternalCandidateOut]:
    """Return preview rows for a previously created batch."""
    batch = db.get(ExternalCandidateBatch, batch_id)
    if batch is None or batch.organization_id != ctx.organization_id:
        raise HTTPException(status_code=404, detail="Batch not found")
    rows = db.execute(
        select(ExternalCandidate)
        .where(ExternalCandidate.batch_id == batch_id)
        .order_by(ExternalCandidate.created_at.asc())
    ).scalars().all()
    return [_serialize_external(r) for r in rows]

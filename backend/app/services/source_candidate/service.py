"""
PATHS Backend — Source Candidate service (fix6.md).

Orchestrates the recruiter "Add to Process" → preview → "Import" flow:

  1. fetch_batch — calls the configured provider for up to 5 candidates,
     applies the technical-role filter, persists rows in
     ``external_candidate_batches`` + ``external_candidates``.
  2. import_candidate — runs duplicate detection (email, profile URL,
     normalized name + company), either creates a fresh ``Candidate``
     row or links to an existing one, and updates ``import_status``.
  3. list_database_candidates — what the "Candidates From Our Database"
     section reads.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.candidate_sources import SourceType
from app.core.config import get_settings
from app.db.models.candidate import Candidate
from app.db.models.evidence import CandidateSource
from app.db.models.external_candidate import (
    ExternalCandidate,
    ExternalCandidateBatch,
)
from app.db.models.organization import Organization
from app.db.models.sync import AuditLog
from app.services.source_candidate.linkedin_account import (
    apply_org_credentials_to_mcp,
)
from app.services.source_candidate.provider import (
    CandidateSourcingProvider,
    ExternalCandidatePayload,
    FetchOpenToWorkInput,
    SourcingProviderError,
)
from app.services.source_candidate.providers import get_sourcing_provider

logger = logging.getLogger(__name__)
_settings = get_settings()


# ── Technical-role taxonomy (fix6.md §"Technical Roles Filter") ───────────
TECHNICAL_ROLE_KEYWORDS: tuple[str, ...] = (
    "software engineer",
    "backend engineer",
    "frontend engineer",
    "full stack engineer",
    "fullstack engineer",
    "full-stack engineer",
    "data scientist",
    "machine learning engineer",
    "ml engineer",
    "ai engineer",
    "data engineer",
    "devops engineer",
    "platform engineer",
    "cloud engineer",
    "cybersecurity engineer",
    "security engineer",
    "mobile developer",
    "android developer",
    "ios developer",
    "qa automation engineer",
    "qa engineer",
    "sre",
    "site reliability",
    "developer",
    "engineer",
    "programmer",
)

# Tokens that strongly suggest a non-technical role — reject if present
# and no technical token is also present.
NON_TECHNICAL_KEYWORDS: tuple[str, ...] = (
    "sales",
    "marketing",
    "hr",
    "human resources",
    "recruiter",
    "talent acquisition",
    "finance",
    "accountant",
    "admin",
    "administrative",
    "legal",
    "lawyer",
    "office manager",
    "operations manager",
    "customer success",
    "customer service",
)


def _clip(value: str | None, limit: int = 250) -> str | None:
    """Defensively bound a string to fit the DB's VARCHAR(255) columns."""
    if value is None:
        return None
    s = str(value)
    return s[:limit] if len(s) > limit else s


def is_technical_role(*texts: str | None) -> tuple[bool, str | None]:
    """Return (is_technical, evidence_phrase).

    Looks across the concatenated text blob for any technical keyword.
    If a non-technical keyword is found *and* no technical one is, returns
    False so the candidate is filtered out of fetch results.
    """
    blob = " ".join((t or "").lower() for t in texts).strip()
    if not blob:
        return False, None
    tech_hit = next((kw for kw in TECHNICAL_ROLE_KEYWORDS if kw in blob), None)
    nontech_hit = next((kw for kw in NON_TECHNICAL_KEYWORDS if kw in blob), None)
    if tech_hit:
        return True, f"Matches technical taxonomy: '{tech_hit}'"
    if nontech_hit:
        return False, None
    return False, None


# ── Service ──────────────────────────────────────────────────────────────


@dataclass
class FetchResult:
    batch_id: uuid.UUID
    items: list[ExternalCandidate]


@dataclass
class ImportResult:
    candidate_id: uuid.UUID
    created_account: bool
    duplicate_detected: bool
    message: str


class SourceCandidateService:
    def __init__(self, *, provider: CandidateSourcingProvider | None = None) -> None:
        self._provider_override = provider

    # ── Fetch ───────────────────────────────────────────────────────────

    async def fetch_batch(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        requested_by_user_id: uuid.UUID | None,
        provider_name: str | None = None,
        count: int | None = None,
        keywords: list[str] | None = None,
        location: str | None = None,
        apply_technical_filter: bool = True,
        max_count: int | None = None,
    ) -> FetchResult:
        cap = int(max_count or _settings.source_candidate_fetch_count)
        target_count = max(1, min(int(count or cap), cap))
        provider = self._provider_override or get_sourcing_provider(provider_name)

        # Before any MCP-backed fetch, push the recruiter's stored LinkedIn
        # cookies to the MCP server's cookies.json so its next browser
        # context picks them up. Silent no-op if nothing is stored.
        org = db.get(Organization, organization_id)
        if org is not None:
            try:
                apply_org_credentials_to_mcp(org)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "[SourceCandidate] could not refresh MCP cookies — "
                    "the provider may need interactive LinkedIn login.",
                )

        batch = ExternalCandidateBatch(
            id=uuid.uuid4(),
            organization_id=organization_id,
            provider=provider.provider_name,
            requested_by_user_id=requested_by_user_id,
            role_category="technical",
            requested_count=target_count,
            fetched_count=0,
            status="running",
            keywords=keywords or None,
            location=location,
            created_at=datetime.now(timezone.utc),
        )
        db.add(batch)
        db.flush()

        try:
            payloads = await provider.fetch_open_to_work_candidates(
                FetchOpenToWorkInput(
                    organization_id=str(organization_id),
                    count=target_count,
                    role_category="technical",
                    keywords=list(keywords or _default_technical_keywords()),
                    location=location,
                    source=provider.provider_name,  # type: ignore[arg-type]
                ),
            )
        except SourcingProviderError as exc:
            batch.status = "failed"
            batch.error_message = str(exc)
            db.commit()
            _audit(
                db,
                organization_id=organization_id,
                actor_user_id=requested_by_user_id,
                action="source_candidate.fetch.failed",
                payload={"batch_id": str(batch.id), "error": str(exc)},
            )
            raise

        accepted: list[ExternalCandidate] = []
        seen_urls: set[str] = set()
        for payload in payloads:
            is_tech, evidence = is_technical_role(
                payload.headline,
                payload.current_title,
                payload.full_name,
                " ".join(payload.skills or []),
            )
            # Find Talent ranks against the recruiter's query/job, so it opts
            # out of the technical-only gate; the legacy fetch keeps it on.
            if apply_technical_filter and not is_tech:
                continue

            url = _clip(payload.profile_url, 500)
            # The same query re-run returns the same profiles. The table has a
            # unique (organization_id, provider, profile_url) constraint, so
            # re-inserting would raise an IntegrityError and 500 the whole
            # request (which the browser surfaces as "Failed to fetch" because
            # an unhandled 500 carries no CORS headers). De-dupe instead:
            # skip in-batch repeats and reuse any existing row for this org.
            existing: ExternalCandidate | None = None
            if url:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                existing = db.execute(
                    select(ExternalCandidate)
                    .where(
                        ExternalCandidate.organization_id == organization_id,
                        ExternalCandidate.provider == payload.provider,
                        ExternalCandidate.profile_url == url,
                    )
                    .limit(1)
                ).scalar_one_or_none()

            if existing is not None:
                # Refresh the cheap display fields and reuse the existing row.
                existing.full_name = _clip(payload.full_name) or existing.full_name
                existing.headline = _clip(payload.headline) or existing.headline
                existing.current_title = _clip(payload.current_title) or existing.current_title
                existing.location = _clip(payload.location) or existing.location
                if payload.skills:
                    existing.skills = list(payload.skills)
                accepted.append(existing)
            else:
                row = ExternalCandidate(
                    id=uuid.uuid4(),
                    batch_id=batch.id,
                    organization_id=organization_id,
                    provider=payload.provider,
                    external_id=_clip(payload.external_id),
                    profile_url=url,
                    full_name=_clip(payload.full_name),
                    headline=_clip(payload.headline),
                    current_title=_clip(payload.current_title),
                    current_company=_clip(payload.current_company),
                    location=_clip(payload.location),
                    email=_clip(payload.email),
                    phone=_clip(payload.phone, 64),
                    skills=list(payload.skills or []),
                    open_to_work_signal=payload.open_to_work_signal,
                    open_to_work_evidence=_clip(payload.open_to_work_evidence),
                    technical_role_evidence=_clip(payload.technical_role_evidence or evidence),
                    raw_payload=payload.raw or None,
                    import_status="ready_to_import",
                    created_at=datetime.now(timezone.utc),
                )
                db.add(row)
                accepted.append(row)
            if len(accepted) >= target_count:
                break

        batch.fetched_count = len(accepted)
        batch.status = "completed"
        db.commit()
        _audit(
            db,
            organization_id=organization_id,
            actor_user_id=requested_by_user_id,
            action="source_candidate.fetch",
            payload={
                "batch_id": str(batch.id),
                "provider": provider.provider_name,
                "fetched_count": len(accepted),
                "requested_count": target_count,
            },
        )
        for row in accepted:
            db.refresh(row)
        return FetchResult(batch_id=batch.id, items=accepted)

    # ── Import ──────────────────────────────────────────────────────────

    def import_candidate(
        self,
        db: Session,
        *,
        external_candidate_id: uuid.UUID,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
    ) -> ImportResult:
        row = db.get(ExternalCandidate, external_candidate_id)
        if row is None or row.organization_id != organization_id:
            raise LookupError("External candidate not found")

        if row.imported_candidate_id is not None:
            return ImportResult(
                candidate_id=row.imported_candidate_id,
                created_account=False,
                duplicate_detected=row.import_status == "duplicate",
                message="Candidate already imported.",
            )

        existing = _find_duplicate(
            db,
            email=row.email,
            profile_url=row.profile_url,
            full_name=row.full_name,
            current_company=row.current_company,
            phone=row.phone,
            organization_id=organization_id,
        )

        if existing is not None:
            row.imported_candidate_id = existing.id
            row.import_status = "duplicate"
            row.imported_at = datetime.now(timezone.utc)
            # Backfill: the external row may carry skills the existing
            # profile lacks (e.g. enriched from the LinkedIn profile read).
            if not (existing.skills or []) and (row.skills or []):
                existing.skills = list(row.skills)
            _ensure_candidate_source(
                db,
                candidate_id=existing.id,
                provider=row.provider,
                profile_url=row.profile_url,
            )
            db.commit()
            _audit(
                db,
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                action="source_candidate.import.duplicate",
                payload={
                    "external_candidate_id": str(row.id),
                    "candidate_id": str(existing.id),
                    "provider": row.provider,
                },
            )
            return ImportResult(
                candidate_id=existing.id,
                created_account=False,
                duplicate_detected=True,
                message="Candidate already exists in your database. Linked external source to the existing profile.",
            )

        candidate = Candidate(
            id=uuid.uuid4(),
            full_name=row.full_name or "Unknown candidate",
            email=row.email,
            phone=row.phone,
            current_title=row.current_title,
            location_text=row.location,
            headline=row.headline,
            skills=list(row.skills or []) or None,
            summary=None,
            status="active",
            source_type=SourceType.SOURCED.value,
            source_platform=row.provider,
            owner_organization_id=organization_id,
        )
        db.add(candidate)
        db.flush()

        _ensure_candidate_source(
            db,
            candidate_id=candidate.id,
            provider=row.provider,
            profile_url=row.profile_url,
        )

        row.imported_candidate_id = candidate.id
        row.import_status = "imported"
        row.imported_at = datetime.now(timezone.utc)
        db.commit()
        _audit(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="source_candidate.import",
            payload={
                "external_candidate_id": str(row.id),
                "candidate_id": str(candidate.id),
                "provider": row.provider,
                "profile_url": row.profile_url,
            },
        )
        return ImportResult(
            candidate_id=candidate.id,
            created_account=True,
            duplicate_detected=False,
            message="Candidate imported successfully and added to the organization candidate pool.",
        )

    # ── Read APIs ───────────────────────────────────────────────────────

    def list_database_candidates(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        q: str | None = None,
        limit: int = 100,
    ) -> list[Candidate]:
        """Real candidates already in the platform, scoped to this org's pool.

        Includes:
          * candidates the org imported / uploaded / manually added
          * candidates the org sourced (including via the new import flow)
          * platform-wide PATHS profiles (no owner_organization_id)
        """
        stmt = (
            select(Candidate)
            .where(
                or_(
                    Candidate.owner_organization_id == organization_id,
                    Candidate.owner_organization_id.is_(None),
                ),
                # Show everyone still in the pool. A per-job outcome
                # (accepted_candidate / rejected_candidate) does NOT remove a
                # person from the database — they remain a real candidate who
                # can be sourced for other roles. Only hide the genuinely
                # removed (deleted / merged / withdrawn / inactive).
                or_(
                    Candidate.status.is_(None),
                    Candidate.status.notin_(
                        ("deleted", "inactive", "archived", "merged", "duplicate", "withdrawn"),
                    ),
                ),
            )
            .order_by(Candidate.created_at.desc())
            .limit(limit)
        )
        if q:
            needle = f"%{q.strip()}%"
            stmt = stmt.where(
                or_(
                    Candidate.full_name.ilike(needle),
                    Candidate.current_title.ilike(needle),
                    Candidate.location_text.ilike(needle),
                    Candidate.headline.ilike(needle),
                )
            )
        return list(db.execute(stmt).scalars().all())


# ── Helpers ──────────────────────────────────────────────────────────────


def _default_technical_keywords() -> list[str]:
    return [
        "software engineer",
        "data scientist",
        "machine learning",
        "backend",
        "frontend",
        "devops",
        "data engineer",
    ]


_PUNCT_RE = re.compile(r"[^a-z0-9]+")


def _normalize_name(value: str | None) -> str:
    return _PUNCT_RE.sub(" ", (value or "").lower()).strip()


def _find_duplicate(
    db: Session,
    *,
    email: str | None,
    profile_url: str | None,
    full_name: str | None,
    current_company: str | None,
    phone: str | None,
    organization_id: uuid.UUID,
) -> Candidate | None:
    """Duplicate detection — priority order from fix6.md §Duplicate Handling."""

    if email:
        existing = db.execute(
            select(Candidate).where(Candidate.email.ilike(email.strip())).limit(1)
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    if profile_url:
        candidate_id_row = db.execute(
            select(CandidateSource.candidate_id).where(
                CandidateSource.url == profile_url.strip()
            ).limit(1)
        ).scalar_one_or_none()
        if candidate_id_row:
            cand = db.get(Candidate, candidate_id_row)
            if cand is not None:
                return cand

    if full_name:
        norm_name = _normalize_name(full_name)
        if norm_name:
            candidates: Iterable[Candidate] = db.execute(
                select(Candidate).where(
                    Candidate.full_name.ilike(f"%{full_name.strip()}%"),
                    or_(
                        Candidate.owner_organization_id == organization_id,
                        Candidate.owner_organization_id.is_(None),
                    ),
                ).limit(20)
            ).scalars().all()
            for cand in candidates:
                if _normalize_name(cand.full_name) != norm_name:
                    continue
                # Candidate has no current_company column — match on
                # headline/current_title text instead.
                if current_company:
                    norm_company = _normalize_name(current_company)
                    existing_blob = _normalize_name(
                        " ".join(
                            filter(None, [cand.headline, cand.current_title])
                        )
                    )
                    if norm_company and norm_company in existing_blob:
                        return cand
                else:
                    return cand

    if phone:
        digits = re.sub(r"\D", "", phone)
        if digits:
            existing = db.execute(
                select(Candidate).where(Candidate.phone.ilike(f"%{digits}%")).limit(1)
            ).scalar_one_or_none()
            if existing is not None:
                return existing
    return None


def _ensure_candidate_source(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    provider: str,
    profile_url: str | None,
) -> None:
    """Idempotently insert a CandidateSource row for the imported candidate.

    Records the external provenance so the candidate carries a source badge
    in the UI (LinkedIn Open-To-Work / External Recruitment Platform).
    """
    if profile_url:
        existing = db.execute(
            select(CandidateSource).where(
                and_(
                    CandidateSource.candidate_id == candidate_id,
                    CandidateSource.source == provider,
                    CandidateSource.url == profile_url,
                )
            ).limit(1)
        ).scalar_one_or_none()
        if existing is not None:
            return
    db.add(
        CandidateSource(
            candidate_id=candidate_id,
            source=provider,
            url=profile_url,
        )
    )


def _audit(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    action: str,
    payload: dict,
) -> None:
    """Best-effort audit logging — never fails the parent transaction."""
    try:
        entry = AuditLog(
            actor_user_id=actor_user_id,
            entity_type="external_candidate",
            entity_id=organization_id,
            action=action,
            new_value=payload,
        )
        db.add(entry)
        db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("source_candidate audit log failed for %s", action)
        db.rollback()

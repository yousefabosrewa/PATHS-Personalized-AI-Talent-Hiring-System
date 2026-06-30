"""
PATHS Backend — Open-to-Work Candidate Sourcing orchestrator.

Mirrors `app.services.job_scraper.job_import_service.JobImportService` but
for candidates instead of jobs. The service:

  1. Acquires a PostgreSQL advisory lock so concurrent runs don't import
     the same candidate twice.
  2. Calls the configured provider for raw open-to-work profiles.
  3. Normalizes and validates each one.
  4. For every accepted profile, in its own transaction:
       a. Dedup by source URL / external id / email.
       b. Upsert into `candidates` (no schema changes).
       c. Persist provenance into the existing `candidate_sources`
          and `evidence_items` tables (using `meta_json` for any
          extras).
       d. Persist links / contacts / projects / experiences / education
          via the existing `candidates_relational` helpers.
       e. Sync the candidate to AGE + Qdrant via the existing
          `candidate_sync_service.sync_candidate_full`.

Failures in graph or vector sync are logged but never delete the
PostgreSQL candidate — the existing admin retry endpoints can recover
the candidate later.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.db.models.candidate import Candidate
from app.db.models.candidate_extras import CandidateLink
from app.db.models.evidence import CandidateSource, EvidenceItem
from app.db.repositories import candidates_relational
from app.services.candidate_sync_service import sync_candidate_full
from app.services.sourcing.normalizers import (
    NormalizedSourcedCandidate,
    normalize_sourced_candidates,
)
from app.services.sourcing.providers import (
    BaseCandidateProvider,
    SourcingRunResult,
    get_provider,
)

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class CandidateSourcingRunResult:
    """Spec-compliant sourcing run summary returned by the service."""

    source_platform: str
    requested_limit: int
    started_at: datetime
    finished_at: datetime | None = None
    fetched_count: int = 0
    valid_count: int = 0
    inserted_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    graph_synced_count: int = 0
    vector_synced_count: int = 0
    candidate_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    status: str = "success"  # success | partial | failed | locked | disabled


class CandidateSourcingService:
    """Orchestrates provider → normalize → PostgreSQL → AGE → Qdrant."""

    def __init__(
        self,
        *,
        provider: BaseCandidateProvider | None = None,
        session_factory=SessionLocal,
    ) -> None:
        self._provider = provider
        self._session_factory = session_factory

    # ── Public API ─────────────────────────────────────────────────────

    async def run_sourcing(
        self,
        *,
        limit: int | None = None,
        provider_name: str | None = None,
        keywords: list[str] | None = None,
        location: str | None = None,
        admin_override: bool = False,
    ) -> CandidateSourcingRunResult:
        provider_name = provider_name or settings.candidate_sourcing_provider
        provider = self._provider or get_provider(provider_name)

        capped_limit = self._resolve_limit(limit, admin_override=admin_override)
        started = datetime.now(timezone.utc)
        result = CandidateSourcingRunResult(
            source_platform=provider.name(),
            requested_limit=capped_limit,
            started_at=started,
        )

        if not settings.candidate_sourcing_enabled:
            result.status = "disabled"
            result.finished_at = datetime.now(timezone.utc)
            logger.info(
                "[CandidateSourcing] disabled — set CANDIDATE_SOURCING_ENABLED=true",
            )
            return result

        kws = list(keywords or self._default_keywords())
        loc = location or self._default_location()

        # Advisory lock so concurrent workers don't import duplicates.
        lock_session: Session = self._session_factory()
        try:
            locked = self._try_acquire_lock(
                lock_session, settings.candidate_sourcing_lock_name,
            )
            if not locked:
                logger.info("[CandidateSourcing] another worker holds the lock; skipping")
                result.status = "locked"
                result.finished_at = datetime.now(timezone.utc)
                return result
            try:
                await self._run_locked(
                    result,
                    provider=provider,
                    limit=capped_limit,
                    keywords=kws,
                    location=loc,
                )
            finally:
                self._release_lock(lock_session, settings.candidate_sourcing_lock_name)
        finally:
            try:
                lock_session.close()
            except Exception:  # noqa: BLE001
                pass

        result.finished_at = datetime.now(timezone.utc)
        logger.info(
            "[CandidateSourcing] finished status=%s fetched=%d valid=%d "
            "inserted=%d updated=%d skipped=%d failed=%d graph_synced=%d vector_synced=%d",
            result.status,
            result.fetched_count,
            result.valid_count,
            result.inserted_count,
            result.updated_count,
            result.skipped_count,
            result.failed_count,
            result.graph_synced_count,
            result.vector_synced_count,
        )
        return result

    # ── Locked work ────────────────────────────────────────────────────

    async def _run_locked(
        self,
        result: CandidateSourcingRunResult,
        *,
        provider: BaseCandidateProvider,
        limit: int,
        keywords: list[str],
        location: str | None,
    ) -> None:
        try:
            run: SourcingRunResult = await provider.fetch_open_to_work_candidates(
                limit=limit,
                offset=0,
                keywords=keywords,
                location=location,
                timeout_seconds=settings.candidate_sourcing_request_timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("[CandidateSourcing] provider failed")
            result.status = "failed"
            result.errors.append(f"provider_error:{exc}")
            return

        result.fetched_count = len(run.raw_candidates)
        result.errors.extend(run.errors)

        normalized, rejected = normalize_sourced_candidates(run.raw_candidates)
        result.valid_count = len(normalized)
        for r in rejected:
            result.errors.append(
                f"rejected:{r.raw.source_url or r.raw.source_external_id}: {','.join(r.reasons)}"
            )

        for norm in normalized[:limit]:
            try:
                outcome, candidate_id = self._upsert_sourced_candidate(norm)
            except Exception as exc:  # noqa: BLE001
                logger.exception("[CandidateSourcing] upsert failed for %s", norm.source_url)
                result.failed_count += 1
                result.errors.append(f"upsert_error:{exc}")
                continue

            if outcome == "inserted":
                result.inserted_count += 1
            elif outcome == "updated":
                result.updated_count += 1
            else:
                result.skipped_count += 1

            if candidate_id:
                result.candidate_ids.append(str(candidate_id))
                sync_outcome = self._sync_candidate(candidate_id)
                if sync_outcome["graph"]:
                    result.graph_synced_count += 1
                if sync_outcome["vector"]:
                    result.vector_synced_count += 1
                if sync_outcome["graph_error"]:
                    result.errors.append(
                        f"graph:{candidate_id}:{sync_outcome['graph_error']}"
                    )
                if sync_outcome["vector_error"]:
                    result.errors.append(
                        f"vector:{candidate_id}:{sync_outcome['vector_error']}"
                    )

        if result.failed_count and result.inserted_count + result.updated_count == 0:
            result.status = "failed"
        elif result.failed_count or result.errors:
            result.status = "partial"
        else:
            result.status = "success"

    # ── Per-candidate database work (own session) ──────────────────────

    def _upsert_sourced_candidate(
        self, norm: NormalizedSourcedCandidate,
    ) -> tuple[str, UUID | None]:
        session: Session = self._session_factory()
        try:
            existing = self._find_existing_candidate(session, norm)
            if existing is not None:
                outcome = self._update_candidate(session, existing, norm)
                candidate_id: UUID = existing.id
            else:
                created = candidates_relational.create_candidate(
                    session,
                    {
                        "full_name": norm.full_name,
                        "email": norm.email,
                        "phone": norm.phone,
                        "current_title": norm.current_title,
                        "location_text": norm.location_text,
                        "headline": norm.headline,
                        "years_experience": norm.years_experience,
                        "summary": norm.summary,
                        "status": "active",
                    },
                )
                candidate_id = created.id
                # Record the array fields directly (model exposes them).
                created.skills = norm.skills or None
                created.open_to_job_types = norm.desired_job_types or None
                created.open_to_workplace_settings = norm.desired_workplace or None
                created.desired_job_titles = norm.desired_titles or None
                outcome = "inserted"

            self._upsert_relations(session, candidate_id, norm)
            self._upsert_source(session, candidate_id, norm)
            self._upsert_evidence(session, candidate_id, norm)
            session.commit()
            return outcome, candidate_id
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _find_existing_candidate(
        self, session: Session, norm: NormalizedSourcedCandidate,
    ) -> Candidate | None:
        # 1. Match on the same external profile URL via CandidateLink/CandidateSource
        if norm.source_url:
            row = session.execute(
                select(Candidate)
                .join(CandidateSource, CandidateSource.candidate_id == Candidate.id)
                .where(CandidateSource.url == norm.source_url)
                .limit(1)
            ).scalar_one_or_none()
            if row is not None:
                return row
            row = session.execute(
                select(Candidate)
                .join(CandidateLink, CandidateLink.candidate_id == Candidate.id)
                .where(CandidateLink.url == norm.source_url)
                .limit(1)
            ).scalar_one_or_none()
            if row is not None:
                return row

        # 2. Match on email when available.
        if norm.email:
            row = session.execute(
                select(Candidate).where(Candidate.email == norm.email).limit(1)
            ).scalar_one_or_none()
            if row is not None:
                return row
        return None

    def _update_candidate(
        self,
        session: Session,
        candidate: Candidate,
        norm: NormalizedSourcedCandidate,
    ) -> str:
        changed = False
        for field_name, value in [
            ("full_name", norm.full_name),
            ("email", norm.email),
            ("phone", norm.phone),
            ("current_title", norm.current_title),
            ("location_text", norm.location_text),
            ("headline", norm.headline),
            ("summary", norm.summary),
            ("years_experience", norm.years_experience),
        ]:
            if value is None:
                continue
            current = getattr(candidate, field_name, None)
            if current != value:
                setattr(candidate, field_name, value)
                changed = True

        if norm.skills and (not candidate.skills or set(norm.skills) - set(candidate.skills)):
            merged = list({*(candidate.skills or []), *norm.skills})
            candidate.skills = merged
            changed = True
        if norm.desired_titles:
            candidate.desired_job_titles = list(
                {*(candidate.desired_job_titles or []), *norm.desired_titles},
            )
            changed = True
        if norm.desired_job_types:
            candidate.open_to_job_types = list(
                {*(candidate.open_to_job_types or []), *norm.desired_job_types},
            )
            changed = True
        if norm.desired_workplace:
            candidate.open_to_workplace_settings = list(
                {*(candidate.open_to_workplace_settings or []), *norm.desired_workplace},
            )
            changed = True
        if candidate.status != "active":
            candidate.status = "active"
            changed = True

        session.flush()
        return "updated" if changed else "skipped"

    def _upsert_relations(
        self,
        session: Session,
        candidate_id: UUID,
        norm: NormalizedSourcedCandidate,
    ) -> None:
        for skill in norm.skills:
            try:
                candidates_relational.upsert_candidate_skill(
                    session, candidate_id, {"name": skill},
                )
            except ValueError:
                continue
        for exp in norm.experiences:
            try:
                candidates_relational.upsert_candidate_experience(
                    session, candidate_id, exp,
                )
            except Exception:  # noqa: BLE001
                logger.exception("[CandidateSourcing] experience upsert failed")
        for project in norm.projects:
            try:
                candidates_relational.upsert_candidate_project(
                    session, candidate_id, project,
                )
            except Exception:  # noqa: BLE001
                logger.exception("[CandidateSourcing] project upsert failed")
        for contact in norm.contacts:
            try:
                candidates_relational.upsert_candidate_contact(
                    session,
                    candidate_id,
                    contact_type=contact.get("contact_type", "other"),
                    contact_value=contact.get("contact_value", ""),
                    source=norm.source_platform,
                )
            except Exception:  # noqa: BLE001
                logger.exception("[CandidateSourcing] contact upsert failed")
        for link in norm.links:
            try:
                candidates_relational.upsert_candidate_link(
                    session,
                    candidate_id,
                    link_type=link.get("link_type", "other"),
                    url=link.get("url", ""),
                    label=link.get("label"),
                )
            except Exception:  # noqa: BLE001
                logger.exception("[CandidateSourcing] link upsert failed")

    def _upsert_source(
        self,
        session: Session,
        candidate_id: UUID,
        norm: NormalizedSourcedCandidate,
    ) -> None:
        if not norm.source_url and not norm.source_external_id:
            return
        existing = session.execute(
            select(CandidateSource).where(
                CandidateSource.candidate_id == candidate_id,
                CandidateSource.source == norm.source_platform,
            ).limit(1)
        ).scalar_one_or_none()
        if existing is None:
            row = CandidateSource(
                candidate_id=candidate_id,
                source=norm.source_platform,
                url=norm.source_url,
                fetched_at=datetime.now(timezone.utc),
            )
            session.add(row)
            session.flush()
            return
        existing.url = norm.source_url or existing.url
        existing.fetched_at = datetime.now(timezone.utc)
        session.flush()

    def _upsert_evidence(
        self,
        session: Session,
        candidate_id: UUID,
        norm: NormalizedSourcedCandidate,
    ) -> None:
        """Store the open-to-work signal + raw payload as evidence rows."""
        meta = {
            "open_to_work": bool(norm.open_to_work),
            "source_platform": norm.source_platform,
            "source_url": norm.source_url,
            "source_external_id": norm.source_external_id,
            "desired_titles": norm.desired_titles,
            "desired_job_types": norm.desired_job_types,
            "desired_workplace": norm.desired_workplace,
            "current_company": norm.current_company,
            "raw_keys": sorted(list(norm.raw.keys()))[:20] if isinstance(norm.raw, dict) else [],
        }
        existing = session.execute(
            select(EvidenceItem).where(
                EvidenceItem.candidate_id == candidate_id,
                EvidenceItem.type == "sourced_profile",
                EvidenceItem.field_ref == norm.source_platform,
            ).limit(1)
        ).scalar_one_or_none()
        if existing is None:
            row = EvidenceItem(
                candidate_id=candidate_id,
                type="sourced_profile",
                field_ref=norm.source_platform,
                source_uri=norm.source_url,
                extracted_text=(norm.headline or norm.summary or "")[:2000] or None,
                confidence=0.5,
                meta_json=meta,
            )
            session.add(row)
        else:
            existing.source_uri = norm.source_url or existing.source_uri
            existing.extracted_text = (norm.headline or norm.summary or existing.extracted_text or "")[:2000]
            existing.meta_json = meta
        session.flush()

    # ── Sync helpers ───────────────────────────────────────────────────

    def _sync_candidate(self, candidate_id: UUID) -> dict[str, Any]:
        out = {"graph": False, "vector": False, "graph_error": None, "vector_error": None}
        session: Session = self._session_factory()
        try:
            sync_result = sync_candidate_full(session, candidate_id, force_vector=True)
            graph = sync_result.get("graph", {})
            vector = sync_result.get("vector", {})
            if graph.get("status") == "success":
                out["graph"] = True
            else:
                out["graph_error"] = graph.get("error") or graph.get("status")
            if vector.get("status") in {"success", "unchanged"}:
                out["vector"] = True
            else:
                out["vector_error"] = vector.get("error") or vector.get("status")
        except Exception as exc:  # noqa: BLE001
            logger.exception("[CandidateSourcing] sync failed for %s", candidate_id)
            out["graph_error"] = str(exc)
            out["vector_error"] = str(exc)
        finally:
            session.close()
        return out

    # ── Misc helpers ───────────────────────────────────────────────────

    @staticmethod
    def _resolve_limit(limit: int | None, *, admin_override: bool) -> int:
        cap = max(1, int(settings.candidate_sourcing_max_per_run))
        if limit is None:
            return cap
        n = max(1, int(limit))
        if admin_override:
            return min(n, 50)
        return min(n, cap)

    @staticmethod
    def _default_keywords() -> list[str]:
        raw = settings.candidate_sourcing_default_keywords or ""
        return [k.strip() for k in raw.split(",") if k.strip()]

    @staticmethod
    def _default_location() -> str | None:
        return (settings.candidate_sourcing_default_location or "").strip() or None

    @staticmethod
    def _try_acquire_lock(session: Session, lock_name: str) -> bool:
        try:
            locked = session.execute(
                text("SELECT pg_try_advisory_lock(hashtext(:n))"),
                {"n": lock_name},
            ).scalar()
            return bool(locked)
        except Exception:  # noqa: BLE001
            logger.exception("[CandidateSourcing] advisory lock acquire failed")
            return False

    @staticmethod
    def _release_lock(session: Session, lock_name: str) -> None:
        try:
            session.execute(
                text("SELECT pg_advisory_unlock(hashtext(:n))"),
                {"n": lock_name},
            )
            session.commit()
        except Exception:  # noqa: BLE001
            logger.warning("[CandidateSourcing] advisory lock release failed (non-fatal)")


__all__ = [
    "CandidateSourcingService",
    "CandidateSourcingRunResult",
]

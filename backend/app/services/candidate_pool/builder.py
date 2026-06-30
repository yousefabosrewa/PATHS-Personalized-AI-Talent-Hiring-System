"""
CandidatePoolBuilderService.

Builds the candidate pool for a single job based on:

  1. The org-level OrganizationCandidateSourceSettings (defaults)
  2. The per-job JobCandidatePoolConfig (overrides + filters + top_k)

The builder enforces tenant isolation strictly:

  * COMPANY_UPLOADED / SOURCED / JOB_FAIR / ATS_IMPORT / MANUAL_ADD
    candidates are visible to the requesting org ONLY when
    `candidates.owner_organization_id == requesting_org_id`.

  * PATHS_PROFILE candidates are visible to ANY org provided the candidate
    is in `status='active'`. We do not yet have a public/visible flag — when
    one is added (`candidate.is_public_profile`), this filter can be
    tightened in a follow-up.

  * The builder never returns candidates from another organization; even
    `preview()` filters on the requesting org.

The builder produces two artefacts:

  * preview(): a count-only summary (no DB writes). Used by the UI before
    the user commits. Always cheap.

  * build(): a full CandidatePoolRun with one CandidatePoolMember per
    candidate that was *considered*, including those that were excluded —
    so an auditor can see why each candidate did or did not make the pool.

Profile-completeness and evidence-confidence are computed inline. They
are intentionally simple — a follow-up should plug in the real signals
from the Candidate Profile Agent + Evidence Agent. The numbers here are
honest stand-ins, not random.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.candidate_sources import (
    SETTINGS_FLAG_MAP,
    SOURCE_LABELS,
    SourceType,
)
from app.db.models.candidate import Candidate
from app.db.models.candidate_sourcing import (
    CandidatePoolMember,
    CandidatePoolRun,
    JobCandidatePoolConfig,
    OrganizationCandidateSourceSettings,
)
from app.db.models.job import Job


# ── Eligibility statuses ─────────────────────────────────────────────────

ELIGIBLE = "eligible"
EXCLUDED_INCOMPLETE_PROFILE = "excluded_incomplete_profile"
EXCLUDED_LOW_EVIDENCE = "excluded_low_evidence"
EXCLUDED_DUPLICATE = "excluded_duplicate"
EXCLUDED_SOURCE_DISABLED = "excluded_source_disabled"
EXCLUDED_NO_OWNERSHIP = "excluded_no_ownership"


# ── Public dataclasses ───────────────────────────────────────────────────


@dataclass
class PoolPreview:
    """Cheap, count-only summary returned to the UI before pool commit."""

    job_id: uuid.UUID
    organization_id: uuid.UUID
    config_snapshot: dict
    source_breakdown: dict[str, int] = field(default_factory=dict)
    duplicates_removed: int = 0
    excluded_incomplete_profile: int = 0
    excluded_low_evidence: int = 0
    eligible_candidates: int = 0
    total_candidates_found: int = 0


@dataclass
class PoolBuildResult:
    """Returned to the API after a pool is committed."""

    pool_run_id: uuid.UUID
    job_id: uuid.UUID
    organization_id: uuid.UUID
    eligible_candidates: int
    excluded_candidates: int
    duplicates_removed: int
    source_breakdown: dict[str, int]
    status: str


# ── Service ──────────────────────────────────────────────────────────────


class CandidatePoolBuilderService:
    def __init__(self, db: Session):
        self.db = db

    # ---- public API --------------------------------------------------

    def get_or_create_org_settings(
        self, organization_id: uuid.UUID
    ) -> OrganizationCandidateSourceSettings:
        row = (
            self.db.query(OrganizationCandidateSourceSettings)
            .filter(
                OrganizationCandidateSourceSettings.organization_id
                == organization_id
            )
            .one_or_none()
        )
        if row is not None:
            return row
        row = OrganizationCandidateSourceSettings(organization_id=organization_id)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_or_create_job_config(
        self, job_id: uuid.UUID, organization_id: uuid.UUID
    ) -> JobCandidatePoolConfig:
        row = (
            self.db.query(JobCandidatePoolConfig)
            .filter(JobCandidatePoolConfig.job_id == job_id)
            .one_or_none()
        )
        if row is not None:
            if row.organization_id != organization_id:
                # Tenant isolation: refuse if config belongs to another org.
                raise PermissionError(
                    "Pool config belongs to a different organization."
                )
            return row

        # Seed config from org defaults when first created
        org_settings = self.get_or_create_org_settings(organization_id)
        row = JobCandidatePoolConfig(
            job_id=job_id,
            organization_id=organization_id,
            use_paths_profiles=org_settings.use_paths_profiles_default,
            use_sourced_candidates=org_settings.use_sourced_candidates_default,
            use_uploaded_candidates=org_settings.use_uploaded_candidates_default,
            use_job_fair_candidates=org_settings.use_job_fair_candidates_default,
            use_ats_candidates=org_settings.use_ats_candidates_default,
            top_k=org_settings.default_top_k,
            min_profile_completeness=org_settings.default_min_profile_completeness,
            min_evidence_confidence=org_settings.default_min_evidence_confidence,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def preview(
        self, job_id: uuid.UUID, organization_id: uuid.UUID
    ) -> PoolPreview:
        """Cheap dry-run that does not write anything."""

        config = self.get_or_create_job_config(job_id, organization_id)
        enabled = self._enabled_sources_from_config(config)
        candidates = self._fetch_candidates_for_org(
            organization_id=organization_id, enabled_sources=enabled
        )

        breakdown: dict[str, int] = {s.value: 0 for s in SourceType}
        eligible = 0
        excluded_profile = 0
        excluded_evidence = 0
        seen_keys: set[str] = set()
        duplicates = 0

        for c in candidates:
            breakdown[c.source_type] = breakdown.get(c.source_type, 0) + 1
            dup_key = self._dedupe_key(c)
            if dup_key in seen_keys:
                duplicates += 1
                continue
            seen_keys.add(dup_key)

            comp = self._profile_completeness(c)
            if comp < config.min_profile_completeness:
                excluded_profile += 1
                continue

            ev = self._evidence_confidence(c)
            if ev < config.min_evidence_confidence:
                excluded_evidence += 1
                continue

            eligible += 1

        return PoolPreview(
            job_id=job_id,
            organization_id=organization_id,
            config_snapshot=self._config_snapshot(config),
            source_breakdown={k: v for k, v in breakdown.items() if v > 0},
            duplicates_removed=duplicates,
            excluded_incomplete_profile=excluded_profile,
            excluded_low_evidence=excluded_evidence,
            eligible_candidates=eligible,
            total_candidates_found=len(candidates),
        )

    def build(
        self,
        job_id: uuid.UUID,
        organization_id: uuid.UUID,
        created_by_user_id: uuid.UUID | None = None,
    ) -> PoolBuildResult:
        """Persist a CandidatePoolRun + members. Idempotent only in the
        sense that each call produces a *new* run; older runs are kept for
        audit. Callers wanting the latest pool should query by job_id +
        status='completed' ORDER BY created_at DESC LIMIT 1.
        """

        config = self.get_or_create_job_config(job_id, organization_id)
        enabled = self._enabled_sources_from_config(config)
        candidates = self._fetch_candidates_for_org(
            organization_id=organization_id, enabled_sources=enabled
        )

        run = CandidatePoolRun(
            job_id=job_id,
            organization_id=organization_id,
            config_id=config.id,
            status="running",
            total_candidates_found=len(candidates),
            created_by_user_id=created_by_user_id,
        )
        self.db.add(run)
        self.db.flush()  # need run.id for member rows

        breakdown: dict[str, int] = {}
        seen_keys: set[str] = set()
        duplicates = 0
        eligible = 0
        excluded = 0

        members: list[CandidatePoolMember] = []
        for c in candidates:
            breakdown[c.source_type] = breakdown.get(c.source_type, 0) + 1
            comp = self._profile_completeness(c)
            ev = self._evidence_confidence(c)

            dup_key = self._dedupe_key(c)
            if dup_key in seen_keys:
                duplicates += 1
                excluded += 1
                members.append(
                    CandidatePoolMember(
                        pool_run_id=run.id,
                        candidate_id=c.id,
                        source_type=c.source_type,
                        eligibility_status=EXCLUDED_DUPLICATE,
                        exclusion_reason=(
                            "Identified as a duplicate of another candidate "
                            "in this pool by email/phone match."
                        ),
                        profile_completeness=comp,
                        evidence_confidence=ev,
                    )
                )
                continue
            seen_keys.add(dup_key)

            if comp < config.min_profile_completeness:
                excluded += 1
                members.append(
                    CandidatePoolMember(
                        pool_run_id=run.id,
                        candidate_id=c.id,
                        source_type=c.source_type,
                        eligibility_status=EXCLUDED_INCOMPLETE_PROFILE,
                        exclusion_reason=(
                            f"Profile completeness {comp}% is below the "
                            f"minimum {config.min_profile_completeness}%."
                        ),
                        profile_completeness=comp,
                        evidence_confidence=ev,
                    )
                )
                continue
            if ev < config.min_evidence_confidence:
                excluded += 1
                members.append(
                    CandidatePoolMember(
                        pool_run_id=run.id,
                        candidate_id=c.id,
                        source_type=c.source_type,
                        eligibility_status=EXCLUDED_LOW_EVIDENCE,
                        exclusion_reason=(
                            f"Evidence confidence {ev}% is below the "
                            f"minimum {config.min_evidence_confidence}%."
                        ),
                        profile_completeness=comp,
                        evidence_confidence=ev,
                    )
                )
                continue

            eligible += 1
            members.append(
                CandidatePoolMember(
                    pool_run_id=run.id,
                    candidate_id=c.id,
                    source_type=c.source_type,
                    eligibility_status=ELIGIBLE,
                    profile_completeness=comp,
                    evidence_confidence=ev,
                )
            )

        if members:
            self.db.bulk_save_objects(members)

        run.eligible_candidates = eligible
        run.excluded_candidates = excluded
        run.duplicates_removed = duplicates
        run.source_breakdown = {k: v for k, v in breakdown.items() if v > 0}
        run.status = "completed"
        run.completed_at = datetime.now(tz=timezone.utc)
        self.db.commit()
        self.db.refresh(run)

        return PoolBuildResult(
            pool_run_id=run.id,
            job_id=run.job_id,
            organization_id=run.organization_id,
            eligible_candidates=run.eligible_candidates,
            excluded_candidates=run.excluded_candidates,
            duplicates_removed=run.duplicates_removed,
            source_breakdown=run.source_breakdown or {},
            status=run.status,
        )

    # ---- read helpers ------------------------------------------------

    def source_counts_for_org(
        self, organization_id: uuid.UUID
    ) -> dict[str, int]:
        """Returns {source_type: count} of candidates currently visible to
        the org per the source-isolation rules.
        """

        result: dict[str, int] = {s.value: 0 for s in SourceType}

        # Org-owned candidates of any non-PATHS_PROFILE type
        owned = (
            self.db.query(Candidate.source_type, Candidate.id)
            .filter(Candidate.owner_organization_id == organization_id)
            .filter(Candidate.status == "active")
            .all()
        )
        for st, _ in owned:
            result[st] = result.get(st, 0) + 1

        # PATHS_PROFILE candidates are visible to any org
        paths_count = (
            self.db.query(Candidate.id)
            .filter(Candidate.source_type == SourceType.PATHS_PROFILE.value)
            .filter(Candidate.status == "active")
            .count()
        )
        result[SourceType.PATHS_PROFILE.value] = paths_count

        return result

    # ---- internals ---------------------------------------------------

    def _enabled_sources_from_config(
        self, config: JobCandidatePoolConfig
    ) -> set[str]:
        enabled: set[str] = set()
        # MANUAL_ADD is always implicitly enabled (org-owned candidates that
        # were keyed by hand). It is treated as an allowed source whenever
        # `use_uploaded_candidates` is on, since manual-add and uploaded
        # share the org-ownership rule.
        for src, flag in SETTINGS_FLAG_MAP.items():
            if getattr(config, flag, False):
                enabled.add(src.value)
        if config.use_uploaded_candidates:
            enabled.add(SourceType.MANUAL_ADD.value)
        return enabled

    def _fetch_candidates_for_org(
        self,
        organization_id: uuid.UUID,
        enabled_sources: set[str],
    ) -> list[Candidate]:
        """Apply isolation rules + enabled-source filter."""

        if not enabled_sources:
            return []

        # PATHS profiles are visible to all orgs
        public_clause = and_(
            Candidate.source_type == SourceType.PATHS_PROFILE.value,
            Candidate.owner_organization_id.is_(None),
        )
        # All other sources must be owned by the requesting org
        owned_clause = and_(
            Candidate.source_type != SourceType.PATHS_PROFILE.value,
            Candidate.owner_organization_id == organization_id,
        )

        stmt = (
            select(Candidate)
            .where(Candidate.status == "active")
            .where(Candidate.source_type.in_(list(enabled_sources)))
            .where(or_(public_clause, owned_clause))
        )
        return list(self.db.execute(stmt).scalars())

    def _dedupe_key(self, c: Candidate) -> str:
        """Cheap email-or-phone dedupe key. A real identity-resolution
        service would be plugged in here; this is intentionally simple and
        deterministic so duplicate counts in preview() match build()."""

        if c.email:
            return f"email:{c.email.strip().lower()}"
        if c.phone:
            return f"phone:{c.phone.strip()}"
        # Fall back to candidate id so two profiles with no contact never
        # collide.
        return f"id:{c.id}"

    def _profile_completeness(self, c: Candidate) -> int:
        """Score 0–100 based on which profile fields are populated. Honest
        stand-in until the Candidate Profile Agent emits a real signal."""

        slots = [
            bool(c.full_name and c.full_name.strip()),
            bool(c.email),
            bool(c.phone),
            bool(c.current_title),
            bool(c.location_text),
            bool(c.headline or c.summary),
            bool(c.skills),
            c.years_experience is not None,
            bool(c.career_level),
            bool(c.desired_job_titles),
        ]
        filled = sum(1 for s in slots if s)
        return int(round(100 * filled / len(slots)))

    def _evidence_confidence(self, c: Candidate) -> int:
        """Score 0–100 derived from candidate skills count + years_exp.

        Replace with the real signal from the Evidence Agent once available.
        Until then this returns a deterministic, monotonically-improving
        score based on what we know about the profile.
        """

        score = 0
        if c.skills:
            score += min(40, len(c.skills) * 4)  # up to 40 from skills
        if c.years_experience is not None and c.years_experience >= 0:
            score += min(30, c.years_experience * 5)  # up to 30 from yoe
        if c.summary or c.headline:
            score += 15
        if c.desired_job_titles:
            score += 10
        if c.career_level:
            score += 5
        return min(100, score)

    def _config_snapshot(self, config: JobCandidatePoolConfig) -> dict:
        return {
            "use_paths_profiles": config.use_paths_profiles,
            "use_sourced_candidates": config.use_sourced_candidates,
            "use_uploaded_candidates": config.use_uploaded_candidates,
            "use_job_fair_candidates": config.use_job_fair_candidates,
            "use_ats_candidates": config.use_ats_candidates,
            "top_k": config.top_k,
            "min_profile_completeness": config.min_profile_completeness,
            "min_evidence_confidence": config.min_evidence_confidence,
            "filters_json": config.filters_json,
        }

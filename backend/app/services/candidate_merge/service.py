"""
PATHS Backend — Candidate duplicate detection + merge (fix2_1.md Feature 2).

Detects *exact identity* duplicate groups inside one organisation —
candidates that share the same normalized name + email + phone — and merges
each group into a single canonical record while preserving history.

Scope: candidates the organisation can act on, i.e. those it owns
(``owner_organization_id == org``) or those that have an application to one
of the org's jobs. Public profiles owned by another org are never touched.

Merge is transactional: all FK repointing + soft-archive + audit happen in
one transaction; any failure rolls the whole thing back.
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.application import Application
from app.db.models.candidate import Candidate
from app.db.models.candidate_merge import CandidateMergeAudit
from app.db.models.job import Job

logger = logging.getLogger(__name__)


# ── Normalization (fix2_1.md §Duplicate Detection Rule) ──────────────────


_SPACES = re.compile(r"\s+")


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    return _SPACES.sub(" ", value).strip().lower()


def normalize_email(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().lower()


def normalize_phone(value: str | None) -> str:
    """Digits only; keep the last 10 so +20-100... and 0100... match."""
    if not value:
        return ""
    digits = re.sub(r"\D", "", value)
    if not digits:
        return ""
    return digits[-10:] if len(digits) > 10 else digits


def _group_id(norm_name: str, norm_email: str, norm_phone: str) -> str:
    raw = f"{norm_name}|{norm_email}|{norm_phone}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


# ── Data shapes ──────────────────────────────────────────────────────────


@dataclass
class DuplicateGroup:
    group_id: str
    normalized_name: str
    normalized_email: str
    normalized_phone: str
    candidates: list[Candidate] = field(default_factory=list)

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)


@dataclass
class MergeOutcome:
    canonical_candidate_id: uuid.UUID
    merged_candidate_ids: list[uuid.UUID]
    details: dict


# ── Detection ────────────────────────────────────────────────────────────


def _org_scoped_candidates(db: Session, organization_id: uuid.UUID) -> list[Candidate]:
    """Candidates the org can act on, excluding already-merged duplicates."""
    job_ids = [
        r[0] for r in db.execute(
            select(Job.id).where(Job.organization_id == organization_id)
        ).all()
    ]
    applicant_ids: set[uuid.UUID] = set()
    if job_ids:
        applicant_ids = {
            r[0] for r in db.execute(
                select(Application.candidate_id)
                .where(Application.job_id.in_(job_ids))
                .distinct()
            ).all()
        }

    stmt = select(Candidate).where(
        Candidate.is_merged_duplicate.is_(False),
        or_(
            Candidate.owner_organization_id == organization_id,
            Candidate.id.in_(applicant_ids) if applicant_ids else False,
        ),
    )
    return list(db.execute(stmt).scalars().all())


def find_duplicate_groups(
    db: Session, organization_id: uuid.UUID,
) -> list[DuplicateGroup]:
    """Return exact name+email+phone duplicate groups (2+ members)."""
    candidates = _org_scoped_candidates(db, organization_id)
    buckets: dict[tuple[str, str, str], list[Candidate]] = {}
    for cand in candidates:
        nname = normalize_name(cand.full_name)
        nemail = normalize_email(cand.email)
        nphone = normalize_phone(cand.phone)
        # Require all three identifiers present — the spec only merges exact,
        # fully-specified identity matches.
        if not (nname and nemail and nphone):
            continue
        buckets.setdefault((nname, nemail, nphone), []).append(cand)

    groups: list[DuplicateGroup] = []
    for (nname, nemail, nphone), members in buckets.items():
        if len(members) < 2:
            continue
        members.sort(key=lambda c: c.created_at or datetime.min.replace(tzinfo=timezone.utc))
        groups.append(
            DuplicateGroup(
                group_id=_group_id(nname, nemail, nphone),
                normalized_name=nname,
                normalized_email=nemail,
                normalized_phone=nphone,
                candidates=members,
            )
        )
    groups.sort(key=lambda g: g.candidate_count, reverse=True)
    return groups


def get_group_by_id(
    db: Session, organization_id: uuid.UUID, group_id: str,
) -> DuplicateGroup | None:
    for g in find_duplicate_groups(db, organization_id):
        if g.group_id == group_id:
            return g
    return None


# ── Canonical selection ──────────────────────────────────────────────────


def _completeness_score(cand: Candidate) -> int:
    score = 0
    for value in (
        cand.email, cand.phone, cand.current_title, cand.location_text,
        cand.headline, cand.summary, cand.years_experience,
    ):
        if value:
            score += 1
    if cand.skills:
        score += min(len(cand.skills), 10)
    return score


def _choose_canonical(db: Session, candidates: list[Candidate]) -> Candidate:
    """Most complete → has applications → oldest."""
    # Count applications per candidate.
    app_counts: dict[uuid.UUID, int] = {}
    for cand in candidates:
        app_counts[cand.id] = db.execute(
            select(text("count(*)")).select_from(Application).where(
                Application.candidate_id == cand.id
            )
        ).scalar() or 0

    def sort_key(c: Candidate):
        return (
            _completeness_score(c),
            app_counts.get(c.id, 0),
            # oldest first → negate timestamp so larger sort-key = better,
            # but we want oldest preferred, so use negative epoch.
            -(c.created_at.timestamp() if c.created_at else 0),
        )

    return max(candidates, key=sort_key)


# ── Merge ────────────────────────────────────────────────────────────────


def _tables_with_candidate_id(db: Session) -> list[str]:
    rows = db.execute(
        text(
            """
            SELECT table_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND column_name = 'candidate_id'
            """
        )
    ).all()
    # Never touch the identity-resolution suggestion table's own bookkeeping
    # or the candidates table itself (handled separately).
    skip = {"candidate_merge_audit"}
    return [r[0] for r in rows if r[0] not in skip]


def _fill_missing_scalars(canonical: Candidate, dup: Candidate) -> None:
    """Fill canonical's empty scalar fields from a duplicate (no overwrite)."""
    scalar_fields = (
        "email", "phone", "current_title", "location_text", "headline",
        "summary", "years_experience", "career_level",
    )
    for f in scalar_fields:
        if not getattr(canonical, f, None) and getattr(dup, f, None):
            setattr(canonical, f, getattr(dup, f))
    # Merge skills (union, preserve order).
    if dup.skills:
        existing = list(canonical.skills or [])
        lower = {s.lower() for s in existing}
        for s in dup.skills:
            if s and s.lower() not in lower:
                existing.append(s)
                lower.add(s.lower())
        canonical.skills = existing or None


def merge_group(
    db: Session,
    *,
    organization_id: uuid.UUID,
    group_id: str,
    performed_by_user_id: uuid.UUID | None,
) -> MergeOutcome:
    """Merge an exact-duplicate group into one canonical candidate.

    Transactional: a single commit at the end; any exception rolls back the
    whole merge so we never leave half-merged candidates.
    """
    group = get_group_by_id(db, organization_id, group_id)
    if group is None or group.candidate_count < 2:
        raise ValueError("Duplicate group not found or has fewer than 2 candidates")

    canonical = _choose_canonical(db, group.candidates)
    duplicates = [c for c in group.candidates if c.id != canonical.id]

    moved: dict[str, int] = {}
    tables = _tables_with_candidate_id(db)

    try:
        for dup in duplicates:
            for table in tables:
                # Each table move in its own SAVEPOINT: on a unique-constraint
                # collision we keep the duplicate's rows on the archived record
                # (history preserved) rather than failing the whole merge.
                sp = db.begin_nested()
                try:
                    result = db.execute(
                        text(
                            f"UPDATE {table} SET candidate_id = :canon "
                            f"WHERE candidate_id = :dup"
                        ),
                        {"canon": str(canonical.id), "dup": str(dup.id)},
                    )
                    moved[table] = moved.get(table, 0) + (result.rowcount or 0)
                    sp.commit()
                except IntegrityError:
                    sp.rollback()
                    logger.info(
                        "[CandidateMerge] collision moving %s for dup %s — "
                        "left on archived record",
                        table, dup.id,
                    )

            _fill_missing_scalars(canonical, dup)
            dup.is_merged_duplicate = True
            dup.merged_into_candidate_id = canonical.id
            dup.duplicate_merge_group_id = group_id
            dup.status = "merged"

        canonical.duplicate_merge_group_id = group_id

        audit = CandidateMergeAudit(
            organization_id=organization_id,
            canonical_candidate_id=canonical.id,
            merged_candidate_ids=[str(d.id) for d in duplicates],
            merge_reason="exact_name_email_phone_match",
            performed_by_user_id=performed_by_user_id,
            details={"moved_rows": moved},
        )
        db.add(audit)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("[CandidateMerge] merge failed; rolled back")
        raise

    return MergeOutcome(
        canonical_candidate_id=canonical.id,
        merged_candidate_ids=[d.id for d in duplicates],
        details={"moved_rows": moved},
    )

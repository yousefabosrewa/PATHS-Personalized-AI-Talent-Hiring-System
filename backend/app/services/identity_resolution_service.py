"""
Identity Resolution Service — finds duplicate candidate records and manages merges.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models.candidate import Candidate
from app.db.models.identity_resolution import CandidateDuplicate, MergeHistory


def _find_matches(
    db: Session,
    field: str,
    value: str | None,
    exclude_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> list[Candidate]:
    """Find candidates in the same org with the same field value."""
    if not value or not value.strip():
        return []
    stmt = (
        select(Candidate)
        .where(
            Candidate.id != exclude_id,
            getattr(Candidate, field) == value.strip(),
        )
    )
    return list(db.execute(stmt).scalars().all())


def find_duplicates(db: Session, candidate_id: uuid.UUID) -> list[dict[str, Any]]:
    """Check a single candidate against all others in their org for duplicates."""
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        return []

    # Determine org from the candidate (they belong to an org via applications)
    from app.db.models.application import Application
    from app.db.models.job import Job

    app_stmt = (
        select(Application.job_id)
        .where(Application.candidate_id == candidate_id)
        .limit(1)
    )
    job_id = db.execute(app_stmt).scalar_one_or_none()
    if not job_id:
        return []
    job = db.get(Job, job_id)
    if not job or not job.organization_id:
        return []
    organization_id = job.organization_id

    check_fields: list[tuple[str, str]] = [
        ("email", "email"),
        ("phone", "phone"),
        ("linkedin_url", None),
        ("github_username", None),
        ("portfolio_url", None),
    ]

    # Try candidate_extras for linkedin_url, github_username, portfolio_url
    from app.db.models.candidate_extras import CandidateLink

    suggestions: list[dict[str, Any]] = []

    # Check direct fields on Candidate
    for field_name, _ in [("email", "email"), ("phone", "phone")]:
        value = getattr(candidate, field_name, None)
        if value:
            matches = _find_matches(db, field_name, value, candidate_id, organization_id)
            for m in matches:
                suggestions.append({
                    "candidate_id": m.id,
                    "match_reason": field_name,
                    "match_value": value,
                })

    # Check link fields via CandidateLink
    link_fields = {
        "linkedin_url": "linkedin_url",
        "github_username": "github_username",
        "portfolio_url": "portfolio_url",
    }
    links_stmt = select(CandidateLink).where(CandidateLink.candidate_id == candidate_id)
    links = list(db.execute(links_stmt).scalars().all())

    for link in links:
        for reason, attr in link_fields.items():
            value = getattr(link, attr, None)
            if not value or not str(value).strip():
                continue
            # Find other candidates with the same link value
            other_links = (
                select(CandidateLink)
                .where(
                    CandidateLink.candidate_id != candidate_id,
                    getattr(CandidateLink, attr) == str(value).strip(),
                )
            )
            other = list(db.execute(other_links).scalars().all())
            for ol in other:
                suggestions.append({
                    "candidate_id": ol.candidate_id,
                    "match_reason": reason,
                    "match_value": str(value),
                })

    return suggestions


def _compute_confidence(reason: str) -> float:
    """Compute a confidence score based on match reason."""
    scores = {
        "email": 0.95,
        "phone": 0.90,
        "linkedin_url": 0.85,
        "github_username": 0.80,
        "portfolio_url": 0.75,
    }
    return scores.get(reason, 0.5)


def suggest_duplicates(db: Session, organization_id: uuid.UUID) -> list[CandidateDuplicate]:
    """Scan all candidates in an organization and return any duplicates found."""
    from app.db.models.application import Application
    from app.db.models.job import Job

    # Get all candidates that have applications in this org's jobs
    jobs_stmt = select(Job.id).where(Job.organization_id == organization_id)
    job_ids = [r[0] for r in db.execute(jobs_stmt).all()]
    if not job_ids:
        return []

    app_stmt = (
        select(Application.candidate_id)
        .where(Application.job_id.in_(job_ids))
        .distinct()
    )
    candidate_ids = [r[0] for r in db.execute(app_stmt).all()]

    created: list[CandidateDuplicate] = []

    for cid in candidate_ids:
        dups = find_duplicates(db, cid)
        for dup in dups:
            dup_candidate_id = dup["candidate_id"]
            match_reason = dup["match_reason"]
            match_value = dup["match_value"]

            # Check if duplicate already exists (in either direction)
            existing = db.execute(
                select(CandidateDuplicate).where(
                    or_(
                        (CandidateDuplicate.candidate_id_a == cid) &
                        (CandidateDuplicate.candidate_id_b == dup_candidate_id),
                        (CandidateDuplicate.candidate_id_a == dup_candidate_id) &
                        (CandidateDuplicate.candidate_id_b == cid),
                    ),
                    CandidateDuplicate.match_reason == match_reason,
                    CandidateDuplicate.match_value == match_value,
                )
            ).scalar_one_or_none()

            if existing:
                continue

            confidence = _compute_confidence(match_reason)
            cd = CandidateDuplicate(
                candidate_id_a=cid,
                candidate_id_b=dup_candidate_id,
                organization_id=organization_id,
                match_reason=match_reason,
                match_value=match_value,
                confidence=confidence,
                status="pending",
            )
            db.add(cd)
            created.append(cd)

    if created:
        db.commit()
        for c in created:
            db.refresh(c)

    return created


def approve_merge(
    db: Session,
    duplicate_id: uuid.UUID,
    reviewer: uuid.UUID,
    notes: str | None = None,
) -> CandidateDuplicate:
    """Approve a duplicate suggestion and perform the merge."""
    dup = db.get(CandidateDuplicate, duplicate_id)
    if not dup:
        raise ValueError("Duplicate suggestion not found")
    if dup.status != "pending":
        raise ValueError(f"Duplicate already {dup.status}")

    dup.status = "approved"
    dup.reviewed_by = reviewer
    dup.reviewed_at = datetime.now(timezone.utc)
    dup.notes = notes
    dup.merged_into_candidate_id = dup.candidate_id_a

    # Create merge history record
    mh = MergeHistory(
        organization_id=dup.organization_id,
        kept_candidate_id=dup.candidate_id_a,
        removed_candidate_id=dup.candidate_id_b,
        merged_by=reviewer,
        merge_reason=notes,
        audit_log={
            "match_reason": dup.match_reason,
            "match_value": dup.match_value,
            "confidence": dup.confidence,
        },
    )
    db.add(mh)
    db.commit()
    db.refresh(dup)
    return dup


def reject_merge(
    db: Session,
    duplicate_id: uuid.UUID,
    reviewer: uuid.UUID,
    notes: str | None = None,
) -> CandidateDuplicate:
    """Reject a duplicate suggestion without merging."""
    dup = db.get(CandidateDuplicate, duplicate_id)
    if not dup:
        raise ValueError("Duplicate suggestion not found")
    if dup.status != "pending":
        raise ValueError(f"Duplicate already {dup.status}")

    dup.status = "rejected"
    dup.reviewed_by = reviewer
    dup.reviewed_at = datetime.now(timezone.utc)
    dup.notes = notes
    db.commit()
    db.refresh(dup)
    return dup


def get_merge_history(
    db: Session,
    organization_id: uuid.UUID,
) -> list[MergeHistory]:
    """Return all merge history records for an organization."""
    stmt = (
        select(MergeHistory)
        .where(MergeHistory.organization_id == organization_id)
        .order_by(MergeHistory.merged_at.desc())
    )
    return list(db.execute(stmt).scalars().all())

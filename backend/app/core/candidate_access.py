"""
Candidate data visibility for mixed candidate vs organisation users.

No schema changes — uses existing Application, Job, Interview, and the
Candidate sourcing-pool flags.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.application import Application
from app.db.models.candidate import Candidate
from app.db.models.interview import Interview
from app.db.models.job import Job


# Candidate.source_type values that mean "this person is in the platform's
# open sourcing pool" — i.e. visible to recruiters for discovery. Candidates
# with other source_types (private imports, etc.) still require an explicit
# hiring touchpoint to be viewable.
_OPEN_POOL_SOURCE_TYPES = (
    "paths_profile",
    "imported",
    "uploaded",
    "manual",
)


def org_can_view_candidate(db: Session, org_id: uuid.UUID, candidate_id: uuid.UUID) -> bool:
    """True if the organisation may view this candidate.

    Allowed when ANY of the following holds:
      1. The org has an Application for the candidate on one of its Jobs.
      2. The org has an Interview record with the candidate.
      3. The org already owns this candidate row (sourced into its pool).
      4. The candidate is in the platform's open sourcing pool
         (an active candidate with an internal-platform source_type) —
         this is what makes the recruiter Sourcing page work without
         requiring the org to have engaged with each profile first.
    """
    app_row = db.execute(
        select(Application.id)
        .join(Job, Job.id == Application.job_id)
        .where(
            Application.candidate_id == candidate_id,
            Job.organization_id == org_id,
        )
        .limit(1),
    ).scalar_one_or_none()
    if app_row is not None:
        return True

    inv_row = db.execute(
        select(Interview.id)
        .where(
            Interview.candidate_id == candidate_id,
            Interview.organization_id == org_id,
        )
        .limit(1),
    ).scalar_one_or_none()
    if inv_row is not None:
        return True

    # Sourcing visibility — owned-by-org OR active platform-pool candidate.
    cand = db.execute(
        select(Candidate.owner_organization_id, Candidate.source_type, Candidate.status)
        .where(Candidate.id == candidate_id)
    ).first()
    if cand is None:
        return False
    owner_org_id, source_type, status = cand
    if owner_org_id == org_id:
        return True
    if (source_type or "") in _OPEN_POOL_SOURCE_TYPES and (status or "active") == "active":
        return True
    return False

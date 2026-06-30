"""
PATHS Backend — Targeted demo-data disable.

Soft-disables a hard-coded list of demo / test accounts that the read-only
audit identified. Does NOT hard-delete anything — every row is preserved,
only is_active=False (and Organization.status='suspended' for orgs) is set
so foreign keys, jobs, applications, and audit history are kept intact.

Run once after Phase 1 migration is applied.

The lists below are the ones explicitly approved in the chat conversation
that produced this script. To extend or change them, edit DEMO_USER_EMAILS
or DEMO_ORG_SLUGS — never blindly add patterns.

Usage:
    cd backend
    python scripts/disable_demo_data.py             # show plan + apply
    python scripts/disable_demo_data.py --dry-run   # show plan only
"""

from __future__ import annotations

import argparse
import io
import os
import sys
from datetime import datetime, timezone

# Make `app` importable when invoked as `python scripts/disable_demo_data.py`
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(HERE)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from sqlalchemy import select  # noqa: E402

# Register all model relationships before queries.
from app.db.models import (  # noqa: E402,F401
    candidate as _m_candidate,
    candidate_extras as _m_candidate_extras,
    cv_entities as _m_cv_entities,
    job as _m_job,
    job_ingestion as _m_job_ingestion,
    application as _m_application,
    ingestion as _m_ingestion,
    reference as _m_reference,
    sync as _m_sync,
    job_scraper as _m_job_scraper,
    scoring as _m_scoring,
    organization_matching as _m_organization_matching,
    interview as _m_interview,
    decision_support as _m_decision_support,
    screening as _m_screening,
    outreach_agent as _m_outreach_agent,
    evidence as _m_evidence,
    bias_fairness as _m_bias_fairness,
    hitl as _m_hitl,
    organization as _m_organization,
)

from app.core.database import SessionLocal, engine  # noqa: E402
from app.db.models.user import User  # noqa: E402
from app.db.models.organization import Organization, OrganizationStatus  # noqa: E402
from app.db.models.application import OrganizationMember  # noqa: E402
from app.db.repositories.sync_status import write_audit_log  # noqa: E402

engine.echo = False


# Hard-coded list approved by the operator. Do not extend silently.
DEMO_USER_EMAILS: list[str] = [
    "admin@acme-corp.com",
    "admin1@beta-corp.com",
    "admin@gamma-inc.com",
    "hr@gamma-inc.com",
    "login_candidate@test.com",
    "access_candidate_jobs@test.com",
    "hacker@test.com",
]

DEMO_ORG_SLUGS: list[str] = [
    "acme-corp",
    "beta-corp",
    "gamma-inc",
]

# Explicit safety net: emails / slugs that must NEVER be touched by this
# script. If someone adds an entry to DEMO_USER_EMAILS that matches one of
# these by accident, the script aborts.
PROTECTED_USER_EMAILS = {"elswesyosama@gmail.com"}
PROTECTED_ORG_SLUGS = {"elswesy", "paths-inc"}


def _validate_lists() -> None:
    bad_users = set(DEMO_USER_EMAILS) & PROTECTED_USER_EMAILS
    if bad_users:
        raise SystemExit(f"ABORT — DEMO_USER_EMAILS overlaps with protected list: {bad_users}")
    bad_orgs = set(DEMO_ORG_SLUGS) & PROTECTED_ORG_SLUGS
    if bad_orgs:
        raise SystemExit(f"ABORT — DEMO_ORG_SLUGS overlaps with protected list: {bad_orgs}")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _disable_users(db, dry_run: bool) -> tuple[int, int]:
    """Set is_active=False for each user in DEMO_USER_EMAILS that exists.

    Returns (changed, skipped). Active memberships are also deactivated so
    org dashboards can't surface them.
    """
    changed = skipped = 0
    for email in DEMO_USER_EMAILS:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            print(f"  [skip] user not found: {email}")
            skipped += 1
            continue
        if not user.is_active:
            print(f"  [unchanged] user already disabled: {email}")
            skipped += 1
            continue

        # Deactivate the user.
        if not dry_run:
            user.is_active = False
            # Deactivate any active memberships.
            for m in db.execute(
                select(OrganizationMember).where(
                    OrganizationMember.user_id == user.id,
                    OrganizationMember.is_active == True,  # noqa: E712
                )
            ).scalars().all():
                m.is_active = False
            write_audit_log(
                db,
                action="platform_admin.user_disabled",
                entity_type="user",
                entity_id=user.id,
                actor_user_id=None,  # script-driven; no human actor
                old_value={"is_active": True},
                new_value={"is_active": False, "reason": "demo cleanup"},
            )
        print(f"  [disable] user: {email}")
        changed += 1
    return changed, skipped


def _disable_orgs(db, dry_run: bool) -> tuple[int, int]:
    changed = skipped = 0
    for slug in DEMO_ORG_SLUGS:
        org = db.execute(select(Organization).where(Organization.slug == slug)).scalar_one_or_none()
        if org is None:
            print(f"  [skip] org not found: {slug}")
            skipped += 1
            continue
        if (
            not org.is_active
            and org.status == OrganizationStatus.SUSPENDED.value
        ):
            print(f"  [unchanged] org already suspended: {slug}")
            skipped += 1
            continue

        if not dry_run:
            old_status = org.status
            org.is_active = False
            org.status = OrganizationStatus.SUSPENDED.value
            org.suspended_at = _now()
            org.suspended_reason = "demo cleanup"
            # Deactivate every membership in this org so org-list endpoints
            # don't surface phantom users.
            for m in db.execute(
                select(OrganizationMember).where(
                    OrganizationMember.organization_id == org.id,
                    OrganizationMember.is_active == True,  # noqa: E712
                )
            ).scalars().all():
                m.is_active = False
            write_audit_log(
                db,
                action="platform_admin.org_suspended",
                entity_type="organization",
                entity_id=org.id,
                actor_user_id=None,
                old_value={"status": old_status, "is_active": True},
                new_value={
                    "status": OrganizationStatus.SUSPENDED.value,
                    "is_active": False,
                    "reason": "demo cleanup",
                },
            )
        print(f"  [suspend] org: {slug}")
        changed += 1
    return changed, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="Disable demo users and demo organizations.")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan without committing.")
    args = parser.parse_args()

    _validate_lists()

    print("PATHS — disable_demo_data")
    print(
        f"Mode: {'DRY RUN — no changes will be committed' if args.dry_run else 'APPLY — changes will be committed'}"
    )
    print(f"Users to disable: {len(DEMO_USER_EMAILS)}")
    for e in DEMO_USER_EMAILS:
        print(f"  - {e}")
    print(f"Orgs to suspend: {len(DEMO_ORG_SLUGS)}")
    for s in DEMO_ORG_SLUGS:
        print(f"  - {s}")
    print()

    with SessionLocal() as db:
        print("Users:")
        u_changed, u_skipped = _disable_users(db, dry_run=args.dry_run)
        print()
        print("Organizations:")
        o_changed, o_skipped = _disable_orgs(db, dry_run=args.dry_run)

        if args.dry_run:
            db.rollback()
            print("\nDry run — rolled back. Re-run without --dry-run to apply.")
        else:
            db.commit()
            print("\nCommitted.")

    print()
    print(
        f"Summary: users changed={u_changed} skipped={u_skipped}; "
        f"orgs changed={o_changed} skipped={o_skipped}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

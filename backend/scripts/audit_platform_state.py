"""
PATHS Backend — Platform-state read-only audit.

Inspects the live database BEFORE any RBAC / approval-flow migration runs.
Pure SELECTs only. Does NOT update, delete, disable, or alter anything.

What it reports:
  1. Total user count, broken down by `account_type`.
  2. Every user whose `account_type` is NOT in {"candidate", "organization_member"}.
  3. Every user whose email matches admin-like patterns (admin/test/demo/example).
     (Match is informational only — no action is taken.)
  4. Total organization count + count where `is_active=True`.
  5. Recent organizations (last 25 by created_at) with name/slug/is_active.
  6. Total organization_members count + breakdown by role_code.
  7. Every distinct `role_code` value currently in the DB (so we know what
     the new enum migration must accommodate).
  8. Sanity-check rows that future migration must consider:
       - role_codes outside {org_admin, hiring_manager, recruiter, hr,
         hr_manager, interviewer, member, admin}
       - account_types outside {candidate, organization_member}.

Usage:
    cd backend
    python scripts/audit_platform_state.py

Exits 0 on success regardless of what is found — this is a report, not a check.
"""

from __future__ import annotations

import io
import os
import sys
from collections import Counter
from datetime import datetime, timezone

# Force UTF-8 stdout/stderr so the report's Unicode separators (—, ·, …) print
# cleanly on Windows consoles that default to cp1252.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

# Make sure `app` is importable when running as `python scripts/audit_platform_state.py`
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(HERE)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from sqlalchemy import func, select  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402

# Quiet down SQLAlchemy echo (settings.debug enables echo=True). This is a
# read-only audit; raw SQL chatter just clutters the report.
engine.echo = False

# Register every mapper before issuing queries. SQLAlchemy needs every model
# class loaded into the registry so that relationships (e.g. Candidate ->
# EvidenceItem) resolve at query time. The package __init__ does not import
# every module, so we explicitly load the ones touching evidence/HITL/etc.
from app.db.models import Organization, User  # noqa: E402,F401
from app.db.models.application import OrganizationMember  # noqa: E402
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
)


KNOWN_ACCOUNT_TYPES = {"candidate", "organization_member"}
EXPECTED_ROLE_CODES = {
    "org_admin",
    "hiring_manager",
    "recruiter",
    "hr",
    "hr_manager",     # legacy — will be merged into hr/hiring_manager during migration
    "interviewer",
    "member",         # legacy — will be remapped to recruiter
    "admin",          # legacy — will be remapped to org_admin
}
ADMIN_LIKE_EMAIL_PATTERNS = ("admin", "test", "demo", "example", "root", "super")


# ── Output helpers ───────────────────────────────────────────────────────────


def header(title: str) -> None:
    bar = "=" * 78
    print(f"\n{bar}\n  {title}\n{bar}")


def subheader(title: str) -> None:
    print(f"\n— {title} —")


def warn(msg: str) -> None:
    print(f"  ! {msg}")


def info(msg: str) -> None:
    print(f"  · {msg}")


def fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return "-"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


# ── Audit sections ───────────────────────────────────────────────────────────


def audit_user_counts(db) -> None:
    header("1. USERS — Account type distribution")
    total = db.execute(select(func.count(User.id))).scalar_one()
    info(f"Total users: {total}")

    rows = db.execute(
        select(User.account_type, func.count(User.id))
        .group_by(User.account_type)
        .order_by(func.count(User.id).desc())
    ).all()

    if not rows:
        warn("No users in the database.")
        return

    subheader("Breakdown by account_type")
    for account_type, n in rows:
        flag = "" if account_type in KNOWN_ACCOUNT_TYPES else "  <-- UNKNOWN account_type"
        print(f"    {account_type or '(null)':<30} {n}{flag}")


def audit_unexpected_account_types(db) -> None:
    header("2. USERS — Unexpected account_types (outside candidate/organization_member)")
    rows = db.execute(
        select(User.id, User.email, User.full_name, User.account_type, User.is_active, User.created_at)
        .where(~User.account_type.in_(KNOWN_ACCOUNT_TYPES))
        .order_by(User.created_at.desc())
    ).all()

    if not rows:
        info("None. All users use candidate or organization_member. [OK]")
        return

    warn(f"Found {len(rows)} user(s) with unexpected account_type — review before migration:")
    for row in rows:
        print(
            f"    {str(row.id)[:8]}…  "
            f"email={row.email!r:<40}  "
            f"type={row.account_type!r:<22}  "
            f"active={row.is_active}  "
            f"created={fmt_dt(row.created_at)}"
        )


def audit_admin_like_emails(db) -> None:
    header("3. USERS — Admin-like email patterns (informational only)")
    print("  Matches emails containing any of: " + ", ".join(repr(p) for p in ADMIN_LIKE_EMAIL_PATTERNS))
    print("  No action will be taken automatically. You decide what to do with these.\n")

    matches: list[User] = []
    all_users = db.execute(
        select(User).order_by(User.created_at.desc())
    ).scalars().all()

    for u in all_users:
        email_lower = (u.email or "").lower()
        if any(pat in email_lower for pat in ADMIN_LIKE_EMAIL_PATTERNS):
            matches.append(u)

    if not matches:
        info("No admin-like emails found. [OK]")
        return

    warn(f"Found {len(matches)} user(s) with admin-like emails:")
    for u in matches:
        roles = [m.role_code for m in (u.memberships or []) if m.is_active]
        roles_s = ",".join(roles) if roles else "(no active membership)"
        print(
            f"    {str(u.id)[:8]}…  "
            f"email={u.email!r:<45}  "
            f"name={u.full_name!r:<30}  "
            f"type={u.account_type!r:<22}  "
            f"active={u.is_active}  "
            f"roles=[{roles_s}]  "
            f"created={fmt_dt(u.created_at)}"
        )


def audit_organizations(db) -> None:
    header("4. ORGANIZATIONS — Counts and recent rows")
    total = db.execute(select(func.count(Organization.id))).scalar_one()
    active = db.execute(
        select(func.count(Organization.id)).where(Organization.is_active == True)  # noqa: E712
    ).scalar_one()
    info(f"Total organizations: {total}")
    info(f"is_active=True:       {active}")
    info(f"is_active=False:      {total - active}")

    if total == 0:
        return

    subheader("Most recent 25 organizations (newest first)")
    rows = db.execute(
        select(Organization.id, Organization.name, Organization.slug,
               Organization.industry, Organization.is_active,
               Organization.contact_email, Organization.created_at)
        .order_by(Organization.created_at.desc())
        .limit(25)
    ).all()

    for r in rows:
        print(
            f"    {str(r.id)[:8]}…  "
            f"name={r.name!r:<35}  "
            f"slug={r.slug!r:<28}  "
            f"active={r.is_active!s:<5}  "
            f"contact={r.contact_email!r:<40}  "
            f"created={fmt_dt(r.created_at)}"
        )


def audit_memberships(db) -> None:
    header("5. ORGANIZATION_MEMBERS — Distribution by role_code")
    total = db.execute(select(func.count(OrganizationMember.id))).scalar_one()
    active = db.execute(
        select(func.count(OrganizationMember.id))
        .where(OrganizationMember.is_active == True)  # noqa: E712
    ).scalar_one()
    info(f"Total memberships: {total}")
    info(f"is_active=True:    {active}")
    info(f"is_active=False:   {total - active}")

    if total == 0:
        return

    subheader("Breakdown by (role_code, is_active)")
    rows = db.execute(
        select(OrganizationMember.role_code, OrganizationMember.is_active,
               func.count(OrganizationMember.id))
        .group_by(OrganizationMember.role_code, OrganizationMember.is_active)
        .order_by(OrganizationMember.role_code, OrganizationMember.is_active)
    ).all()
    for role, is_active, n in rows:
        flag = "" if role in EXPECTED_ROLE_CODES else "  <-- UNKNOWN role_code"
        print(f"    role={role!r:<22}  active={is_active!s:<5}  count={n}{flag}")

    subheader("Distinct role_code values seen")
    distinct = db.execute(
        select(OrganizationMember.role_code).distinct()
    ).scalars().all()
    for role in sorted(distinct, key=lambda r: (r is None, r or "")):
        flag = "" if role in EXPECTED_ROLE_CODES else "  <-- not in expected set"
        print(f"    {role!r}{flag}")


def audit_migration_blockers(db) -> None:
    header("6. MIGRATION-BLOCKER PRECHECK")
    print("  These rows must be considered before converting the columns to ENUMs.\n")

    # account_type values outside the two known
    bad_at = db.execute(
        select(User.account_type, func.count(User.id))
        .where(~User.account_type.in_(KNOWN_ACCOUNT_TYPES))
        .group_by(User.account_type)
    ).all()
    if bad_at:
        warn("Users with unmapped account_type values:")
        for at, n in bad_at:
            print(f"    account_type={at!r:<25} -> {n} user(s)")
    else:
        info("All users.account_type values are in {candidate, organization_member}. [OK]")

    # role_code values outside the expected set
    bad_rc = db.execute(
        select(OrganizationMember.role_code, func.count(OrganizationMember.id))
        .where(~OrganizationMember.role_code.in_(EXPECTED_ROLE_CODES))
        .group_by(OrganizationMember.role_code)
    ).all()
    if bad_rc:
        warn("Memberships with role_code outside the expected set:")
        for rc, n in bad_rc:
            print(f"    role_code={rc!r:<25} -> {n} membership(s)")
    else:
        info("All organization_members.role_code values are in the expected set. [OK]")

    # Mapping plan that will run during migration:
    print()
    print("  Migration mapping (informational, NOT executed by this script):")
    print("    role_code 'admin'  -> 'org_admin'")
    print("    role_code 'member' -> 'recruiter'")
    print("    role_code 'hr_manager' -> kept (will be folded into the new enum if used)")
    print("    role_code 'interviewer' -> kept (and added to the active org-roles set)")


def audit_user_org_join(db) -> None:
    header("7. USER ↔ ORGANIZATION snapshot (most recent 25 active memberships)")
    rows = db.execute(
        select(
            OrganizationMember.id,
            OrganizationMember.role_code,
            OrganizationMember.is_active,
            User.email,
            User.full_name,
            User.account_type,
            Organization.name.label("org_name"),
            Organization.is_active.label("org_active"),
            OrganizationMember.joined_at,
        )
        .join(User, User.id == OrganizationMember.user_id)
        .join(Organization, Organization.id == OrganizationMember.organization_id)
        .where(OrganizationMember.is_active == True)  # noqa: E712
        .order_by(OrganizationMember.joined_at.desc())
        .limit(25)
    ).all()

    if not rows:
        info("No active memberships.")
        return

    for r in rows:
        print(
            f"    org={r.org_name!r:<30}  "
            f"org_active={r.org_active!s:<5}  "
            f"user={r.email!r:<40}  "
            f"acct={r.account_type!r:<22}  "
            f"role={r.role_code!r:<22}  "
            f"joined={fmt_dt(r.joined_at)}"
        )


def main() -> int:
    print("PATHS — Read-only platform-state audit")
    print(f"Started at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("This script performs SELECT queries only. No data is modified.")

    with SessionLocal() as db:
        try:
            audit_user_counts(db)
            audit_unexpected_account_types(db)
            audit_admin_like_emails(db)
            audit_organizations(db)
            audit_memberships(db)
            audit_user_org_join(db)
            audit_migration_blockers(db)
        except Exception as exc:  # pragma: no cover
            print(f"\n!! Audit aborted due to error: {exc}")
            return 1

    header("DONE — Audit complete. No data was modified.")
    print("  Review the output above. Confirm in chat before any migration runs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

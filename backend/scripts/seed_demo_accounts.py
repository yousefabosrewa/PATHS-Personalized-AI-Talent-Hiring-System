"""
PATHS — seed_demo_accounts.py

Creates one demo account for each customer segment:

  1. Platform Admin   — admin@paths.dev          / Admin@PATHS2025
  2. Org Admin        — recruiter@acme-demo.com  / Recruiter@PATHS2025
     (org slug: acme-demo)
  3. Candidate        — candidate@paths.dev       / Candidate@PATHS2025

Safe to re-run (idempotent). Prints a table of results.
"""

from __future__ import annotations

import os
import sys
import io

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

import uuid
from sqlalchemy import select

from app.db.models import (  # noqa: F401 — force relationship resolution
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

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.db.models.user import User
from app.db.models.organization import Organization
from app.db.models.application import OrganizationMember
from app.db.models.candidate import Candidate

get_settings()  # force .env load


ACCOUNTS = [
    {
        "segment":      "Platform Admin",
        "email":        "admin@paths.dev",
        "password":     "Admin@PATHS2025",
        "full_name":    "PATHS Admin",
        "account_type": "platform_admin",
    },
    {
        "segment":      "Org Admin (Recruiter)",
        "email":        "recruiter@acme-demo.com",
        "password":     "Recruiter@PATHS2025",
        "full_name":    "Demo Recruiter",
        "account_type": "organization_member",
        "org_name":     "Acme Demo Corp",
        "org_slug":     "acme-demo",
    },
    {
        "segment":      "Candidate",
        "email":        "candidate@paths.dev",
        "password":     "Candidate@PATHS2025",
        "full_name":    "Demo Candidate",
        "account_type": "candidate",
    },
]


def main() -> int:
    print("PATHS — seed_demo_accounts")
    print("=" * 60)

    with SessionLocal() as db:
        for acct in ACCOUNTS:
            email = acct["email"]
            want_type = acct["account_type"]
            user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
            notes: list[str] = []

            # ── User row: create, or self-heal an existing one ────
            if user is None:
                user = User(
                    email=email,
                    full_name=acct["full_name"],
                    hashed_password=hash_password(acct["password"]),
                    account_type=want_type,
                    is_active=True,
                )
                db.add(user)
                db.flush()  # get user.id
                verb = "CREATED"
            else:
                verb = "OK"
                # Heal an invalid/legacy account_type (e.g. a prior run that
                # wrote the non-existent "organization" type).
                if user.account_type != want_type:
                    notes.append(f"account_type {user.account_type!r}->{want_type!r}")
                    user.account_type = want_type
                if not user.is_active:
                    user.is_active = True
                    notes.append("reactivated")

            # ── Org member: ensure active org + active membership ─
            if want_type == "organization_member":
                org = db.execute(
                    select(Organization).where(Organization.slug == acct["org_slug"])
                ).scalar_one_or_none()
                if org is None:
                    org = Organization(
                        name=acct["org_name"],
                        slug=acct["org_slug"],
                        contact_email=email,
                        is_active=True,
                        status="active",
                    )
                    db.add(org)
                    db.flush()
                    notes.append(f"org created ({org.slug})")
                elif org.status != "active":
                    org.status = "active"
                    org.is_active = True
                    notes.append("org activated")

                membership = db.execute(
                    select(OrganizationMember).where(
                        OrganizationMember.user_id == user.id,
                        OrganizationMember.organization_id == org.id,
                    )
                ).scalar_one_or_none()
                if membership is None:
                    db.add(OrganizationMember(
                        organization_id=org.id,
                        user_id=user.id,
                        role_code="org_admin",
                        is_active=True,
                    ))
                    db.flush()
                    notes.append("membership created (org_admin)")
                elif not membership.is_active:
                    membership.is_active = True
                    notes.append("membership reactivated")

            # ── Candidate: ensure a Candidate profile exists ──────
            if want_type == "candidate":
                cand = db.execute(
                    select(Candidate).where(Candidate.user_id == user.id)
                ).scalar_one_or_none()
                if cand is None:
                    db.add(Candidate(
                        user_id=user.id,
                        full_name=acct["full_name"],
                        email=email,
                        status="active",
                        source_type="paths_profile",
                        skills=["Python", "JavaScript", "Communication"],
                        current_title="Software Engineer",
                    ))
                    db.flush()
                    notes.append("candidate profile created")

            suffix = f"  ({'; '.join(notes)})" if notes else ""
            print(f"[{verb:<7}] {acct['segment']:<22} {email}{suffix}")

        db.commit()

    print()
    print("=" * 60)
    print("Demo accounts ready.")
    print()
    print(f"{'Segment':<24} {'Email':<30} {'Password'}")
    print("-" * 75)
    for a in ACCOUNTS:
        print(f"  {a['segment']:<22} {a['email']:<30} {a['password']}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

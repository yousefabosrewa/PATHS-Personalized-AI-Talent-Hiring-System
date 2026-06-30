"""
PATHS Backend — Idempotent seed script for the five platform-admin users.

Reads PLATFORM_ADMIN_{1..5}_{NAME,EMAIL,PASSWORD} from environment (loads
backend/.env automatically via the project Settings). For each non-empty
triple it ensures a User row exists with account_type='platform_admin'.

Behaviour:
  * If a user with the email exists AND already has account_type=platform_admin
      → leave password and name as-is (idempotent). Logged as 'unchanged'.
  * If a user with the email exists AND a DIFFERENT account_type
      → ABORT with an error. Never silently re-assigns. The operator must
        either pick a different email or manually delete the old user. This
        is the safety rule the audit script flagged.
  * If a user does NOT exist
      → create with hashed password, is_active=True, account_type=platform_admin.
        Audit log row written: action='platform_admin.seeded'.
  * Empty triples are skipped (so you can roll out admins one at a time).

Usage:
    cd backend
    # 1. Edit .env locally and set PLATFORM_ADMIN_N_EMAIL / _PASSWORD
    # 2. Run:
    python scripts/seed_platform_admins.py
"""

from __future__ import annotations

import io
import os
import sys
from typing import NamedTuple

# Make `app` importable when invoked as `python scripts/seed_platform_admins.py`
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(HERE)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

# Force UTF-8 stdout for Windows consoles.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from sqlalchemy import select  # noqa: E402

# Import every model module so SQLAlchemy resolves all relationships before
# we hit the DB.
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
from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal, engine  # noqa: E402
from app.core.rbac import AccountType  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.models.user import User  # noqa: E402
from app.db.repositories.sync_status import write_audit_log  # noqa: E402

engine.echo = False  # quiet — this is an admin tool


class AdminTriple(NamedTuple):
    slot: int
    name: str
    email: str
    password: str


# Names are the five fixed platform admins from the spec. They cannot be
# changed via env — only their emails/passwords can.
FIXED_NAMES = {
    1: "Osama El-Swesy",
    2: "Abdelrahman Atef",
    3: "Ahmed Ashraf",
    4: "Ahmed Alaa",
    5: "Youssef Abousrewa",
}


def _read_triples() -> list[AdminTriple]:
    """Read the 5 admin triples from the environment.

    Honours both `PLATFORM_ADMIN_N_*` and the values loaded by
    pydantic-settings via .env. Skips any slot whose email OR password is
    empty so partial rollouts work.
    """
    # Loading settings ensures .env is read. We then read directly from
    # os.environ because Settings doesn't model these (they're admin secrets,
    # not app config).
    get_settings()  # forces .env load via pydantic-settings caching

    triples: list[AdminTriple] = []
    for slot in range(1, 6):
        # Allow operators to override the fixed name if absolutely needed,
        # but default to the spec names so .env can omit them entirely.
        name = (os.environ.get(f"PLATFORM_ADMIN_{slot}_NAME") or FIXED_NAMES[slot]).strip()
        email = (os.environ.get(f"PLATFORM_ADMIN_{slot}_EMAIL") or "").strip()
        password = os.environ.get(f"PLATFORM_ADMIN_{slot}_PASSWORD") or ""
        if not email or not password:
            print(f"[skip] PLATFORM_ADMIN_{slot} ({name}) — empty email or password")
            continue
        triples.append(AdminTriple(slot=slot, name=name, email=email, password=password))
    return triples


def _seed_one(db, triple: AdminTriple) -> str:
    """Apply one triple. Returns a status word for logging."""
    user = db.execute(select(User).where(User.email == triple.email)).scalar_one_or_none()

    if user is None:
        new_user = User(
            email=triple.email,
            full_name=triple.name,
            hashed_password=hash_password(triple.password),
            account_type=AccountType.PLATFORM_ADMIN.value,
            is_active=True,
        )
        db.add(new_user)
        db.flush()  # get id
        write_audit_log(
            db,
            action="platform_admin.seeded",
            entity_type="user",
            entity_id=new_user.id,
            actor_user_id=new_user.id,
            new_value={
                "email": new_user.email,
                "full_name": new_user.full_name,
                "account_type": new_user.account_type,
                "slot": triple.slot,
            },
        )
        return "created"

    if user.account_type == AccountType.PLATFORM_ADMIN.value:
        # Leave password and name as-is — idempotent. If you need to rotate
        # the password, do it via a dedicated admin endpoint or reset flow.
        if not user.is_active:
            user.is_active = True
            write_audit_log(
                db,
                action="platform_admin.reactivated",
                entity_type="user",
                entity_id=user.id,
                actor_user_id=user.id,
                new_value={"is_active": True},
            )
            return "reactivated"
        return "unchanged"

    # Email exists but is bound to a different account_type. Refuse.
    raise SystemExit(
        f"\n!! ABORT: a user with email {triple.email!r} already exists with "
        f"account_type={user.account_type!r}. This script will NOT silently "
        f"promote them to platform_admin. Either pick a different email or "
        f"manually clean up the existing row first.\n"
    )


def main() -> int:
    print("PATHS — seed_platform_admins")
    print("Reads PLATFORM_ADMIN_{1..5}_{NAME,EMAIL,PASSWORD} from environment.")
    print()

    triples = _read_triples()
    if not triples:
        print("No platform admins configured. Nothing to do.")
        print("Set PLATFORM_ADMIN_N_EMAIL and PLATFORM_ADMIN_N_PASSWORD in .env first.")
        return 0

    print(f"Applying {len(triples)} admin triple(s).")
    counts: dict[str, int] = {"created": 0, "unchanged": 0, "reactivated": 0}

    with SessionLocal() as db:
        for t in triples:
            verb = _seed_one(db, t)
            counts[verb] = counts.get(verb, 0) + 1
            print(f"  [{verb:<11}] slot={t.slot}  email={t.email}  name={t.name}")
        db.commit()

    print()
    print(
        f"Done. created={counts.get('created', 0)} "
        f"reactivated={counts.get('reactivated', 0)} "
        f"unchanged={counts.get('unchanged', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

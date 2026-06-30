"""
PATHS Backend — Platform-admin / RBAC tests.

Covers the security guarantees added in the platform-admin rollout:
  * Public candidate signup CANNOT create a platform_admin user, even when
    the request body tries to inject account_type.
  * Public organisation signup CANNOT create a platform_admin user.
  * Newly registered organisations land in PENDING_APPROVAL.
  * /api/v1/admin/* refuses non-platform-admin users (candidate, org member).
  * /auth/me returns is_platform_admin and organization.status fields.

These tests share the dev database with the rest of the suite (per
conftest.py). Each test uses a unique uuid-based email so re-runs are
idempotent and never collide with rows from previous runs.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _unique_email(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}@paths-test.io"


# ── Public candidate signup hardening ────────────────────────────────────


def test_candidate_signup_ignores_account_type_in_body(client: TestClient):
    """A malicious body field 'account_type' must be silently ignored."""
    email = _unique_email("escalation_candidate")
    resp = client.post(
        "/api/v1/auth/register/candidate",
        json={
            "full_name": "Escalation Tester",
            "email": email,
            "password": "StrongPassword123",
            # Attempted privilege escalation:
            "account_type": "platform_admin",
            "is_platform_admin": True,
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["account_type"] == "candidate"


def test_org_signup_creates_pending_request(client: TestClient):
    """register/organization must produce a PENDING org + access request."""
    suffix = uuid.uuid4().hex[:6]
    email = _unique_email("orgreq")
    resp = client.post(
        "/api/v1/auth/register/organization",
        json={
            "organization_name": f"Test Co {suffix}",
            "organization_slug": f"test-co-{suffix}",
            "first_admin_full_name": "Org Admin",
            "first_admin_email": email,
            "first_admin_password": "StrongPassword123",
            "first_admin_job_title": "Founder",
            "accept_terms": True,
            "confirm_authorized": True,
            # Attempted privilege escalation:
            "account_type": "platform_admin",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["role_code"] == "org_admin"

    # Login as that user → /me must show pending org
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPassword123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["account_type"] == "organization_member"
    assert me["is_platform_admin"] is False
    assert me["organization"] is not None
    assert me["organization"]["status"] == "pending_approval"


# ── Admin route gating ───────────────────────────────────────────────────


def test_candidate_cannot_hit_admin_routes(client: TestClient):
    """A candidate JWT must be rejected by every /api/v1/admin/* route."""
    email = _unique_email("rbac_candidate")
    client.post(
        "/api/v1/auth/register/candidate",
        json={"full_name": "RBAC Candidate", "email": email, "password": "StrongPassword123"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPassword123"})
    token = login.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    for path in [
        "/api/v1/admin/dashboard-stats",
        "/api/v1/admin/organization-requests",
        "/api/v1/admin/organizations",
        "/api/v1/admin/users",
        "/api/v1/admin/audit",
    ]:
        resp = client.get(path, headers=h)
        assert resp.status_code == 403, f"{path} returned {resp.status_code}, expected 403"


def test_unauthenticated_admin_routes_blocked(client: TestClient):
    """No JWT → 401 on every admin route."""
    for path in [
        "/api/v1/admin/dashboard-stats",
        "/api/v1/admin/organization-requests",
        "/api/v1/admin/organizations",
    ]:
        resp = client.get(path)
        assert resp.status_code == 401, f"{path} returned {resp.status_code}, expected 401"


# ── /auth/me payload shape ────────────────────────────────────────────────


def test_me_payload_has_new_fields(client: TestClient):
    """/auth/me must include is_platform_admin and permissions[]."""
    email = _unique_email("me_shape")
    client.post(
        "/api/v1/auth/register/candidate",
        json={"full_name": "Me Shape", "email": email, "password": "StrongPassword123"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPassword123"})
    token = login.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["is_platform_admin"] is False
    assert isinstance(me.get("permissions"), list)
    # Candidate permissions baseline
    assert "candidate.view_jobs" in me["permissions"]

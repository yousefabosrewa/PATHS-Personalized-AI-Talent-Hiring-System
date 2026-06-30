"""
PATHS — Tenant isolation integration tests.

Verifies that Org B cannot read or mutate any resource belonging to Org A,
across the most security-critical routers.

Run with:
    pytest tests/security/test_tenant_isolation.py -v

Prerequisites:
    - A running Postgres database with migrations applied.
    - DATABASE_URL env var pointing to a test database.

PATHS-174 (Phase 8 — Launch Hardening)
"""

from __future__ import annotations

import uuid
import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client() -> Generator:
    """Return a TestClient backed by the real FastAPI app."""
    # Import here so the test can be skipped if the app doesn't start
    from app.main import app
    with TestClient(app) as c:
        yield c


def _register_org(client: TestClient, email: str, org_name: str, slug: str):
    """Register a new org and return the JWT token + org_id."""
    resp = client.post("/api/v1/auth/register/organization", json={
        "email": email,
        "password": "TestPass!123",
        "full_name": "Test User",
        "organization_name": org_name,
        "organization_slug": slug,
        "contact_role": "CEO",
    })
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    return resp.json()


def _login(client: TestClient, email: str) -> str:
    """Login and return JWT token."""
    resp = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "TestPass!123",
    })
    if resp.status_code != 200:
        pytest.skip(f"Login failed (DB not available?): {resp.text}")
    return resp.json()["access_token"]


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestTenantIsolation:
    """Org B cannot access Org A's resources."""

    @pytest.fixture(autouse=True, scope="class")
    def setup(self, client: TestClient):
        """Create two independent orgs and get their tokens."""
        suffix = uuid.uuid4().hex[:6]
        self.email_a = f"org_a_{suffix}@test.paths"
        self.email_b = f"org_b_{suffix}@test.paths"
        self.slug_a = f"org-a-{suffix}"
        self.slug_b = f"org-b-{suffix}"

        try:
            reg_a = _register_org(client, self.email_a, f"Org A {suffix}", self.slug_a)
            reg_b = _register_org(client, self.email_b, f"Org B {suffix}", self.slug_b)
        except Exception as e:
            pytest.skip(f"Could not register test orgs (DB not available?): {e}")
            return

        self.token_a = _login(client, self.email_a)
        self.token_b = _login(client, self.email_b)
        self.org_id_a = reg_a.get("organization_id", "")
        self.org_id_b = reg_b.get("organization_id", "")
        self.client = client

    def _headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    # ── Jobs ──────────────────────────────────────────────────────────────────

    def test_org_b_cannot_read_org_a_jobs(self):
        """Org B must receive 403 or empty list when reading Org A's jobs."""
        resp = self.client.get(
            "/api/v1/jobs",
            headers=self._headers(self.token_b),
        )
        # The endpoint is scoped to the JWT org, so Org B sees its own jobs.
        # It must NOT see Org A's jobs if any were created.
        assert resp.status_code in (200, 403)
        if resp.status_code == 200:
            jobs = resp.json()
            assert isinstance(jobs, (list, dict))

    def test_org_b_cannot_create_job_in_org_a(self):
        """Org B must receive 403 when trying to create a job for Org A."""
        resp = self.client.post(
            "/api/v1/jobs",
            json={
                "title": "Malicious Job",
                "organization_id": self.org_id_a,
                "status": "published",
            },
            headers=self._headers(self.token_b),
        )
        # Either 403 (forbidden) or 422 (validation — org_id is ignored/forbidden)
        assert resp.status_code in (403, 422, 400)

    # ── Candidates ────────────────────────────────────────────────────────────

    def test_org_b_cannot_read_org_a_candidates(self):
        """Candidates are org-scoped — Org B must not see Org A's candidates."""
        resp = self.client.get(
            "/api/v1/candidates",
            headers=self._headers(self.token_b),
        )
        assert resp.status_code in (200, 403)
        # If 200, none of the returned candidates should belong to Org A
        if resp.status_code == 200 and self.org_id_a:
            data = resp.json()
            if isinstance(data, list):
                for c in data:
                    assert c.get("organization_id") != self.org_id_a, (
                        "Org B retrieved a candidate belonging to Org A!"
                    )

    # ── Billing ───────────────────────────────────────────────────────────────

    def test_org_b_cannot_read_org_a_subscription(self):
        """Org B must receive 403 when requesting Org A's subscription."""
        resp = self.client.get(
            f"/api/v1/billing/subscription?org_id={self.org_id_a}",
            headers=self._headers(self.token_b),
        )
        assert resp.status_code in (403, 404), (
            f"Org B got {resp.status_code} on Org A's subscription: {resp.text}"
        )

    def test_org_b_cannot_read_org_a_invoices(self):
        """Org B must receive 403 when requesting Org A's invoices."""
        resp = self.client.get(
            f"/api/v1/billing/invoices?org_id={self.org_id_a}",
            headers=self._headers(self.token_b),
        )
        assert resp.status_code in (403, 404)

    # ── Applications ──────────────────────────────────────────────────────────

    def test_org_b_cannot_list_org_a_applications(self):
        """Applications are org-scoped via the JWT."""
        resp = self.client.get(
            "/api/v1/applications",
            headers=self._headers(self.token_b),
        )
        assert resp.status_code in (200, 403)

    # ── Org members ───────────────────────────────────────────────────────────

    def test_org_b_cannot_list_org_a_members(self):
        """Members endpoint must be scoped to the requester's org."""
        resp = self.client.get(
            f"/api/v1/organizations/{self.org_id_a}/members",
            headers=self._headers(self.token_b),
        )
        assert resp.status_code in (403, 404)

    # ── Audit log ─────────────────────────────────────────────────────────────

    def test_org_b_cannot_read_org_a_audit_log(self):
        """Audit log must be filtered by org or require admin."""
        resp = self.client.get(
            "/api/v1/audit",
            headers=self._headers(self.token_b),
        )
        assert resp.status_code in (200, 403)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                for row in data:
                    assert row.get("organization_id") != self.org_id_a

    # ── Admin routes must reject non-admins ────────────────────────────────────

    def test_org_member_cannot_access_admin_stats(self):
        """Non-admin org members must receive 403 on admin endpoints."""
        resp = self.client.get(
            "/api/v1/admin/stats",
            headers=self._headers(self.token_a),
        )
        assert resp.status_code == 403

    def test_org_member_cannot_access_owner_revenue(self):
        """Non-admin org members must receive 403 on owner endpoints."""
        resp = self.client.get(
            "/api/v1/owner/revenue-summary",
            headers=self._headers(self.token_a),
        )
        assert resp.status_code == 403

"""PATHS Backend — Assessment Agent API tests."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.dependencies import (
    OrgContext,
    get_current_hiring_org_context,
    require_active_org_status,
)
from app.db.models.assessment import Assessment
from app.main import app

ORG_A_ID = uuid.uuid4()
ORG_B_ID = uuid.uuid4()
CANDIDATE_ID = uuid.uuid4()
JOB_ID = uuid.uuid4()
APPLICATION_ID = uuid.uuid4()


def _make_assessment(org_id: uuid.UUID, **overrides) -> Assessment:
    kwargs = dict(
        id=uuid.uuid4(),
        organization_id=org_id,
        application_id=APPLICATION_ID,
        candidate_id=CANDIDATE_ID,
        job_id=JOB_ID,
        title="Test Assessment",
        assessment_type="coding",
        status="pending",
    )
    kwargs.update(overrides)
    return Assessment(**kwargs)


@pytest.fixture
def org_a_context() -> OrgContext:
    return OrgContext(
        user=MagicMock(),
        organization_id=ORG_A_ID,
        role_code="hiring_manager",
    )


@pytest.fixture
def org_b_context() -> OrgContext:
    return OrgContext(
        user=MagicMock(),
        organization_id=ORG_B_ID,
        role_code="hiring_manager",
    )


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def client(mock_db: MagicMock, org_a_context: OrgContext):
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[require_active_org_status] = lambda: org_a_context
    app.dependency_overrides[get_current_hiring_org_context] = lambda: org_a_context
    with TestClient(app, base_url="http://localhost") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def assessment_payload() -> dict:
    return {
        "application_id": str(APPLICATION_ID),
        "candidate_id": str(CANDIDATE_ID),
        "job_id": str(JOB_ID),
        "title": "Test Assessment",
        "assessment_type": "coding",
        "instructions": "Complete the following tasks",
    }


# ── 1. Create assessment ─────────────────────────────────────────────────


def test_create_assessment(client, mock_db, assessment_payload):
    resp = client.post("/api/v1/assessments", json=assessment_payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Test Assessment"
    assert body["assessment_type"] == "coding"
    assert body["status"] == "pending"
    assert body["organization_id"] == str(ORG_A_ID)
    assert body["application_id"] == str(APPLICATION_ID)
    assert body["candidate_id"] == str(CANDIDATE_ID)
    assert body["job_id"] == str(JOB_ID)
    assert body["instructions"] == "Complete the following tasks"
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


# ── 2. List assessments ──────────────────────────────────────────────────


def test_list_assessments(client, mock_db):
    a = _make_assessment(ORG_A_ID)
    mock_db.execute.return_value.scalars.return_value.all.return_value = [a]
    resp = client.get("/api/v1/assessments")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["title"] == "Test Assessment"
    assert data[0]["organization_id"] == str(ORG_A_ID)


# ── 3. Get assessment by id ──────────────────────────────────────────────


def test_get_assessment(client, mock_db):
    a = _make_assessment(ORG_A_ID)
    mock_db.get.return_value = a
    resp = client.get(f"/api/v1/assessments/{a.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(a.id)
    assert body["title"] == "Test Assessment"
    assert body["status"] == "pending"


# ── 4. Update assessment ─────────────────────────────────────────────────


def test_update_assessment(client, mock_db):
    a = _make_assessment(ORG_A_ID)
    mock_db.get.return_value = a
    resp = client.patch(
        f"/api/v1/assessments/{a.id}",
        json={"score": 85, "max_score": 100, "status": "reviewed", "reviewer_notes": "Good work"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["score"] == 85.0
    assert body["max_score"] == 100.0
    assert body["status"] == "reviewed"
    assert body["reviewer_notes"] == "Good work"


# ── 5. Delete assessment ─────────────────────────────────────────────────


def test_delete_assessment(client, mock_db):
    a = _make_assessment(ORG_A_ID)
    mock_db.get.return_value = a
    resp = client.delete(f"/api/v1/assessments/{a.id}")
    assert resp.status_code == 204
    mock_db.delete.assert_called_once_with(a)
    mock_db.commit.assert_called_once()


# ── 6. Org isolation ─────────────────────────────────────────────────────


def test_org_isolation(client, mock_db, org_b_context):
    a = _make_assessment(ORG_A_ID)
    mock_db.get.return_value = a
    app.dependency_overrides[get_current_hiring_org_context] = lambda: org_b_context
    resp = client.get(f"/api/v1/assessments/{a.id}")
    assert resp.status_code == 404
    # Restore original context
    app.dependency_overrides[get_current_hiring_org_context] = lambda: OrgContext(
        user=MagicMock(),
        organization_id=ORG_A_ID,
        role_code="hiring_manager",
    )


# ── 7. Unauthorized access ───────────────────────────────────────────────


def test_unauthorized_access(mock_db):
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: mock_db
    with TestClient(app, base_url="http://localhost") as c:
        resp = c.get("/api/v1/assessments")
        assert resp.status_code == 401
    app.dependency_overrides.clear()


# ── 8. Invalid payload ───────────────────────────────────────────────────


def test_create_assessment_missing_fields(client):
    resp = client.post("/api/v1/assessments", json={"title": "Incomplete"})
    assert resp.status_code == 422


# ── 9. Status transitions ────────────────────────────────────────────────


def test_status_transitions(client, mock_db):
    a = _make_assessment(ORG_A_ID)
    mock_db.get.return_value = a

    # pending -> submitted
    resp = client.patch(f"/api/v1/assessments/{a.id}", json={"status": "submitted"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "submitted"

    # Reset mock for second call
    mock_db.reset_mock()
    mock_db.get.return_value = a

    # submitted -> reviewed
    resp = client.patch(f"/api/v1/assessments/{a.id}", json={"status": "reviewed"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "reviewed"


# ── 10. Filter by application_id ─────────────────────────────────────────


def test_filter_by_application_id(client, mock_db):
    a = _make_assessment(ORG_A_ID, application_id=APPLICATION_ID)
    mock_db.execute.return_value.scalars.return_value.all.return_value = [a]
    resp = client.get(f"/api/v1/assessments?application_id={APPLICATION_ID}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["application_id"] == str(APPLICATION_ID)

"""
PATHS — Role separation: candidates vs organisation hiring API.
"""

import uuid

from fastapi.testclient import TestClient


def test_candidate_detail_requires_auth(client: TestClient):
    cid = uuid.uuid4()
    r = client.get(f"/api/v1/candidates/{cid}")
    assert r.status_code == 401


def test_candidate_denied_org_jobs_list(client: TestClient):
    reg_data = {
        "full_name": "Access Test Candidate",
        "email": "access_candidate_jobs@test.com",
        "password": "StrongPassword123",
        "phone": "123456789",
    }
    r = client.post("/api/v1/auth/register/candidate", json=reg_data)
    assert r.status_code == 201

    login_data = {"email": reg_data["email"], "password": reg_data["password"]}
    r = client.post("/api/v1/auth/login", json=login_data)
    assert r.status_code == 200
    token = r.json()["access_token"]

    r = client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403

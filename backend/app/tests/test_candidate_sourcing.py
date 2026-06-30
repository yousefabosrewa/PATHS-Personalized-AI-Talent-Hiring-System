"""Unit tests for the Open-to-Work Candidate Sourcing module.

These tests focus on the parts of the pipeline that don't require a
running database, AGE, or Qdrant — i.e. the providers, the normalizer,
and the deterministic reasoning fallback. The orchestrator + router are
covered by their own integration tests once a Postgres test database is
configured.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.services.sourcing.agents.candidate_job_reasoning_agent import (
    CandidateJobReasoning,
    _coerce_decision,
    _fallback_reasoning,
    _summary_template,
)
from app.services.sourcing.normalizers import (
    NormalizedSourcedCandidate,
    normalize_sourced_candidates,
)
from app.services.sourcing.providers import (
    LinkedInOpenToWorkProvider,
    MockOpenToWorkProvider,
    RawSourcedCandidate,
    get_provider,
)


# ── Provider factory ─────────────────────────────────────────────────────


def test_get_provider_default_is_mock():
    assert isinstance(get_provider(""), MockOpenToWorkProvider)
    assert isinstance(get_provider("unknown_source"), MockOpenToWorkProvider)


def test_get_provider_returns_linkedin():
    assert isinstance(get_provider("linkedin"), LinkedInOpenToWorkProvider)


# ── Mock provider ────────────────────────────────────────────────────────


# Anonymised, generic test roster — must never contain the named mock
# candidates that fix6.md mandates be removed.
_TEST_ROSTER = [
    {
        "external_id": "anon-001",
        "source_url": "https://example.test/in/anon-001",
        "full_name": "Test Engineer One",
        "headline": "Backend Engineer · open to work",
        "current_title": "Backend Engineer",
        "skills": ["python", "fastapi", "postgresql"],
        "location_text": "Remote",
    },
    {
        "external_id": "anon-002",
        "source_url": "https://example.test/in/anon-002",
        "full_name": "Test Engineer Two",
        "headline": "Full-stack engineer · open to work",
        "current_title": "Full-stack Engineer",
        "skills": ["react", "typescript", "node.js"],
        "location_text": "Remote",
    },
    {
        "external_id": "anon-003",
        "source_url": "https://example.test/in/anon-003",
        "full_name": "Test Engineer Three",
        "headline": "Data engineer · open to senior roles",
        "current_title": "Data Engineer",
        "skills": ["python", "dbt", "snowflake"],
        "location_text": "Remote",
    },
]


def test_mock_provider_returns_open_to_work_candidates():
    provider = MockOpenToWorkProvider(seed_roster=_TEST_ROSTER)
    result = asyncio.run(
        provider.fetch_open_to_work_candidates(limit=3)
    )
    assert len(result.raw_candidates) == 3
    for c in result.raw_candidates:
        assert c.source_platform == "mock"
        assert c.open_to_work is True
        assert c.full_name
        assert c.skills


def test_mock_provider_default_roster_is_empty():
    # fix6.md: the default mock roster must be empty so no smoke
    # candidates ever surface in the UI.
    provider = MockOpenToWorkProvider()
    result = asyncio.run(provider.fetch_open_to_work_candidates(limit=5))
    assert result.raw_candidates == []


def test_mock_provider_offset_rotates():
    provider = MockOpenToWorkProvider(seed_roster=_TEST_ROSTER)
    a = asyncio.run(provider.fetch_open_to_work_candidates(limit=2, offset=0))
    b = asyncio.run(
        provider.fetch_open_to_work_candidates(limit=2, offset=a.new_offset)
    )
    a_ids = [c.source_external_id for c in a.raw_candidates]
    b_ids = [c.source_external_id for c in b.raw_candidates]
    assert a_ids != b_ids


def test_mock_provider_keyword_filter_keeps_only_matches():
    provider = MockOpenToWorkProvider(seed_roster=_TEST_ROSTER)
    result = asyncio.run(
        provider.fetch_open_to_work_candidates(
            limit=10, keywords=["data engineer"], location=None,
        )
    )
    assert result.raw_candidates
    assert any("data" in (c.headline or "").lower() for c in result.raw_candidates)


# ── LinkedIn provider (compliance) ───────────────────────────────────────


def test_linkedin_provider_is_stub_by_default(tmp_path):
    provider = LinkedInOpenToWorkProvider(
        export_dir=str(tmp_path), stub=True,
    )
    result = asyncio.run(provider.fetch_open_to_work_candidates(limit=5))
    assert result.raw_candidates == []
    assert result.errors == []


def test_linkedin_provider_authorized_api_path_raises_until_configured(tmp_path):
    provider = LinkedInOpenToWorkProvider(
        export_dir=str(tmp_path), stub=False,
    )
    # The connector must NOT scrape LinkedIn — the API hook raises
    # NotImplementedError, the provider falls back to consented exports
    # (none in this dir) and returns an empty list.
    result = asyncio.run(
        provider.fetch_open_to_work_candidates(
            limit=2, keywords=["engineer"], location=None,
        )
    )
    assert result.raw_candidates == []
    assert result.errors == []


def test_linkedin_provider_loads_consented_export(tmp_path):
    payload = {
        "linkedin_url": "https://linkedin.com/in/jane-doe",
        "name": "Jane Doe",
        "headline": "Senior Backend Engineer · #OpenToWork",
        "about": "Backend specialist with 8 years of Python and Go.",
        "location": "Berlin, Germany",
        "skills": ["python", "fastapi", "postgresql"],
        "experiences": [
            {
                "position_title": "Senior Backend Engineer",
                "institution_name": "Example Co",
                "from_date": "2021-01",
            }
        ],
        "open_to_work": True,
    }
    (tmp_path / "jane.json").write_text(__import__("json").dumps(payload))
    provider = LinkedInOpenToWorkProvider(export_dir=str(tmp_path), stub=True)
    result = asyncio.run(provider.fetch_open_to_work_candidates(limit=5))
    assert len(result.raw_candidates) == 1
    raw = result.raw_candidates[0]
    assert raw.source_platform == "linkedin_open_to_work"
    assert raw.full_name == "Jane Doe"
    assert raw.skills == ["python", "fastapi", "postgresql"]
    assert raw.experiences[0]["title"] == "Senior Backend Engineer"


# ── Normalizer ───────────────────────────────────────────────────────────


def _raw(**overrides) -> RawSourcedCandidate:
    base = dict(
        source_platform="mock",
        source_url="https://mock.local/in/123",
        source_external_id="123",
        full_name="Test Candidate",
        headline="Backend Engineer",
        about="Loves Python.",
        skills=["Python", "PostgreSQL", "fastapi"],
        desired_titles=["Senior Backend Engineer"],
        desired_job_types=["full-time"],
        desired_workplace=["wfh", "Onsite"],
        contacts=[{"contact_type": "email", "contact_value": "jane@example.com"}],
        links=[{"link_type": "linkedin", "url": "https://mock.local/in/123"}],
        experiences=[{"title": "Engineer", "company_name": "Acme"}],
        education=[{"institution": "MIT", "degree": "BS", "field_of_study": "CS"}],
    )
    base.update(overrides)
    return RawSourcedCandidate(**base)


def test_normalizer_accepts_minimal_profile():
    accepted, rejected = normalize_sourced_candidates([_raw()])
    assert rejected == []
    assert len(accepted) == 1
    norm = accepted[0]
    assert isinstance(norm, NormalizedSourcedCandidate)
    assert norm.email == "jane@example.com"
    assert norm.desired_job_types == ["full_time"]
    assert "remote" in norm.desired_workplace
    assert "onsite" in norm.desired_workplace
    assert "Python" in norm.skills  # canonicalised by skill dictionary


def test_normalizer_rejects_when_no_identity():
    raw = _raw(source_url=None, source_external_id=None, full_name=None)
    accepted, rejected = normalize_sourced_candidates([raw])
    assert accepted == []
    assert rejected
    reasons = rejected[0].reasons
    assert "missing_full_name" in reasons or "missing_source_identity" in reasons


def test_normalizer_synthesizes_name_when_only_external_id_present():
    raw = _raw(full_name=None)
    accepted, rejected = normalize_sourced_candidates([raw])
    assert rejected == []
    assert accepted[0].full_name.startswith("Sourced Candidate")


# ── Reasoning fallback ───────────────────────────────────────────────────


def test_decision_inference_from_score():
    assert _coerce_decision(None, 90.0) == "strong_match"
    assert _coerce_decision(None, 60.0) == "potential_match"
    assert _coerce_decision(None, 10.0) == "weak_match"


def test_summary_template_speaks_score():
    assert "75" in _summary_template("strong_match", 75)
    assert "Weak fit" in _summary_template("weak_match", 5.0)


def test_fallback_reasoning_returns_object_when_llm_off():
    reasoning = _fallback_reasoning(
        candidate_id=uuid4(),
        job_id=uuid4(),
        overall_score=88.0,
        matched_skills=["python", "fastapi"],
        missing_required_skills=["kafka"],
        note="test",
    )
    assert isinstance(reasoning, CandidateJobReasoning)
    assert reasoning.fallback is True
    assert reasoning.decision == "strong_match"
    assert reasoning.recommended_next_step == "shortlist"
    assert any("python" in s.lower() for s in reasoning.strengths)
    assert any("kafka" in g.lower() for g in reasoning.gaps)


# ── Sanity: providers register with the factory ──────────────────────────


def test_provider_factory_reflects_settings_default():
    """``get_provider`` is the public API used by the orchestrator."""
    assert get_provider("mock").source_platform == "mock"
    assert get_provider("linkedin").source_platform == "linkedin_open_to_work"

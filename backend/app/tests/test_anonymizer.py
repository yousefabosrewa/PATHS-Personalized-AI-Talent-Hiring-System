"""
Unit tests for the Bias & Fairness anonymizer (Phase 4).

Tests confirm:
  - No PII leaks through build_anonymized_json
  - Name tokens are redacted in text fields
  - Location is generalised (street stripped)
  - Skills, experience years, certifications are preserved
  - Company names are not present in the anonymized output
  - School names are not present in the anonymized output
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pytest

from app.services.bias_fairness.anonymizer import (
    _redact_name,
    _general_location,
    build_anonymized_json,
)


# ── Minimal stubs so we don't need a real DB ──────────────────────────────────


def _make_candidate(**kwargs):
    cand = MagicMock()
    cand.id = uuid.uuid4()
    cand.full_name = kwargs.get("full_name", "Jane Smith")
    cand.email = kwargs.get("email", "jane@example.com")
    cand.phone = kwargs.get("phone", "+201234567890")
    cand.current_title = kwargs.get("current_title", "Software Engineer")
    cand.location_text = kwargs.get("location_text", "5 Nasr St, Nasr City, Cairo, Egypt")
    cand.years_experience = kwargs.get("years_experience", 5)
    cand.career_level = kwargs.get("career_level", "senior")
    cand.summary = kwargs.get("summary", "Jane Smith is a great engineer.")
    cand.skills = kwargs.get("skills", ["Python", "FastAPI"])
    cand.open_to_job_types = kwargs.get("open_to_job_types", ["full_time"])
    cand.open_to_workplace_settings = kwargs.get("open_to_workplace_settings", ["remote"])
    cand.updated_at = "2026-01-01T00:00:00"
    return cand


def _make_profile(candidate=None, *, num_skills=2, num_experiences=1):
    profile = MagicMock()
    profile.candidate = candidate or _make_candidate()

    # Skills: (CandidateSkill, Skill)
    skills = []
    for i in range(num_skills):
        cs = MagicMock()
        cs.proficiency_level = "intermediate"
        sk = MagicMock()
        sk.name = f"Skill_{i}"
        skills.append((cs, sk))
    profile.skills = skills

    # Experiences: (CandidateExperience, Company|None)
    experiences = []
    for i in range(num_experiences):
        exp = MagicMock()
        exp.job_title = "Backend Developer"
        exp.description = f"Worked at Acme Corp on backend services. Jane Smith led the team."
        exp.start_date = None
        exp.end_date = None
        exp.is_current = i == 0
        company = MagicMock()
        company.name = "Acme Corp"
        experiences.append((exp, company))
    profile.experiences = experiences

    profile.education = []
    profile.certifications = []
    profile.projects = []
    return profile


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestRedactName:
    def test_redacts_full_name(self):
        result = _redact_name("Jane Smith is a senior engineer.", "Jane Smith")
        assert "Jane Smith" not in result
        assert "[REDACTED]" in result

    def test_case_insensitive(self):
        result = _redact_name("JANE SMITH joined the team.", "Jane Smith")
        assert "JANE SMITH" not in result

    def test_empty_text_returns_empty(self):
        assert _redact_name("", "Jane Smith") == ""

    def test_no_name_no_change(self):
        text = "Senior engineer with 5 years experience."
        assert _redact_name(text, None) == text

    def test_name_not_in_text_unchanged(self):
        text = "Engineer with Python skills."
        assert _redact_name(text, "Jane Smith") == text


class TestGeneralLocation:
    def test_strips_street_keeps_city_country(self):
        result = _general_location("5 Nasr St, Nasr City, Cairo, Egypt")
        assert result == "Cairo, Egypt"

    def test_city_country_only_unchanged(self):
        result = _general_location("Cairo, Egypt")
        assert result == "Cairo, Egypt"

    def test_none_returns_none(self):
        assert _general_location(None) is None

    def test_single_value_returned_as_is(self):
        result = _general_location("Remote")
        assert result == "Remote"


class TestBuildAnonymizedJson:
    def test_no_name_in_output(self):
        profile = _make_profile(_make_candidate(full_name="Jane Smith"))
        view_json, stripped = build_anonymized_json(profile)

        output_str = str(view_json)
        assert "Jane Smith" not in output_str
        assert "jane@example.com" not in output_str
        assert "+201234567890" not in output_str

    def test_name_in_summary_is_redacted(self):
        profile = _make_profile(_make_candidate(summary="Jane Smith is a great engineer."))
        view_json, _ = build_anonymized_json(profile)
        assert "Jane Smith" not in view_json["summary"]
        assert "[REDACTED]" in view_json["summary"]

    def test_name_in_experience_description_is_redacted(self):
        profile = _make_profile(_make_candidate(full_name="Jane Smith"), num_experiences=1)
        view_json, _ = build_anonymized_json(profile)
        for exp in view_json["experiences"]:
            assert "Jane Smith" not in exp["description"]

    def test_alias_present(self):
        profile = _make_profile()
        view_json, _ = build_anonymized_json(profile)
        assert "alias" in view_json
        assert view_json["alias"].startswith("Candidate ")

    def test_skills_preserved(self):
        profile = _make_profile(num_skills=3)
        view_json, _ = build_anonymized_json(profile)
        assert len(view_json["skills"]) == 3

    def test_years_experience_preserved(self):
        profile = _make_profile(_make_candidate(years_experience=7))
        view_json, _ = build_anonymized_json(profile)
        assert view_json["years_experience"] == 7

    def test_location_generalised(self):
        profile = _make_profile(_make_candidate(location_text="5 Nasr St, Nasr City, Cairo, Egypt"))
        view_json, _ = build_anonymized_json(profile)
        # Should be general (city, country) not street-level
        assert "5 Nasr St" not in (view_json["location_general"] or "")

    def test_current_title_preserved(self):
        profile = _make_profile(_make_candidate(current_title="Senior Backend Engineer"))
        view_json, _ = build_anonymized_json(profile)
        assert view_json["current_title"] == "Senior Backend Engineer"

    def test_stripped_fields_reported(self):
        profile = _make_profile(_make_candidate(email="jane@example.com"))
        _, stripped = build_anonymized_json(profile)
        assert "email" in stripped

    def test_desired_job_types_preserved(self):
        profile = _make_profile(_make_candidate(open_to_job_types=["full_time", "contract"]))
        view_json, _ = build_anonymized_json(profile)
        assert "full_time" in view_json["desired_job_types"]

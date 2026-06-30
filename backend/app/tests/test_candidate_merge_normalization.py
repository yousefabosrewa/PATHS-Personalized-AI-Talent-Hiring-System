"""Unit tests for candidate duplicate normalization (fix2_1.md Feature 2).

Covers the spec's worked example:

    Candidate A: Ahmed Ali, ahmed@example.com, +201001112223
    Candidate B:  ahmed ali , AHMED@example.com, 01001112223
    Candidate C: Ahmed Ali, other@example.com, +201001112223

Expected: A and B share an identity key; C differs (email differs).
"""

from __future__ import annotations

from app.services.candidate_merge.service import (
    _group_id,
    normalize_email,
    normalize_name,
    normalize_phone,
)


def _key(name, email, phone):
    return (normalize_name(name), normalize_email(email), normalize_phone(phone))


def test_name_normalization_collapses_space_and_case():
    assert normalize_name("Ahmed Ali") == "ahmed ali"
    assert normalize_name("  ahmed   ali ") == "ahmed ali"


def test_email_normalization_trims_and_lowercases():
    assert normalize_email("AHMED@example.com") == "ahmed@example.com"
    assert normalize_email("  ahmed@example.com ") == "ahmed@example.com"


def test_phone_normalization_matches_country_code_and_local():
    # +20 100 111 2223  ==  0 100 111 2223  (last 10 digits)
    assert normalize_phone("+201001112223") == normalize_phone("01001112223")


def test_spec_example_a_and_b_match_c_differs():
    a = _key("Ahmed Ali", "ahmed@example.com", "+201001112223")
    b = _key(" ahmed ali ", "AHMED@example.com", "01001112223")
    c = _key("Ahmed Ali", "other@example.com", "+201001112223")

    assert a == b, "A and B should normalize to the same identity key"
    assert a != c, "C must differ from A because the email differs"

    # Group ids follow the same rule.
    assert _group_id(*a) == _group_id(*b)
    assert _group_id(*a) != _group_id(*c)


def test_incomplete_identity_excluded_via_empty_fields():
    # Missing phone → empty normalized phone (grouping skips these upstream).
    assert normalize_phone(None) == ""
    assert normalize_email("") == ""
    assert normalize_name(None) == ""

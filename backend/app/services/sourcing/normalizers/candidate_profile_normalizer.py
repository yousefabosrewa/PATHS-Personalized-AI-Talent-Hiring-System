"""
PATHS Backend — Sourced candidate profile normalizer.

Converts a `RawSourcedCandidate` (provider output) into a clean
`NormalizedSourcedCandidate` ready for upsert into the existing
PostgreSQL `candidates` table — without ever changing the schema.

Design principles
-----------------
* Reuse existing fields only:
    Candidate.full_name / email / phone / current_title / location_text /
    headline / years_experience / summary / status / skills /
    open_to_job_types / open_to_workplace_settings / desired_job_titles /
    desired_job_categories
* Provenance lives in the existing CandidateSource row + EvidenceItem
  meta_json, not in a new schema field.
* Never invent contact values. We only emit a contact row when the
  provider supplied one *and* it can be safely classified.
* Reject obviously incomplete records (no name and no source URL).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.services.job_scraper.skill_dictionary import normalize_skill_list
from app.services.sourcing.providers.base_candidate_provider import RawSourcedCandidate

logger = logging.getLogger(__name__)


_WHITESPACE = re.compile(r"\s+")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class NormalizedSourcedCandidate:
    """Spec-compliant normalized candidate ready for upsert."""

    source_platform: str
    source_url: str | None
    source_external_id: str | None
    full_name: str
    email: str | None = None
    phone: str | None = None
    headline: str | None = None
    summary: str | None = None
    current_title: str | None = None
    current_company: str | None = None
    location_text: str | None = None
    years_experience: int | None = None
    skills: list[str] = field(default_factory=list)
    desired_titles: list[str] = field(default_factory=list)
    desired_job_types: list[str] = field(default_factory=list)
    desired_workplace: list[str] = field(default_factory=list)
    desired_categories: list[str] = field(default_factory=list)
    experiences: list[dict[str, Any]] = field(default_factory=list)
    education: list[dict[str, Any]] = field(default_factory=list)
    projects: list[dict[str, Any]] = field(default_factory=list)
    certifications: list[dict[str, Any]] = field(default_factory=list)
    contacts: list[dict[str, Any]] = field(default_factory=list)
    links: list[dict[str, Any]] = field(default_factory=list)
    open_to_work: bool = True
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class RejectedSourcedCandidate:
    raw: RawSourcedCandidate
    reasons: list[str]


# ── Helpers ──────────────────────────────────────────────────────────────


def _clean_text(value: str | None, *, max_len: int | None = None) -> str | None:
    if value is None:
        return None
    s = _WHITESPACE.sub(" ", str(value)).strip()
    if not s:
        return None
    if max_len is not None and len(s) > max_len:
        s = s[: max_len].rstrip()
    return s


def _normalize_workplace_settings(values: list[str]) -> list[str]:
    out: list[str] = []
    for v in values or []:
        if not isinstance(v, str):
            continue
        canon = v.strip().lower()
        if canon in {"remote", "wfh", "fully-remote", "fully_remote"}:
            out.append("remote")
        elif canon in {"hybrid", "flex"}:
            out.append("hybrid")
        elif canon in {"onsite", "on-site", "in-office", "office"}:
            out.append("onsite")
        elif canon:
            out.append(canon)
    seen: set[str] = set()
    deduped: list[str] = []
    for v in out:
        if v not in seen:
            seen.add(v)
            deduped.append(v)
    return deduped


def _normalize_job_types(values: list[str]) -> list[str]:
    mapping = {
        "full-time": "full_time",
        "fulltime": "full_time",
        "full time": "full_time",
        "part-time": "part_time",
        "parttime": "part_time",
        "part time": "part_time",
        "freelance": "contract",
        "contractor": "contract",
        "internship": "internship",
        "intern": "internship",
    }
    out: list[str] = []
    seen: set[str] = set()
    for v in values or []:
        if not isinstance(v, str):
            continue
        canon = mapping.get(v.strip().lower(), v.strip().lower())
        if canon and canon not in seen:
            seen.add(canon)
            out.append(canon)
    return out


def _normalize_titles(values: list[str], *, max_items: int = 10) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for v in values or []:
        clean = _clean_text(v, max_len=120)
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(clean)
        if len(out) >= max_items:
            break
    return out


def _email_from_contacts(contacts: list[dict[str, Any]]) -> str | None:
    for c in contacts or []:
        ct = (c.get("contact_type") or c.get("type") or "").lower()
        cv = c.get("contact_value") or c.get("value")
        if ct == "email" and isinstance(cv, str) and _EMAIL_RE.match(cv.strip()):
            return cv.strip().lower()
    return None


def _phone_from_contacts(contacts: list[dict[str, Any]]) -> str | None:
    for c in contacts or []:
        ct = (c.get("contact_type") or c.get("type") or "").lower()
        cv = c.get("contact_value") or c.get("value")
        if ct == "phone" and isinstance(cv, str) and len(cv.strip()) >= 5:
            return cv.strip()
    return None


def _normalize_experiences(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        title = _clean_text(it.get("title") or it.get("position_title"), max_len=200)
        company = _clean_text(
            it.get("company_name") or it.get("institution_name") or it.get("company"),
            max_len=200,
        )
        if not (title or company):
            continue
        out.append(
            {
                "title": title or "Unknown Role",
                "company_name": company or "Unknown",
                "start_date": _clean_text(it.get("start_date") or it.get("from_date"), max_len=50),
                "end_date": _clean_text(it.get("end_date") or it.get("to_date"), max_len=50),
                "description": _clean_text(it.get("description"), max_len=4000),
            }
        )
    return out


def _normalize_education(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        institution = _clean_text(
            it.get("institution") or it.get("institution_name"), max_len=200,
        )
        degree = _clean_text(it.get("degree"), max_len=120)
        field_of_study = _clean_text(it.get("field_of_study"), max_len=200)
        if not (institution or degree or field_of_study):
            continue
        out.append(
            {
                "institution": institution,
                "degree": degree,
                "field_of_study": field_of_study,
                "start_date": _clean_text(it.get("start_date") or it.get("from_date"), max_len=50),
                "end_date": _clean_text(it.get("end_date") or it.get("to_date"), max_len=50),
            }
        )
    return out


def _normalize_contacts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for c in items or []:
        if not isinstance(c, dict):
            continue
        ct = (c.get("contact_type") or c.get("type") or "").strip().lower()
        cv = _clean_text(c.get("contact_value") or c.get("value"), max_len=512)
        if not ct or not cv:
            continue
        key = (ct, cv.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append({"contact_type": ct, "contact_value": cv})
    return out


def _normalize_links(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for c in items or []:
        if not isinstance(c, dict):
            continue
        url = _clean_text(c.get("url"), max_len=1024)
        if not url:
            continue
        if url in seen:
            continue
        seen.add(url)
        link_type = (c.get("link_type") or c.get("type") or "other").strip().lower()
        label = _clean_text(c.get("label"), max_len=200)
        out.append({"link_type": link_type, "url": url, "label": label})
    return out


# ── Public API ───────────────────────────────────────────────────────────


def normalize_sourced_candidates(
    raws: list[RawSourcedCandidate],
) -> tuple[list[NormalizedSourcedCandidate], list[RejectedSourcedCandidate]]:
    accepted: list[NormalizedSourcedCandidate] = []
    rejected: list[RejectedSourcedCandidate] = []
    for raw in raws:
        norm, reasons = _normalize_one(raw)
        if norm is None:
            rejected.append(RejectedSourcedCandidate(raw=raw, reasons=reasons))
            continue
        accepted.append(norm)
    return accepted, rejected


def _normalize_one(
    raw: RawSourcedCandidate,
) -> tuple[NormalizedSourcedCandidate | None, list[str]]:
    reasons: list[str] = []

    full_name = _clean_text(raw.full_name, max_len=255)
    if not full_name:
        # Some providers expose only headline/url. We still want to keep
        # the candidate when an external identifier exists, falling back
        # to a synthetic name for the required Candidate.full_name field.
        if raw.source_external_id:
            full_name = f"Sourced Candidate {raw.source_external_id}"
        else:
            reasons.append("missing_full_name")

    if not raw.source_url and not raw.source_external_id:
        reasons.append("missing_source_identity")

    if reasons:
        return None, reasons

    contacts = _normalize_contacts(raw.contacts)
    links = _normalize_links(raw.links)

    skills = list(normalize_skill_list(raw.skills or []))
    experiences = _normalize_experiences(raw.experiences)
    education = _normalize_education(raw.education)

    summary = _clean_text(raw.about, max_len=4000)
    headline = _clean_text(raw.headline, max_len=500)

    # If no explicit years_experience is supplied, leave it as None — we
    # never invent values; downstream services treat None as "unknown".
    years = raw.years_experience if isinstance(raw.years_experience, int) else None
    if isinstance(years, int) and years < 0:
        years = None

    norm = NormalizedSourcedCandidate(
        source_platform=raw.source_platform,
        source_url=_clean_text(raw.source_url, max_len=1024),
        source_external_id=_clean_text(raw.source_external_id, max_len=255),
        full_name=full_name,  # type: ignore[arg-type]
        email=_email_from_contacts(contacts),
        phone=_phone_from_contacts(contacts),
        headline=headline,
        summary=summary,
        current_title=_clean_text(raw.current_title, max_len=255),
        current_company=_clean_text(raw.current_company, max_len=255),
        location_text=_clean_text(raw.location_text, max_len=255),
        years_experience=years,
        skills=skills,
        desired_titles=_normalize_titles(raw.desired_titles),
        desired_job_types=_normalize_job_types(raw.desired_job_types),
        desired_workplace=_normalize_workplace_settings(raw.desired_workplace),
        desired_categories=[],
        experiences=experiences,
        education=education,
        projects=[p for p in (raw.projects or []) if isinstance(p, dict)],
        certifications=[c for c in (raw.certifications or []) if isinstance(c, dict)],
        contacts=contacts,
        links=links,
        open_to_work=bool(raw.open_to_work),
        raw=dict(raw.raw or {}),
    )
    return norm, []

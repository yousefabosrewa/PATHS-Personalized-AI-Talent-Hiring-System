"""
PATHS Backend — Base candidate sourcing provider.

Defines the canonical raw shape returned by every provider. The shape
intentionally mirrors `JobScraperAdapter.ScrapeRunResult` so the rest of
the pipeline (normalizer + service) can stay provider-agnostic.

A `RawSourcedCandidate` is the *raw* output from a provider — before the
normalizer maps it onto the existing PostgreSQL Candidate model and the
canonical Qdrant payload.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RawSourcedCandidate:
    """Canonical raw shape returned by every candidate-sourcing provider.

    Compliance: providers MUST only populate this from public/authorized
    data (export files, approved APIs, opt-in user submissions). Private
    pages, login walls and CAPTCHA-protected content are out of scope.
    """

    # Required identity / dedup fields
    source_platform: str            # "linkedin_open_to_work", "mock", ...
    source_url: str | None          # public profile URL (preferred dedup key)
    source_external_id: str | None  # external profile id (fallback dedup key)

    # Public profile fields (free-text — normalizer cleans them up)
    full_name: str | None = None
    headline: str | None = None
    about: str | None = None
    location_text: str | None = None
    current_title: str | None = None
    current_company: str | None = None
    years_experience: int | None = None
    open_to_work: bool = True

    # Lists / structured public data (best-effort, may be empty)
    skills: list[str] = field(default_factory=list)
    desired_titles: list[str] = field(default_factory=list)
    desired_job_types: list[str] = field(default_factory=list)        # full_time/part_time/contract
    desired_workplace: list[str] = field(default_factory=list)        # remote/hybrid/onsite
    languages: list[str] = field(default_factory=list)
    experiences: list[dict[str, Any]] = field(default_factory=list)
    education: list[dict[str, Any]] = field(default_factory=list)
    projects: list[dict[str, Any]] = field(default_factory=list)
    certifications: list[dict[str, Any]] = field(default_factory=list)
    contacts: list[dict[str, Any]] = field(default_factory=list)      # type/value
    links: list[dict[str, Any]] = field(default_factory=list)         # type/url

    # Provider-specific raw payload (kept verbatim for evidence)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class SourcingRunResult:
    """Aggregated provider output for a single sourcing run."""

    raw_candidates: list[RawSourcedCandidate] = field(default_factory=list)
    new_offset: int = 0
    visited: int = 0
    errors: list[str] = field(default_factory=list)


class BaseCandidateProvider(abc.ABC):
    """Abstract base class — every concrete provider must subclass this."""

    #: Canonical name used for `CandidateSource.source` and audit logs.
    source_platform: str = "base"

    @abc.abstractmethod
    async def fetch_open_to_work_candidates(
        self,
        *,
        limit: int = 5,
        offset: int = 0,
        keywords: list[str] | None = None,
        location: str | None = None,
        timeout_seconds: int | None = None,
    ) -> SourcingRunResult:
        """Return up to ``limit`` raw, public, open-to-work candidates."""

    # ── Convenience ──────────────────────────────────────────────────────

    def name(self) -> str:
        return self.source_platform

    @staticmethod
    def empty_result(*, offset: int = 0) -> SourcingRunResult:
        return SourcingRunResult(raw_candidates=[], new_offset=offset)

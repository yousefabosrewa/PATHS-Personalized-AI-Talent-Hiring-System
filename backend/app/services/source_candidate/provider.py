"""
PATHS Backend — Source Candidate provider interface (fix6.md).

A thin, provider-agnostic interface used by the recruiter Source Candidate
page. The page never talks directly to an MCP server, scraper, or CSV file —
it goes through the backend, which selects a provider that implements this
interface.

The shape mirrors the spec example so future providers (CSV export,
external recruitment platform, an approved LinkedIn API partner, the
linkedin-mcp-server reference) can drop in without touching the API
layer or the import service.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Literal


ProviderName = Literal["linkedin_mcp", "csv_export", "external_recruitment_platform"]


class SourcingProviderError(RuntimeError):
    """Provider could not return candidates — bubble up a clear UI error."""


@dataclass
class FetchOpenToWorkInput:
    organization_id: str
    count: int = 5
    role_category: str = "technical"
    keywords: list[str] = field(default_factory=list)
    location: str | None = None
    source: ProviderName = "linkedin_mcp"


@dataclass
class ExternalCandidatePayload:
    """Provider-agnostic external candidate row.

    Compliance: providers MUST only return data from authorized sources —
    approved APIs, consented exports, or candidate-submitted profiles.
    Open-to-work signals must come from the provider; never fabricate.
    """

    provider: ProviderName
    external_id: str | None = None
    full_name: str | None = None
    headline: str | None = None
    current_title: str | None = None
    current_company: str | None = None
    location: str | None = None
    profile_url: str | None = None
    email: str | None = None
    phone: str | None = None
    skills: list[str] = field(default_factory=list)
    open_to_work_signal: bool | None = None
    open_to_work_evidence: str | None = None
    technical_role_evidence: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class CandidateSourcingProvider(abc.ABC):
    """Implementations: linkedin_mcp, csv_export, future enterprise APIs."""

    provider_name: ProviderName = "linkedin_mcp"

    @abc.abstractmethod
    async def fetch_open_to_work_candidates(
        self, input: FetchOpenToWorkInput,
    ) -> list[ExternalCandidatePayload]:
        """Return up to ``input.count`` candidates matching the filters."""

    async def fetch_profile_details(self, *, username: str) -> dict[str, Any]:
        """Optionally enrich one candidate from their profile page.

        Returns a dict like ``{open_to_work: bool, open_to_work_evidence: str,
        skills: list[str], about: str}``. Providers that cannot enrich return
        an empty dict (the caller treats that as "unknown").
        """
        return {}

"""Concrete CandidateSourcingProvider implementations."""

from __future__ import annotations

from app.core.config import get_settings
from app.services.source_candidate.provider import (
    CandidateSourcingProvider,
    SourcingProviderError,
)
from app.services.source_candidate.providers.csv_export_provider import (
    CsvExportSourcingProvider,
)
from app.services.source_candidate.providers.linkedin_mcp_provider import (
    LinkedInMcpSourcingProvider,
)

__all__ = [
    "CsvExportSourcingProvider",
    "LinkedInMcpSourcingProvider",
    "get_sourcing_provider",
]


_settings = get_settings()


def get_sourcing_provider(name: str | None) -> CandidateSourcingProvider:
    """Factory — return the requested provider, or the configured default.

    Selection order:
      1. explicit ``name`` argument (passed by the caller / API request)
      2. ``settings.source_candidate_default_provider``
      3. ``linkedin_mcp`` (which itself falls back to CSV exports when the
         MCP/connector isn't configured).
    """
    chosen = (name or _settings.source_candidate_default_provider or "linkedin_mcp").strip().lower()
    if chosen == "csv_export":
        return CsvExportSourcingProvider()
    if chosen in ("linkedin_mcp", "linkedin", "external_recruitment_platform"):
        return LinkedInMcpSourcingProvider(provider_label=chosen)
    raise SourcingProviderError(
        f"Unknown sourcing provider '{chosen}'. "
        "Configure SOURCE_CANDIDATE_DEFAULT_PROVIDER or pass a known source."
    )

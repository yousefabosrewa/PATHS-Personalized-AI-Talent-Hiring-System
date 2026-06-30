"""
PATHS Backend — Mock candidate sourcing provider.

After fix6.md, the recruiter Source Candidate page is no longer allowed to
expose smoke/mock candidates. This provider is therefore **empty by
default**: when ``CANDIDATE_SOURCING_PROVIDER=mock`` it returns zero
candidates so the UI shows the real "no candidates" empty state instead
of fictional people.

The class is kept (rather than deleted) because the existing
``CandidateSourcingService`` orchestrator imports it as a fallback when an
unknown provider name is requested. Tests that need deterministic input
should construct ``MockOpenToWorkProvider(seed_roster=[…])`` explicitly
with their own anonymised data — never the previous hardcoded names.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.sourcing.providers.base_candidate_provider import (
    BaseCandidateProvider,
    RawSourcedCandidate,
    SourcingRunResult,
)

logger = logging.getLogger(__name__)


def _entry_to_raw(entry: dict[str, Any]) -> RawSourcedCandidate:
    return RawSourcedCandidate(
        source_platform="mock",
        source_url=entry.get("source_url"),
        source_external_id=entry.get("external_id"),
        full_name=entry.get("full_name"),
        headline=entry.get("headline"),
        about=entry.get("about"),
        location_text=entry.get("location_text"),
        current_title=entry.get("current_title"),
        current_company=entry.get("current_company"),
        years_experience=entry.get("years_experience"),
        open_to_work=bool(entry.get("open_to_work", True)),
        skills=list(entry.get("skills") or []),
        desired_titles=list(entry.get("desired_titles") or []),
        desired_job_types=list(entry.get("desired_job_types") or []),
        desired_workplace=list(entry.get("desired_workplace") or []),
        experiences=list(entry.get("experiences") or []),
        education=list(entry.get("education") or []),
        projects=list(entry.get("projects") or []),
        certifications=list(entry.get("certifications") or []),
        links=list(entry.get("links") or []),
        raw=dict(entry),
    )


class MockOpenToWorkProvider(BaseCandidateProvider):
    """In-memory provider — empty by default; tests inject their own roster."""

    source_platform = "mock"

    def __init__(self, *, seed_roster: list[dict[str, Any]] | None = None) -> None:
        # The default roster is intentionally empty. fix6.md requires that
        # the recruiter UI never displays hardcoded mock candidates.
        self._roster: list[dict[str, Any]] = list(seed_roster or [])

    async def fetch_open_to_work_candidates(
        self,
        *,
        limit: int = 5,
        offset: int = 0,
        keywords: list[str] | None = None,
        location: str | None = None,
        timeout_seconds: int | None = None,
    ) -> SourcingRunResult:
        if not self._roster:
            logger.info(
                "[CandidateSourcing][mock] roster empty — returning no candidates "
                "(set CANDIDATE_SOURCING_PROVIDER to a real provider in non-test envs)."
            )
            return self.empty_result(offset=offset)

        filtered = self._roster
        if location:
            needle = location.lower()
            filtered = [
                e for e in filtered
                if needle in (e.get("location_text") or "").lower()
            ]
        if keywords:
            kws = [k.lower() for k in keywords if k]
            filtered = [
                e for e in filtered
                if any(
                    kw in " ".join(
                        [
                            (e.get("full_name") or ""),
                            (e.get("headline") or ""),
                            (e.get("current_title") or ""),
                            " ".join(e.get("skills") or []),
                        ]
                    ).lower()
                    for kw in kws
                )
            ]
        if not filtered:
            return self.empty_result(offset=offset)

        n = len(filtered)
        start = offset % n
        rotated = filtered[start:] + filtered[:start]
        slice_ = rotated[: max(1, int(limit))]
        return SourcingRunResult(
            raw_candidates=[_entry_to_raw(e) for e in slice_],
            new_offset=(start + len(slice_)) % n,
            visited=len(slice_),
        )

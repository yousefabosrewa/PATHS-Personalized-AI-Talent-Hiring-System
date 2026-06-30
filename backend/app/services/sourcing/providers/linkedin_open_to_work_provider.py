"""
PATHS Backend — LinkedIn Open-to-Work candidate sourcing provider.

Compliance & safety
===================
This provider is **stub-by-default** and intentionally has no scraping
code path that bypasses authentication, rotates proxies, or solves
CAPTCHA. The PATHS architecture deliberately keeps a `BaseCandidateProvider`
seam so the LinkedIn integration can be replaced or upgraded later
through:

  * an approved LinkedIn API / Talent Hub partner integration, or
  * a manual candidate-export drop folder (CSV / JSON) that recruiters
    place on disk after consenting candidates uploaded their public
    profile.

When ``LINKEDIN_CANDIDATE_PROVIDER_STUB=true`` (the default), the
provider only reads JSON / CSV files in ``LINKEDIN_CANDIDATE_EXPORT_DIR``
that resemble the public Person model from the bundled
`linkedin_scraper-master` reference module. Each file is treated as a
single sourced candidate. **Nothing in this provider opens a browser,
visits linkedin.com, or signs in.**

If a real connector is wired up later, place its implementation behind
``_fetch_via_authorized_api`` and only call it when the project has an
approved enterprise contract — never as a workaround for missing data.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.sourcing.providers.base_candidate_provider import (
    BaseCandidateProvider,
    RawSourcedCandidate,
    SourcingRunResult,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class LinkedInOpenToWorkProvider(BaseCandidateProvider):
    """Compliant LinkedIn-shaped candidate provider.

    Reads consented public-profile exports (JSON / CSV) from a configured
    directory. Never logs in, never scrapes private pages.
    """

    source_platform = "linkedin_open_to_work"

    def __init__(
        self,
        *,
        export_dir: str | None = None,
        stub: bool | None = None,
    ) -> None:
        self.export_dir = Path(export_dir or settings.linkedin_candidate_export_dir)
        self.stub = settings.linkedin_candidate_provider_stub if stub is None else bool(stub)

    async def fetch_open_to_work_candidates(
        self,
        *,
        limit: int = 5,
        offset: int = 0,
        keywords: list[str] | None = None,
        location: str | None = None,
        timeout_seconds: int | None = None,
    ) -> SourcingRunResult:
        kws = [k.lower() for k in (keywords or []) if k]
        loc = (location or "").strip().lower() or None

        if self.stub:
            entries = await self._load_export_files()
        else:
            try:
                entries = await self._fetch_via_authorized_api(
                    keywords=kws, location=loc, limit=limit,
                )
            except NotImplementedError as exc:
                logger.warning(
                    "[CandidateSourcing][linkedin] approved API connector not "
                    "configured (%s) — falling back to consented export files. "
                    "Refusing to scrape private LinkedIn pages.",
                    exc,
                )
                entries = await self._load_export_files()
            except Exception as exc:  # noqa: BLE001
                logger.exception("[CandidateSourcing][linkedin] approved API failed")
                return SourcingRunResult(
                    raw_candidates=[],
                    new_offset=offset,
                    errors=[f"linkedin_api_error:{exc}"],
                )

        filtered = [e for e in entries if self._matches(e, kws, loc)] or list(entries)
        n = len(filtered)
        if n == 0:
            return self.empty_result(offset=offset)

        start = offset % n
        rotated = filtered[start:] + filtered[:start]
        slice_ = rotated[: max(1, int(limit))]
        result = SourcingRunResult(
            raw_candidates=[self._entry_to_raw(e) for e in slice_],
            new_offset=(start + len(slice_)) % n,
            visited=len(slice_),
        )
        logger.info(
            "[CandidateSourcing][linkedin] returning %d/%d candidates "
            "(stub=%s, offset=%d -> %d)",
            len(result.raw_candidates), n, self.stub, start, result.new_offset,
        )
        return result

    # ── Private helpers ──────────────────────────────────────────────────

    async def _load_export_files(self) -> list[dict[str, Any]]:
        """Load consented public-profile JSON / CSV exports from disk."""

        def _load() -> list[dict[str, Any]]:
            if not self.export_dir.exists():
                logger.info(
                    "[CandidateSourcing][linkedin] export dir not found: %s",
                    self.export_dir,
                )
                return []
            out: list[dict[str, Any]] = []
            for path in sorted(self.export_dir.glob("*.json")):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "[CandidateSourcing][linkedin] cannot parse %s: %s",
                        path, exc,
                    )
                    continue
                if isinstance(payload, list):
                    out.extend([p for p in payload if isinstance(p, dict)])
                elif isinstance(payload, dict):
                    out.append(payload)
            return out

        return await asyncio.to_thread(_load)

    async def _fetch_via_authorized_api(
        self,
        *,
        keywords: list[str],
        location: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Hook for an approved LinkedIn / partner API integration.

        Intentionally raises until a real, contract-backed connector is
        wired up. Bypassing this method to scrape linkedin.com is a
        violation of the PATHS sourcing policy and not supported.
        """
        raise NotImplementedError(
            "approved LinkedIn API connector is not configured. "
            "Set LINKEDIN_CANDIDATE_PROVIDER_STUB=true to use consented "
            "export files, or wire an enterprise integration here."
        )

    @staticmethod
    def _matches(entry: dict[str, Any], keywords: list[str], location: str | None) -> bool:
        if location:
            loc_text = (entry.get("location") or entry.get("location_text") or "").lower()
            if location not in loc_text:
                return False
        if not keywords:
            return True
        blob = " ".join(
            [
                (entry.get("name") or entry.get("full_name") or ""),
                (entry.get("headline") or ""),
                (entry.get("about") or ""),
                " ".join(entry.get("skills") or []),
            ]
        ).lower()
        return any(k in blob for k in keywords)

    @staticmethod
    def _entry_to_raw(entry: dict[str, Any]) -> RawSourcedCandidate:
        # Map the canonical reference shape from `linkedin_scraper-master`
        # (Person model) and our tolerant fallback keys.
        url = entry.get("linkedin_url") or entry.get("url") or entry.get("source_url")
        external_id = (
            entry.get("public_id")
            or entry.get("external_id")
            or entry.get("id")
            or (url.rstrip("/").split("/")[-1] if url else None)
        )
        experiences_raw = entry.get("experiences") or []
        normalized_experiences: list[dict[str, Any]] = []
        for exp in experiences_raw:
            if not isinstance(exp, dict):
                continue
            normalized_experiences.append(
                {
                    "title": exp.get("position_title") or exp.get("title"),
                    "company_name": exp.get("institution_name") or exp.get("company") or exp.get("company_name"),
                    "start_date": exp.get("from_date") or exp.get("start_date"),
                    "end_date": exp.get("to_date") or exp.get("end_date"),
                    "description": exp.get("description"),
                }
            )
        education_raw = entry.get("educations") or entry.get("education") or []
        normalized_education: list[dict[str, Any]] = []
        for edu in education_raw:
            if not isinstance(edu, dict):
                continue
            normalized_education.append(
                {
                    "institution": edu.get("institution_name") or edu.get("institution"),
                    "degree": edu.get("degree"),
                    "field_of_study": edu.get("description") or edu.get("field_of_study"),
                    "start_date": edu.get("from_date") or edu.get("start_date"),
                    "end_date": edu.get("to_date") or edu.get("end_date"),
                }
            )
        contacts_raw = entry.get("contacts") or []
        normalized_contacts: list[dict[str, Any]] = []
        for c in contacts_raw:
            if not isinstance(c, dict):
                continue
            ctype = c.get("type") or c.get("contact_type") or "other"
            cval = c.get("value") or c.get("contact_value")
            if not cval:
                continue
            normalized_contacts.append({"contact_type": ctype, "contact_value": cval})

        accomplishments_raw = entry.get("accomplishments") or []
        certifications: list[dict[str, Any]] = []
        for a in accomplishments_raw:
            if not isinstance(a, dict):
                continue
            if (a.get("category") or "").lower().startswith("cert"):
                certifications.append(
                    {
                        "name": a.get("title"),
                        "issuer": a.get("issuer"),
                        "date_issued": a.get("issued_date"),
                        "credential_id": a.get("credential_id"),
                        "credential_url": a.get("credential_url"),
                    }
                )

        return RawSourcedCandidate(
            source_platform="linkedin_open_to_work",
            source_url=url,
            source_external_id=external_id,
            full_name=entry.get("name") or entry.get("full_name"),
            headline=entry.get("headline"),
            about=entry.get("about") or entry.get("summary"),
            location_text=entry.get("location") or entry.get("location_text"),
            current_title=entry.get("job_title") or entry.get("current_title"),
            current_company=entry.get("company") or entry.get("current_company"),
            years_experience=entry.get("years_experience"),
            open_to_work=bool(entry.get("open_to_work", True)),
            skills=list(entry.get("skills") or []),
            desired_titles=list(entry.get("desired_titles") or []),
            desired_job_types=list(entry.get("desired_job_types") or []),
            desired_workplace=list(entry.get("desired_workplace") or []),
            experiences=normalized_experiences,
            education=normalized_education,
            projects=[p for p in (entry.get("projects") or []) if isinstance(p, dict)],
            certifications=certifications,
            contacts=normalized_contacts,
            links=[
                {"link_type": "linkedin", "url": url}
            ] if url else [],
            raw=dict(entry),
        )

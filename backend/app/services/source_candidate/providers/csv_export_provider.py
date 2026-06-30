"""
CSV / JSON export provider — reads consented candidate exports from disk.

Use this provider when the organisation has obtained candidate data
through approved channels (candidate-uploaded export, recruitment-platform
data export with the platform's permission). Never reads private LinkedIn
pages or bypasses authentication.

The directory location is controlled by ``LINKEDIN_CANDIDATE_EXPORT_DIR``
in ``settings`` (re-used so this drops in without new env vars).

Each file in the directory is treated as one candidate. Both JSON and CSV
formats are accepted. CSV columns map by header name; unknown columns
are kept in ``raw`` for later inspection.
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.source_candidate.provider import (
    CandidateSourcingProvider,
    ExternalCandidatePayload,
    FetchOpenToWorkInput,
)

logger = logging.getLogger(__name__)
_settings = get_settings()


class CsvExportSourcingProvider(CandidateSourcingProvider):
    provider_name = "csv_export"

    def __init__(self, *, export_dir: str | None = None) -> None:
        self.export_dir = Path(
            export_dir or _settings.linkedin_candidate_export_dir,
        )

    async def fetch_open_to_work_candidates(
        self, input: FetchOpenToWorkInput,
    ) -> list[ExternalCandidatePayload]:
        entries = await asyncio.to_thread(self._load_entries)
        if not entries:
            return []

        kws = [k.lower() for k in (input.keywords or []) if k]
        loc = (input.location or "").strip().lower() or None
        filtered = [e for e in entries if _matches(e, kws, loc)] or entries
        out: list[ExternalCandidatePayload] = []
        for entry in filtered[: max(1, input.count)]:
            out.append(_entry_to_payload(entry))
        return out

    def _load_entries(self) -> list[dict[str, Any]]:
        if not self.export_dir.exists():
            logger.info(
                "[SourceCandidate][csv] export dir not found: %s",
                self.export_dir,
            )
            return []
        out: list[dict[str, Any]] = []
        for path in sorted(self.export_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[SourceCandidate][csv] cannot parse %s: %s", path, exc,
                )
                continue
            if isinstance(payload, list):
                out.extend([p for p in payload if isinstance(p, dict)])
            elif isinstance(payload, dict):
                out.append(payload)
        for path in sorted(self.export_dir.glob("*.csv")):
            try:
                rows = _read_csv(path)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[SourceCandidate][csv] cannot parse %s: %s", path, exc,
                )
                continue
            out.extend(rows)
        return out


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [
            {k.strip(): (v or "").strip() for k, v in row.items() if k}
            for row in reader
        ]


def _matches(entry: dict[str, Any], keywords: list[str], location: str | None) -> bool:
    if location:
        loc_text = (
            entry.get("location") or entry.get("location_text") or ""
        ).lower()
        if location not in loc_text:
            return False
    if not keywords:
        return True
    blob = " ".join(
        [
            (entry.get("name") or entry.get("full_name") or ""),
            (entry.get("headline") or ""),
            (entry.get("current_title") or entry.get("job_title") or ""),
            " ".join(entry.get("skills") or []) if isinstance(entry.get("skills"), list) else "",
            entry.get("skills") if isinstance(entry.get("skills"), str) else "",
        ]
    ).lower()
    return any(k in blob for k in keywords)


def _entry_to_payload(entry: dict[str, Any]) -> ExternalCandidatePayload:
    url = entry.get("linkedin_url") or entry.get("profile_url") or entry.get("url")
    raw_skills = entry.get("skills") or []
    if isinstance(raw_skills, str):
        skills = [s.strip() for s in raw_skills.split(",") if s.strip()]
    else:
        skills = [str(s) for s in raw_skills if s]
    open_evidence = entry.get("open_to_work_evidence") or (
        "Open-to-work field present in consented export"
        if entry.get("open_to_work")
        else None
    )
    return ExternalCandidatePayload(
        provider="csv_export",
        external_id=str(
            entry.get("external_id") or entry.get("id") or entry.get("public_id") or ""
        ) or None,
        full_name=entry.get("name") or entry.get("full_name"),
        headline=entry.get("headline"),
        current_title=entry.get("current_title") or entry.get("job_title"),
        current_company=entry.get("current_company") or entry.get("company"),
        location=entry.get("location") or entry.get("location_text"),
        profile_url=url,
        email=entry.get("email"),
        phone=entry.get("phone"),
        skills=skills,
        open_to_work_signal=_truthy(entry.get("open_to_work")),
        open_to_work_evidence=open_evidence,
        technical_role_evidence=None,
        raw=dict(entry),
    )


def _truthy(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "open", "ok"}
    return None

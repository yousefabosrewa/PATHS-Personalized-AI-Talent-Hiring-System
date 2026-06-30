"""
Canonical taxonomy for candidate provenance.

Used as the single source of truth across:

  * candidates.source_type column
  * candidate_pool_members.source_type column
  * organization_candidate_source_settings.use_*_default flags
  * job_candidate_pool_configs.use_* flags
  * REST API responses (lower-case string)

The string values must remain stable — they are stored in the database. If
you need to add a new source type, append it here, update the
`ALL_SOURCES` list, and write a migration that widens any CHECK constraints.
"""

from __future__ import annotations

from enum import Enum


class SourceType(str, Enum):
    """Canonical candidate-source identifier."""

    PATHS_PROFILE = "paths_profile"
    SOURCED = "sourced"
    COMPANY_UPLOADED = "company_uploaded"
    JOB_FAIR = "job_fair"
    ATS_IMPORT = "ats_import"
    MANUAL_ADD = "manual_add"


ALL_SOURCES: tuple[SourceType, ...] = tuple(SourceType)


# Human-readable label for each source. Frontend uses this for tooltips and
# tile labels via the API; do not duplicate this string in the frontend.
SOURCE_LABELS: dict[SourceType, str] = {
    SourceType.PATHS_PROFILE: "PATHS Profiles",
    SourceType.SOURCED: "Sourced Candidates",
    SourceType.COMPANY_UPLOADED: "Uploaded Candidates",
    SourceType.JOB_FAIR: "Job Fair Candidates",
    SourceType.ATS_IMPORT: "ATS Imported",
    SourceType.MANUAL_ADD: "Manually Added",
}

SOURCE_DESCRIPTIONS: dict[SourceType, str] = {
    SourceType.PATHS_PROFILE: (
        "Candidates with PATHS accounts who completed their profile and are "
        "actively looking for jobs."
    ),
    SourceType.SOURCED: (
        "Candidates collected by PATHS sourcing agents from external "
        "platforms (LinkedIn, GitHub, Telegram, etc.)."
    ),
    SourceType.COMPANY_UPLOADED: (
        "Candidates uploaded by your company through CV upload, CSV/Excel, "
        "or manual entry."
    ),
    SourceType.JOB_FAIR: (
        "Candidates imported from job fair rosters or university events."
    ),
    SourceType.ATS_IMPORT: (
        "Candidates imported from external ATS exports."
    ),
    SourceType.MANUAL_ADD: (
        "Candidates manually added by a recruiter without a CV upload."
    ),
}


# Map "use_*" flags ↔ source types. The settings/config tables use these
# verbose flag names because they are clearer at the SQL level. Helpers that
# read a settings row into a {source_type: bool} dict use this mapping.
SETTINGS_FLAG_MAP: dict[SourceType, str] = {
    SourceType.PATHS_PROFILE: "use_paths_profiles",
    SourceType.SOURCED: "use_sourced_candidates",
    SourceType.COMPANY_UPLOADED: "use_uploaded_candidates",
    SourceType.JOB_FAIR: "use_job_fair_candidates",
    SourceType.ATS_IMPORT: "use_ats_candidates",
    # MANUAL_ADD has no toggle — manually-added candidates always belong to
    # the company that added them and are always considered for that
    # company's jobs.
}

DEFAULTS_FLAG_MAP: dict[SourceType, str] = {
    src: f"{flag}_default" for src, flag in SETTINGS_FLAG_MAP.items()
}


def parse_source_type(value: str | None) -> SourceType | None:
    if not value:
        return None
    try:
        return SourceType(value)
    except ValueError:
        return None

"""PATHS Outreach Agent (fix4.md).

Searches candidates from the org's internal database or from the
outbound sourced pool (LinkedIn Open-to-Work), anonymizes them, and
asks the OpenRouter-backed agent to write a concise recruiter-facing
explanation for each shortlist entry.

Public API:

    run_outreach_search(db, *, org_id, mode, query, top_k, ...) -> dict

The result shape is documented in :pyfunc:`run_outreach_search`.
"""

from .service import (
    OutreachMode,
    OutreachShortlistItem,
    candidate_alias,
    run_outreach_search,
)

__all__ = [
    "OutreachMode",
    "OutreachShortlistItem",
    "candidate_alias",
    "run_outreach_search",
]

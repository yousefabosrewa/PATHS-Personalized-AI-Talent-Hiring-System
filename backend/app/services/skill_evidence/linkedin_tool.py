"""
LinkedIn evidence tool — best-effort public-profile fetch.

LinkedIn has no open public API for arbitrary profiles, so this tool:

  1. Prefers a configured ``LINKEDIN_MCP_SERVER_URL`` — if set, defers to
     that real MCP server (operators with a working LinkedIn MCP plug
     it in without code changes).

  2. Falls back to fetching the candidate's public LinkedIn URL with a
     realistic browser User-Agent. LinkedIn aggressively challenges
     scrapers, so the tool treats any non-200 / login-wall response as
     ``blocked`` rather than as missing evidence — the brief insists we
     never silently claim "no evidence" when we couldn't actually read
     anything.

  3. When parse succeeds, extracts ``<meta name="description">`` /
     ``<title>`` / OpenGraph blurbs plus visible skill-list-style words.
     The agent does the heavy lifting; this tool only surfaces
     candidate raw text.

If LinkedIn URL isn't on file, returns ``url_missing`` so the UI can
prompt the recruiter to add it.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.evidence import CandidateSource
from app.services.skill_evidence.types import EvidenceResult, EvidenceSnippet

logger = logging.getLogger(__name__)


_LINKEDIN_HOST_RX = re.compile(r"^https?://(?:[a-z]{2,3}\.)?linkedin\.com/", re.IGNORECASE)
_REQUEST_TIMEOUT = 15.0

# Tags we lift verbatim from the HTML when present.
_META_TAGS = (
    ("meta[name=description]", "content"),
    ("meta[property='og:description']", "content"),
    ("meta[property='og:title']", "content"),
    ("title", None),
)


class LinkedinEvidenceTool:
    """MCP-style tool for LinkedIn public-profile evidence."""

    source = "linkedin"

    def __init__(self, db: Session) -> None:
        self._db = db
        self._settings = get_settings()

    def gather_evidence(
        self,
        *,
        candidate_id: uuid.UUID,
        skill: str,
    ) -> EvidenceResult:
        url = self._lookup_url(candidate_id)
        if not url:
            return EvidenceResult(
                source="linkedin",
                status="url_missing",
                snippets=[],
                reason=(
                    "No LinkedIn URL is recorded for this candidate. Add one "
                    "on the profile so the agent can look for public evidence."
                ),
            )

        # ── 1. Real MCP server when configured ────────────────────
        mcp_url = (self._settings.linkedin_mcp_server_url or "").strip()
        if mcp_url:
            return self._fetch_via_mcp(mcp_url=mcp_url, profile_url=url, skill=skill)

        # ── 2. Public-HTML best effort ────────────────────────────
        return self._fetch_public_html(profile_url=url, skill=skill)

    # ── Sources ───────────────────────────────────────────────────

    def _fetch_via_mcp(
        self, *, mcp_url: str, profile_url: str, skill: str,
    ) -> EvidenceResult:
        """Talk to a configured LinkedIn MCP server.

        The contract is intentionally minimal: POST ``{profile_url, skill}``
        and accept either an ``EvidenceResult`` shape directly or a list
        of ``{text, source_url}`` snippets that we wrap. Keeps the door
        open for any community LinkedIn MCP without coupling to one
        implementation.
        """
        try:
            with httpx.Client(timeout=_REQUEST_TIMEOUT) as client:
                r = client.post(
                    mcp_url.rstrip("/") + "/evidence",
                    json={"profile_url": profile_url, "skill": skill},
                )
        except httpx.HTTPError as exc:
            logger.warning("[LinkedinEvidence] MCP fetch failed: %s", exc)
            return EvidenceResult(
                source="linkedin",
                status="error",
                snippets=[],
                reason=f"LinkedIn MCP server unreachable: {exc}",
            )
        if not r.is_success:
            return EvidenceResult(
                source="linkedin",
                status="error",
                snippets=[],
                reason=f"LinkedIn MCP server returned {r.status_code}.",
            )
        try:
            payload = r.json()
        except ValueError:
            payload = None
        if not isinstance(payload, dict):
            return EvidenceResult(
                source="linkedin",
                status="error",
                snippets=[],
                reason="LinkedIn MCP server returned a non-JSON response.",
            )
        # Tolerate both schemas.
        if "snippets" in payload and isinstance(payload["snippets"], list):
            return EvidenceResult(
                source="linkedin",
                status=payload.get("status") or "available",
                snippets=[
                    EvidenceSnippet(
                        text=str(s.get("text") or ""),
                        source_url=s.get("source_url") or profile_url,
                        metadata=s.get("metadata") or {},
                    )
                    for s in payload["snippets"]
                    if isinstance(s, dict) and s.get("text")
                ],
                reason=str(payload.get("reason") or ""),
                raw={"via": "mcp_server", "server": mcp_url},
            )
        return EvidenceResult(
            source="linkedin",
            status="error",
            snippets=[],
            reason="LinkedIn MCP server returned an unrecognised payload.",
        )

    def _fetch_public_html(self, *, profile_url: str, skill: str) -> EvidenceResult:
        if not _LINKEDIN_HOST_RX.search(profile_url):
            return EvidenceResult(
                source="linkedin",
                status="error",
                snippets=[],
                reason=f"URL does not look like a LinkedIn profile: {profile_url!r}.",
            )
        headers = {
            "User-Agent": self._settings.linkedin_user_agent or "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en",
        }
        try:
            with httpx.Client(timeout=_REQUEST_TIMEOUT, follow_redirects=True) as client:
                r = client.get(profile_url, headers=headers)
        except httpx.HTTPError as exc:
            return EvidenceResult(
                source="linkedin",
                status="error",
                snippets=[],
                reason=f"LinkedIn fetch failed: {exc}",
            )
        if r.status_code in (401, 403, 999) or "authwall" in r.url.path.lower():
            return EvidenceResult(
                source="linkedin",
                status="blocked",
                snippets=[],
                reason=(
                    "LinkedIn blocked the public fetch (auth wall). Configure "
                    "LINKEDIN_MCP_SERVER_URL with a real LinkedIn MCP to get "
                    "verified evidence."
                ),
            )
        if not r.is_success:
            return EvidenceResult(
                source="linkedin",
                status="error",
                snippets=[],
                reason=f"LinkedIn returned {r.status_code}.",
            )
        text = r.text or ""
        if "Sign in to LinkedIn" in text and "authwall" in text:
            return EvidenceResult(
                source="linkedin",
                status="blocked",
                snippets=[],
                reason=(
                    "LinkedIn served the sign-in wall instead of the profile. "
                    "Configure LINKEDIN_MCP_SERVER_URL to bypass this."
                ),
            )

        snippets = self._extract_snippets(text, skill=skill, source_url=profile_url)
        if not snippets:
            return EvidenceResult(
                source="linkedin",
                status="no_match",
                snippets=[],
                reason=(
                    "LinkedIn page loaded but did not contain a public mention "
                    f"of {skill!r}. LinkedIn hides most details behind the "
                    "sign-in wall — connecting a LinkedIn MCP gives richer "
                    "evidence."
                ),
                raw={"via": "public_html"},
            )
        return EvidenceResult(
            source="linkedin",
            status="available",
            snippets=snippets,
            reason="",
            raw={"via": "public_html"},
        )

    # ── Internals ─────────────────────────────────────────────────

    @staticmethod
    def _extract_snippets(
        html: str, *, skill: str, source_url: str,
    ) -> list[EvidenceSnippet]:
        """Pull meta description / title and the small set of visible text
        that contains the skill. Intentionally light-weight — heavy DOM
        parsing isn't worth the complexity for a best-effort fetch."""
        if not skill:
            return []
        out: list[EvidenceSnippet] = []
        pattern = rf"(?<![A-Za-z0-9+#.]){re.escape(skill)}(?![A-Za-z0-9+#.])"

        # Meta description (almost always populated by LinkedIn).
        m = re.search(
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
            html,
            flags=re.IGNORECASE,
        )
        if m and re.search(pattern, m.group(1), flags=re.IGNORECASE):
            out.append(
                EvidenceSnippet(
                    text=f"LinkedIn meta description: {m.group(1)[:480]}",
                    source_url=source_url,
                    weight_hint=1.1,
                    metadata={"field": "meta_description"},
                )
            )

        # Title.
        m = re.search(r"<title[^>]*>([^<]+)</title>", html, flags=re.IGNORECASE)
        if m and re.search(pattern, m.group(1), flags=re.IGNORECASE):
            out.append(
                EvidenceSnippet(
                    text=f"LinkedIn page title: {m.group(1)[:240]}",
                    source_url=source_url,
                    weight_hint=0.9,
                    metadata={"field": "title"},
                )
            )

        # Strip tags and pull windows around the first few matches.
        stripped = re.sub(r"<[^>]+>", " ", html)
        stripped = re.sub(r"\s+", " ", stripped).strip()
        for m in list(re.finditer(pattern, stripped, flags=re.IGNORECASE))[:3]:
            start = max(0, m.start() - 140)
            end = min(len(stripped), m.end() + 140)
            out.append(
                EvidenceSnippet(
                    text=f"Public page text: …{stripped[start:end]}…",
                    source_url=source_url,
                    weight_hint=0.8,
                    metadata={"field": "body"},
                )
            )

        # Dedupe on text.
        seen: set[str] = set()
        unique: list[EvidenceSnippet] = []
        for s in out:
            key = s.text
            if key in seen:
                continue
            seen.add(key)
            unique.append(s)
        return unique[:5]

    def _lookup_url(self, candidate_id: uuid.UUID) -> str | None:
        row = self._db.execute(
            select(CandidateSource).where(
                CandidateSource.candidate_id == candidate_id,
                CandidateSource.source == "linkedin",
            ).limit(1)
        ).scalar_one_or_none()
        return row.url if row and row.url else None

"""
LinkedIn MCP sourcing provider (fix6.md, inspired by stickerdaniel/linkedin-mcp-server).

Speaks the MCP Streamable-HTTP transport against the linkedin-mcp-server
reference project. Uses the ``search_people`` tool, which the upstream
server backs by an authenticated Patchright/Chromium session — so all
compliance and access control sits with the MCP server, not here.

Handshake (per the MCP spec):
  1. POST initialize → capture ``Mcp-Session-Id`` from response headers.
  2. POST ``notifications/initialized`` (notification, no response).
  3. POST ``tools/call`` with the session id and the search arguments.

Falls back to the consented-export reader when ``LINKEDIN_MCP_URL`` is
empty, so the recruiter flow still works without a live MCP instance.
The fallback never invents candidates — if no exports are available, the
UI shows the spec's "provider unavailable" message.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.source_candidate.provider import (
    CandidateSourcingProvider,
    ExternalCandidatePayload,
    FetchOpenToWorkInput,
    SourcingProviderError,
)
from app.services.source_candidate.providers.csv_export_provider import (
    CsvExportSourcingProvider,
)

logger = logging.getLogger(__name__)
_settings = get_settings()


# MCP Streamable-HTTP requires both content types in Accept so the server
# can choose between an immediate JSON response and an SSE stream.
_MCP_ACCEPT = "application/json, text/event-stream"
_MCP_CONTENT_TYPE = "application/json"


class LinkedInMcpSourcingProvider(CandidateSourcingProvider):
    """HTTP MCP client for the linkedin-mcp-server reference project."""

    def __init__(
        self,
        *,
        mcp_url: str | None = None,
        provider_label: str = "linkedin_mcp",
    ) -> None:
        self.mcp_url = (mcp_url or _settings.linkedin_mcp_url or "").rstrip("/")
        # ``provider_name`` flows into the DB row. Recruiters may select
        # "external_recruitment_platform" as a label — the underlying MCP
        # call is the same; only the badge in the UI differs.
        self.provider_name = provider_label  # type: ignore[assignment]
        self._fallback = CsvExportSourcingProvider()

    async def fetch_open_to_work_candidates(
        self, input: FetchOpenToWorkInput,
    ) -> list[ExternalCandidatePayload]:
        if not self.mcp_url:
            logger.info(
                "[SourceCandidate][linkedin_mcp] LINKEDIN_MCP_URL not "
                "configured — falling back to consented CSV/JSON exports.",
            )
            return await self._fallback.fetch_open_to_work_candidates(input)

        try:
            entries = await self._search_people(input)
        except httpx.HTTPError as exc:
            logger.warning(
                "[SourceCandidate][linkedin_mcp] HTTP error talking to %s: %s",
                self.mcp_url, exc,
            )
            raise SourcingProviderError(
                "Unable to reach the LinkedIn MCP server. Check that the "
                "MCP server is running and LINKEDIN_MCP_URL is reachable."
            ) from exc
        except SourcingProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("[SourceCandidate][linkedin_mcp] unexpected error")
            raise SourcingProviderError(
                "LinkedIn MCP provider failed. Please retry or import from a "
                "CSV export."
            ) from exc

        out: list[ExternalCandidatePayload] = []
        for entry in entries[: max(1, input.count)]:
            out.append(_entry_to_payload(entry, provider_label=self.provider_name))  # type: ignore[arg-type]
        return out

    async def fetch_profile_details(self, *, username: str) -> dict[str, Any]:
        """Fetch one profile via ``get_person_profile`` → OTW signal + skills.

        Used by Find Talent to verify the public "Open to work" badge and to
        pull real "Top skills" so ranking isn't limited to the search snippet.
        """
        if not self.mcp_url or not username:
            return {}
        timeout = min(float(_settings.linkedin_mcp_timeout_seconds), 60.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                session_id = await self._initialize(client)
                try:
                    await self._post(
                        client,
                        {
                            "jsonrpc": "2.0",
                            "method": "notifications/initialized",
                            "params": {},
                        },
                        session_id=session_id,
                        expect_body=False,
                    )
                    result = await self._call_tool(
                        client,
                        session_id=session_id,
                        name="get_person_profile",
                        arguments={"linkedin_username": username},
                    )
                finally:
                    try:
                        await client.delete(
                            self.mcp_url,
                            headers={
                                "Accept": _MCP_ACCEPT,
                                "Mcp-Session-Id": session_id,
                            },
                        )
                    except httpx.HTTPError:
                        pass
            return _parse_profile_details(result)
        except (httpx.HTTPError, SourcingProviderError) as exc:
            logger.warning(
                "[SourceCandidate][linkedin_mcp] profile fetch failed for %s: %s",
                username, exc,
            )
            return {}
        except Exception:  # noqa: BLE001
            logger.exception("[SourceCandidate][linkedin_mcp] profile parse error")
            return {}

    # ── MCP handshake ──────────────────────────────────────────────────

    async def _search_people(
        self, input: FetchOpenToWorkInput,
    ) -> list[dict[str, Any]]:
        keywords = " ".join(input.keywords) if input.keywords else "open to work"
        async with httpx.AsyncClient(
            timeout=_settings.linkedin_mcp_timeout_seconds,
        ) as client:
            session_id = await self._initialize(client)
            try:
                await self._post(
                    client,
                    {
                        "jsonrpc": "2.0",
                        "method": "notifications/initialized",
                        "params": {},
                    },
                    session_id=session_id,
                    expect_body=False,
                )
                # v4.13.2 search_people(keywords, location, network,
                # current_company) — no ``limit``; the tool returns LinkedIn's
                # first results page (≈10 people). Only send args the tool
                # accepts (it rejects unexpected keyword arguments).
                arguments: dict[str, Any] = {"keywords": keywords}
                if input.location:
                    arguments["location"] = input.location
                result = await self._call_tool(
                    client,
                    session_id=session_id,
                    name="search_people",
                    arguments=arguments,
                )
            finally:
                # Best-effort session close so we don't leak browser sessions
                # on the MCP side.
                try:
                    await client.delete(
                        self.mcp_url,
                        headers={
                            "Accept": _MCP_ACCEPT,
                            "Mcp-Session-Id": session_id,
                        },
                    )
                except httpx.HTTPError:
                    pass

        return _entries_from_tool_result(result)

    async def _initialize(self, client: httpx.AsyncClient) -> str:
        envelope = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "paths-source-candidate",
                    "version": "1.0.0",
                },
            },
        }
        response = await self._post_raw(client, envelope, session_id=None)
        session_id = (
            response.headers.get("mcp-session-id")
            or response.headers.get("Mcp-Session-Id")
        )
        # Even when the initialize response is SSE, we still need to read
        # the body to keep the connection consistent. We ignore the
        # decoded payload here — only the session id matters at this point.
        await _decode_jsonrpc(response)
        if not session_id:
            raise SourcingProviderError(
                "MCP server did not return an Mcp-Session-Id during initialize.",
            )
        return session_id

    async def _call_tool(
        self,
        client: httpx.AsyncClient,
        *,
        session_id: str,
        name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        envelope = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        response = await self._post_raw(client, envelope, session_id=session_id)
        body = await _decode_jsonrpc(response)
        if body is None:
            raise SourcingProviderError(
                f"MCP tools/call '{name}' returned an empty response."
            )
        if body.get("error"):
            err = body["error"]
            raise SourcingProviderError(
                f"MCP {name} error: {err.get('message', 'unknown')}"
            )
        return body.get("result") or {}

    async def _post(
        self,
        client: httpx.AsyncClient,
        envelope: dict[str, Any],
        *,
        session_id: str | None,
        expect_body: bool = True,
    ) -> None:
        response = await self._post_raw(client, envelope, session_id=session_id)
        if expect_body:
            await _decode_jsonrpc(response)
        else:
            await response.aclose()

    async def _post_raw(
        self,
        client: httpx.AsyncClient,
        envelope: dict[str, Any],
        *,
        session_id: str | None,
    ) -> httpx.Response:
        headers = {
            "Accept": _MCP_ACCEPT,
            "Content-Type": _MCP_CONTENT_TYPE,
        }
        if session_id:
            headers["Mcp-Session-Id"] = session_id
        response = await client.post(self.mcp_url, json=envelope, headers=headers)
        response.raise_for_status()
        return response


# ── Response decoding ────────────────────────────────────────────────────


async def _decode_jsonrpc(response: httpx.Response) -> dict[str, Any] | None:
    """Decode a streamable-http response (JSON body or SSE stream)."""
    content_type = (response.headers.get("content-type") or "").lower()
    if "text/event-stream" in content_type:
        text = (await response.aread()).decode("utf-8", errors="replace")
        return _parse_first_sse_message(text)
    raw = await response.aread()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _parse_first_sse_message(text: str) -> dict[str, Any] | None:
    """Return the first SSE ``data:`` payload that decodes as JSON-RPC."""
    data_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
        elif not line.strip() and data_lines:
            joined = "\n".join(data_lines)
            data_lines = []
            try:
                parsed = json.loads(joined)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and ("result" in parsed or "error" in parsed):
                return parsed
    if data_lines:
        joined = "\n".join(data_lines)
        try:
            parsed = json.loads(joined)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, dict):
            return parsed
    return None


def _entries_from_tool_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten a ``search_people`` tools/call result into profile dicts.

    linkedin-scraper-mcp v4.x returns the MCP content envelope::

        {"content": [{"type": "text", "text": "<json>"}], "isError": false}

    where the inner JSON is::

        {"url": ..., "sections": {"search_results": "<raw page text>"},
         "references": {"search_results": [{"kind": "person", "url": "/in/..",
                                            "text": "Name View Name's profile"}]}}

    The ``references`` give clean name + profile URL per person; the
    ``sections`` text carries each person's headline/title and location in
    page order. We pair them to build structured entries.
    """
    # Some servers also return a top-level structured payload; prefer the
    # content envelope which is always present.
    payloads: list[dict[str, Any]] = []
    for item in result.get("content") or []:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if not text:
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            payloads.append(parsed)
    structured = result.get("structuredContent")
    if not payloads and isinstance(structured, dict):
        payloads.append(structured)

    entries: list[dict[str, Any]] = []
    for inner in payloads:
        sections = inner.get("sections") if isinstance(inner.get("sections"), dict) else {}
        references = inner.get("references") if isinstance(inner.get("references"), dict) else {}
        persons: list[dict[str, Any]] = []
        for ref_list in references.values():
            if not isinstance(ref_list, list):
                continue
            for ref in ref_list:
                if isinstance(ref, dict) and ref.get("kind") == "person" and ref.get("url"):
                    persons.append(ref)
        section_text = "\n".join(str(v) for v in sections.values())
        entries.extend(_people_from_search(section_text, persons))
    return entries


# Keep field values comfortably under the DB's VARCHAR(255) columns so a
# stray long string (e.g. a consent banner) can never break the insert.
_MAX_NAME = 200
_MAX_TEXT = 240


def _people_from_search(
    text: str, persons: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build candidates from profile references, enriched with headline/location.

    Only entries backed by a real ``/in/<id>`` profile reference become
    candidates. This naturally drops LinkedIn interstitials (cookie-consent /
    "due to a new EU law" banners, login walls) that carry no person links and
    would otherwise be mis-parsed into a junk candidate with banner-length text.
    """
    ordered: list[dict[str, Any]] = []
    for ref in persons:
        url = str(ref.get("url") or "")
        if url.startswith("/"):
            url = "https://www.linkedin.com" + url
        name = _clean_ref_name(str(ref.get("text") or ""))
        if not name or "/in/" not in url:
            continue
        ordered.append({"name": name, "url": url, "public_id": _public_id(url)})

    if not ordered:
        return []

    parsed_blocks = _parse_search_blocks(text)
    blocks_by_name: dict[str, dict[str, Any]] = {}
    for blk in parsed_blocks:
        nm = (blk.get("name") or "").strip().lower()
        if nm and nm not in blocks_by_name:
            blocks_by_name[nm] = blk

    out: list[dict[str, Any]] = []
    for i, ref in enumerate(ordered):
        nm = (ref.get("name") or "").strip().lower()
        blk = blocks_by_name.get(nm) or (
            parsed_blocks[i] if i < len(parsed_blocks) else {}
        )
        title = _truncate(blk.get("title"), _MAX_TEXT)
        out.append(
            {
                "name": _truncate(ref["name"], _MAX_NAME),
                "headline": title,
                "job_title": title,
                "location": _truncate(blk.get("location"), _MAX_NAME),
                "linkedin_url": ref["url"],
                "public_id": ref.get("public_id"),
            }
        )
    return out


def _truncate(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s[:limit] if s else None


def _parse_search_blocks(text: str) -> list[dict[str, Any]]:
    """Split the people-search page text into per-person {name,title,location}.

    Each person block ends with a ``Message`` line and looks like::

        <Name>
        View <Name>'s profile
        · 3rd+
        3rd+ degree connection
        <Headline / Title>
        <Location>
        Message
    """
    blocks: list[list[str]] = []
    cur: list[str] = []
    for raw_line in (text or "").split("\n"):
        s = raw_line.strip()
        if s.lower() == "message":
            if cur:
                blocks.append(cur)
                cur = []
            continue
        if s:
            cur.append(s)
    if cur:
        blocks.append(cur)

    parsed: list[dict[str, Any]] = []
    for blk in blocks:
        info = _parse_one_block(blk)
        if info:
            parsed.append(info)
    return parsed


def _parse_one_block(lines: list[str]) -> dict[str, Any] | None:
    lines = [l for l in lines if l]
    # Drop the leading "Search results for ..." header if present.
    if lines and lines[0].lower().startswith("search results for"):
        lines = lines[1:]
    if not lines:
        return None
    name = lines[0]
    # Everything after the "... degree connection" marker is headline + location.
    deg_idx: int | None = None
    for i, l in enumerate(lines):
        if "degree connection" in l.lower():
            deg_idx = i
            break
    rest = lines[deg_idx + 1:] if deg_idx is not None else lines[1:]
    rest = [
        l for l in rest
        if not l.lower().startswith("view ")
        and "degree connection" not in l.lower()
        and "are these results helpful" not in l.lower()
        and l not in {"·", "•"}
        and not l.lower().endswith("degree connection")
    ]
    title = rest[0] if len(rest) >= 1 else None
    location = rest[1] if len(rest) >= 2 else None
    return {"name": name, "title": title, "location": location}


# ── Profile-detail parsing (Open-to-Work + skills) ───────────────────────

_OTW_PATTERNS = ("open to work", "#opentowork", "opentowork", "open for work")
_SECTION_STOP = {
    "top skills", "activity", "experience", "education", "featured",
    "licenses & certifications", "skills", "recommendations", "interests",
    "languages", "honors & awards", "projects", "courses", "volunteering",
}


def _profile_text_from_result(result: dict[str, Any]) -> str:
    for item in result.get("content") or []:
        text = item.get("text") if isinstance(item, dict) else None
        if not text:
            continue
        try:
            inner = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(inner, dict):
            sections = inner.get("sections") if isinstance(inner.get("sections"), dict) else {}
            if sections:
                return "\n".join(str(v) for v in sections.values())
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        sections = structured.get("sections") if isinstance(structured.get("sections"), dict) else {}
        return "\n".join(str(v) for v in sections.values())
    return ""


def _parse_profile_details(result: dict[str, Any]) -> dict[str, Any]:
    text = _profile_text_from_result(result)
    if not text:
        return {}
    low = text.lower()
    otw = any(p in low for p in _OTW_PATTERNS)
    evidence: str | None = None
    if otw:
        idx = next((low.find(p) for p in _OTW_PATTERNS if p in low), -1)
        if idx >= 0:
            evidence = " ".join(text[idx: idx + 90].split())[:140]
    return {
        "open_to_work": otw,
        "open_to_work_evidence": evidence,
        "skills": _extract_top_skills(text),
        "about": _extract_about(text),
    }


def _extract_top_skills(text: str) -> list[str]:
    """Pull the 'Top skills' line (e.g. 'Angular • SQL • Microsoft Azure • C#')."""
    lines = [l.strip() for l in (text or "").split("\n")]
    for i, line in enumerate(lines):
        if not line.lower().startswith("top skills"):
            continue
        tail = line.split(":", 1)[1] if ":" in line else ""
        candidates = ([tail] if tail.strip() else []) + lines[i + 1: i + 4]
        for cand in candidates:
            if any(sep in cand for sep in ("•", "•", "·", "|")):
                parts = re.split(r"[••·|]", cand)
                skills = [p.strip() for p in parts if p.strip()]
                if skills:
                    return skills[:15]
    return []


def _extract_about(text: str) -> str | None:
    lines = [l.rstrip() for l in (text or "").split("\n")]
    for i, line in enumerate(lines):
        if line.strip().lower() == "about":
            chunk: list[str] = []
            for nxt in lines[i + 1: i + 14]:
                s = nxt.strip()
                if s.lower() in _SECTION_STOP:
                    break
                if s:
                    chunk.append(s)
            joined = " ".join(chunk).strip()
            return joined[:600] or None
    return None


def _clean_ref_name(text: str) -> str:
    """'Pedro Cera View Pedro Cera's profile' → 'Pedro Cera'."""
    for marker in (" View ", " view "):
        if marker in text:
            return text.split(marker, 1)[0].strip()
    return text.strip()


def _public_id(url: str) -> str | None:
    if not url or "/in/" not in url:
        return None
    tail = url.rstrip("/").split("/in/", 1)[-1]
    return tail.split("/")[0] or None


# ── Mapping to internal payload ──────────────────────────────────────────


def _entry_to_payload(
    entry: dict[str, Any], *, provider_label: str = "linkedin_mcp",
) -> ExternalCandidatePayload:
    url = entry.get("linkedin_url") or entry.get("profile_url") or entry.get("url")
    raw_skills = entry.get("skills") or []
    if isinstance(raw_skills, str):
        skills = [s.strip() for s in raw_skills.split(",") if s.strip()]
    else:
        skills = [str(s) for s in raw_skills if s]
    headline = entry.get("headline") or ""
    open_signal = bool(entry.get("open_to_work")) if "open_to_work" in entry else None
    if open_signal is None and "open to work" in headline.lower():
        open_signal = True
    open_evidence = entry.get("open_to_work_evidence")
    if open_evidence is None and open_signal:
        open_evidence = (
            f"Headline contains open-to-work signal: '{headline}'"
            if "open to work" in headline.lower()
            else "Provider returned open_to_work=true"
        )
    return ExternalCandidatePayload(
        provider=provider_label,  # type: ignore[arg-type]
        external_id=str(
            entry.get("public_id")
            or entry.get("external_id")
            or entry.get("id")
            or (url.rstrip("/").split("/")[-1] if url else "")
        ) or None,
        full_name=entry.get("name") or entry.get("full_name"),
        headline=entry.get("headline"),
        current_title=entry.get("job_title") or entry.get("current_title"),
        current_company=entry.get("company") or entry.get("current_company"),
        location=entry.get("location") or entry.get("location_text"),
        profile_url=url,
        email=entry.get("email"),
        phone=entry.get("phone"),
        skills=skills,
        open_to_work_signal=open_signal,
        open_to_work_evidence=open_evidence,
        technical_role_evidence=None,
        raw=dict(entry),
    )

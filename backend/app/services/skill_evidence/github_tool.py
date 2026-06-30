"""
GitHub evidence tool — pulls per-skill verification from a candidate's
public GitHub presence using the GitHub REST API.

Why this is the strongest source: repos are first-hand behavioural
evidence. A candidate who claims React can be checked against the
languages distribution and the README text of every public repo. The
default weight in ``SKILL_EVIDENCE_WEIGHTS_JSON`` reflects that.

The tool prefers an authenticated PAT (set via ``GITHUB_TOKEN``) but
falls back to unauthenticated requests at ~60 req/h per IP — enough
for demo use. When the candidate has no GitHub URL on file the tool
returns ``url_missing`` so the agent / UI can route the recruiter to
the "set profile URL" affordance.
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


# Conservative limits to keep the API calls cheap even when an org has
# 200 candidates. The agent loop will surface the top-N most relevant
# repos rather than every public repo on the account.
_MAX_REPOS_SCANNED = 30
_MAX_REPOS_DEEP = 6     # repos we pull READMEs / language detail for
_REQUEST_TIMEOUT = 12.0


_GITHUB_HOST_RX = re.compile(r"^https?://(?:www\.)?github\.com/", re.IGNORECASE)


def _extract_username(url: str | None) -> str | None:
    if not url:
        return None
    if not _GITHUB_HOST_RX.search(url):
        # Accept bare usernames too — recruiters paste these often.
        bare = url.strip().lstrip("/").rstrip("/")
        if bare and "/" not in bare and " " not in bare and len(bare) <= 100:
            return bare
        return None
    path = _GITHUB_HOST_RX.sub("", url).strip("/")
    if not path:
        return None
    # First segment is the username — strip /repo, /repos?tab=foo, etc.
    username = path.split("/", 1)[0].strip()
    return username or None


class GithubEvidenceTool:
    """MCP-style tool wrapping the public GitHub REST API."""

    source = "github"

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
                source="github",
                status="url_missing",
                snippets=[],
                reason=(
                    "No GitHub URL is recorded for this candidate. Add one on "
                    "the profile so the agent can verify code-level evidence."
                ),
            )

        username = _extract_username(url)
        if not username:
            return EvidenceResult(
                source="github",
                status="error",
                snippets=[],
                reason=f"Could not parse a GitHub username from {url!r}.",
            )

        try:
            repos = self._list_repos(username)
        except _GithubError as exc:
            return EvidenceResult(
                source="github",
                status="blocked" if exc.is_blocked else "error",
                snippets=[],
                reason=str(exc),
            )

        if not repos:
            return EvidenceResult(
                source="github",
                status="no_match",
                snippets=[],
                reason=f"@{username} has no public repositories on GitHub.",
            )

        snippets: list[EvidenceSnippet] = []
        deep_scanned = 0
        languages_summary: dict[str, int] = {}

        # First pass: cheap signals from the repo list (name / description /
        # primary language). Highest-signal matches go on top.
        ranked = sorted(
            repos[: _MAX_REPOS_SCANNED],
            key=lambda r: (r.get("stargazers_count") or 0),
            reverse=True,
        )

        for repo in ranked:
            name = repo.get("name") or ""
            desc = (repo.get("description") or "").strip()
            lang = repo.get("language") or ""
            stars = repo.get("stargazers_count") or 0
            url_repo = repo.get("html_url") or f"https://github.com/{username}/{name}"
            languages_summary[lang] = languages_summary.get(lang, 0) + 1 if lang else languages_summary.get(lang, 0)

            if self._skill_matches(name, skill) or self._skill_matches(desc, skill) or self._skill_matches(lang, skill):
                snippets.append(
                    EvidenceSnippet(
                        text=(
                            f"Repo {name} ({lang or 'unspecified language'}, "
                            f"★{stars}) — {desc[:240] or 'no description'}"
                        ),
                        source_url=url_repo,
                        weight_hint=1.0 + min(0.5, stars / 50.0),
                        metadata={
                            "repo": name,
                            "language": lang,
                            "stars": stars,
                            "matched_field": (
                                "name" if self._skill_matches(name, skill)
                                else "description" if self._skill_matches(desc, skill)
                                else "language"
                            ),
                        },
                    )
                )

            # Second pass: pull deeper signals (README / languages stats) for
            # repos that already looked promising. Skips when we hit the cap.
            if deep_scanned < _MAX_REPOS_DEEP and (
                self._skill_matches(name, skill) or self._skill_matches(desc, skill)
            ):
                deep_scanned += 1
                readme_excerpt = self._fetch_readme_excerpt(username, name, skill)
                if readme_excerpt:
                    snippets.append(
                        EvidenceSnippet(
                            text=f"README of {name}: …{readme_excerpt}…",
                            source_url=url_repo,
                            weight_hint=1.2,
                            metadata={"repo": name, "kind": "readme_excerpt"},
                        )
                    )

        if not snippets:
            return EvidenceResult(
                source="github",
                status="no_match",
                snippets=[],
                reason=(
                    f"@{username} has public repositories but none reference "
                    f"{skill!r} in their names, descriptions, or primary language."
                ),
                raw={"languages_summary": languages_summary, "repo_count": len(repos)},
            )

        return EvidenceResult(
            source="github",
            status="available",
            snippets=snippets[:10],
            reason="",
            raw={
                "username": username,
                "languages_summary": languages_summary,
                "repo_count": len(repos),
                "deep_scanned": deep_scanned,
            },
        )

    # ── HTTP plumbing ──────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        h = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "PATHS-Skill-Evidence",
        }
        if self._settings.github_token:
            h["Authorization"] = f"Bearer {self._settings.github_token}"
        return h

    def _list_repos(self, username: str) -> list[dict[str, Any]]:
        url = f"{self._settings.github_api_base.rstrip('/')}/users/{username}/repos?per_page=100&sort=updated"
        try:
            with httpx.Client(timeout=_REQUEST_TIMEOUT) as client:
                r = client.get(url, headers=self._headers())
        except httpx.HTTPError as exc:
            raise _GithubError(f"network error: {exc}", is_blocked=False) from exc
        if r.status_code == 403:
            # 403 from GitHub during anonymous access usually means rate
            # limit — surface it cleanly so the UI can prompt for a PAT.
            raise _GithubError(
                "GitHub returned 403 — likely rate-limited. Add a GITHUB_TOKEN to .env to unlock 5000 req/h.",
                is_blocked=True,
            )
        if r.status_code == 404:
            raise _GithubError(f"GitHub user @{username} not found.", is_blocked=False)
        if not r.is_success:
            raise _GithubError(f"GitHub returned {r.status_code}: {r.text[:200]}", is_blocked=False)
        try:
            return r.json() or []
        except ValueError as exc:
            raise _GithubError(f"GitHub returned invalid JSON: {exc}", is_blocked=False) from exc

    def _fetch_readme_excerpt(self, username: str, repo: str, skill: str) -> str:
        url = f"{self._settings.github_api_base.rstrip('/')}/repos/{username}/{repo}/readme"
        try:
            with httpx.Client(timeout=_REQUEST_TIMEOUT) as client:
                r = client.get(
                    url,
                    headers={**self._headers(), "Accept": "application/vnd.github.raw+json"},
                )
        except httpx.HTTPError:
            return ""
        if not r.is_success:
            return ""
        text = r.text or ""
        if not text or not self._skill_matches(text, skill):
            return ""
        pattern = rf"(?<![A-Za-z0-9+#.]){re.escape(skill)}(?![A-Za-z0-9+#.])"
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m is None:
            return ""
        start = max(0, m.start() - 140)
        end = min(len(text), m.end() + 140)
        return text[start:end].strip()

    def _lookup_url(self, candidate_id: uuid.UUID) -> str | None:
        row = self._db.execute(
            select(CandidateSource).where(
                CandidateSource.candidate_id == candidate_id,
                CandidateSource.source == "github",
            ).limit(1)
        ).scalar_one_or_none()
        return row.url if row and row.url else None

    @staticmethod
    def _skill_matches(haystack: str, skill: str) -> bool:
        h = (haystack or "").lower()
        s = (skill or "").lower()
        if not h or not s:
            return False
        pattern = rf"(?<![A-Za-z0-9+#.]){re.escape(s)}(?![A-Za-z0-9+#.])"
        return re.search(pattern, h) is not None


class _GithubError(RuntimeError):
    """Tagged so the caller can distinguish "rate-limited" from "real error"."""

    def __init__(self, msg: str, *, is_blocked: bool) -> None:
        super().__init__(msg)
        self.is_blocked = is_blocked

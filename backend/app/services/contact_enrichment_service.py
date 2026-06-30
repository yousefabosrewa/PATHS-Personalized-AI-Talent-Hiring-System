from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.candidate import Candidate
from app.db.models.candidate_extras import CandidateLink
from app.db.models.contact_enrichment import EnrichedContact
from app.db.models.interview import Interview
from app.schemas.contact_enrichment import EnrichedContactOut, EnrichmentStatusOut

logger = logging.getLogger(__name__)

# Contact channels surfaced by the Contact Finder. "social" links (twitter,
# etc.) are listed separately as they arrive.
_CONTACT_FIELDS = ("email", "phone", "linkedin", "github", "portfolio")


def _contact_to_out(c: EnrichedContact) -> EnrichedContactOut:
    return EnrichedContactOut(
        id=c.id,
        candidate_id=c.candidate_id,
        organization_id=c.organization_id,
        contact_type=c.contact_type,
        original_value=c.original_value,
        enriched_value=c.enriched_value,
        confidence=c.confidence,
        status=c.status,
        source=c.source,
        provenance=c.provenance,
        validated_at=c.validated_at,
        approved_by=c.approved_by,
        approved_at=c.approved_at,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


def get_enrichment_status(db: Session, org_id: UUID) -> EnrichmentStatusOut:
    """Return summary stats (pending/approved/rejected by contact type)."""
    total = db.scalar(
        select(func.count(EnrichedContact.id)).where(EnrichedContact.organization_id == org_id)
    ) or 0
    pending = db.scalar(
        select(func.count(EnrichedContact.id)).where(
            EnrichedContact.organization_id == org_id,
            EnrichedContact.status == "pending",
        )
    ) or 0
    approved = db.scalar(
        select(func.count(EnrichedContact.id)).where(
            EnrichedContact.organization_id == org_id,
            EnrichedContact.status == "approved",
        )
    ) or 0
    rejected = db.scalar(
        select(func.count(EnrichedContact.id)).where(
            EnrichedContact.organization_id == org_id,
            EnrichedContact.status == "rejected",
        )
    ) or 0

    rows = db.execute(
        select(EnrichedContact.contact_type, func.count(EnrichedContact.id))
        .where(EnrichedContact.organization_id == org_id)
        .group_by(EnrichedContact.contact_type)
    ).all()
    by_type = {row[0]: row[1] for row in rows}

    status_rows = db.execute(
        select(EnrichedContact.status, func.count(EnrichedContact.id))
        .where(EnrichedContact.organization_id == org_id)
        .group_by(EnrichedContact.status)
    ).all()
    by_status = {row[0]: row[1] for row in status_rows}

    return EnrichmentStatusOut(
        total=total,
        pending=pending,
        approved=approved,
        rejected=rejected,
        by_type=by_type,
        by_status=by_status,
    )


def list_contacts(
    db: Session,
    org_id: UUID,
    status: str | None = None,
    contact_type: str | None = None,
) -> list[EnrichedContactOut]:
    """List enriched contacts with optional filters."""
    query = select(EnrichedContact).where(EnrichedContact.organization_id == org_id)
    if status:
        query = query.where(EnrichedContact.status == status)
    if contact_type:
        query = query.where(EnrichedContact.contact_type == contact_type)
    query = query.order_by(EnrichedContact.created_at.desc())
    contacts = db.scalars(query).all()
    return [_contact_to_out(c) for c in contacts]


def validate_email(email: str) -> dict:
    """Simple format validation + domain check.

    No external API calls — shows 'not configured' if no provider is set up.
    """
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    is_valid_format = bool(re.match(pattern, email))

    domain = email.split("@")[-1] if "@" in email else None

    result = {
        "email": email,
        "is_valid_format": is_valid_format,
        "domain": domain,
        "domain_has_mx": None,
        "is_disposable": None,
        "provider_configured": False,
        "provider_note": "External enrichment providers are not configured. "
        "Email validation and API-based enrichment require provider credentials.",
    }

    if is_valid_format and domain:
        try:
            import dns.resolver  # noqa: F811
            try:
                dns.resolver.resolve(domain, "MX", lifetime=5)
                result["domain_has_mx"] = True
            except Exception:  # noqa: BLE001
                result["domain_has_mx"] = False
        except ImportError:
            result["domain_has_mx"] = None

    return result


def _get_contact_or_404(db: Session, org_id: UUID, contact_id: UUID) -> EnrichedContact:
    contact = db.scalar(
        select(EnrichedContact).where(
            EnrichedContact.id == contact_id, EnrichedContact.organization_id == org_id,
        )
    )
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )
    return contact


def approve_contact(db: Session, contact_id: UUID, org_id: UUID, reviewer: str | None = None) -> EnrichedContactOut:
    """Mark a contact as approved."""
    contact = _get_contact_or_404(db, org_id, contact_id)
    if contact.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contact is already {contact.status}",
        )
    contact.status = "approved"
    contact.approved_at = datetime.now(timezone.utc)
    contact.validated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(contact)
    return _contact_to_out(contact)


def reject_contact(db: Session, contact_id: UUID, org_id: UUID, reviewer: str | None = None) -> EnrichedContactOut:
    """Mark a contact as rejected."""
    contact = _get_contact_or_404(db, org_id, contact_id)
    if contact.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contact is already {contact.status}",
        )
    contact.status = "rejected"
    db.commit()
    db.refresh(contact)
    return _contact_to_out(contact)


# ── Contact Finder: interview-process candidates + enrichment ───────────────


def _profile_urls(db: Session, candidate_id: UUID) -> dict[str, str | None]:
    """github / linkedin / portfolio from candidate_sources, with a
    CandidateLink fallback for candidates ingested via the CV pipeline."""
    out: dict[str, str | None] = {"github": None, "linkedin": None, "portfolio": None}
    try:
        from app.services.skill_evidence.service import list_profile_urls
        out.update(list_profile_urls(db, candidate_id=candidate_id))
    except Exception:  # noqa: BLE001
        logger.debug("[ContactFinder] list_profile_urls failed", exc_info=True)

    # Fall back to CandidateLink rows for anything still missing.
    links = db.execute(
        select(CandidateLink).where(CandidateLink.candidate_id == candidate_id)
    ).scalars().all()
    for link in links:
        lt = (link.link_type or "").lower()
        if "github" in lt and not out.get("github"):
            out["github"] = link.url
        elif "linkedin" in lt and not out.get("linkedin"):
            out["linkedin"] = link.url
        elif ("portfolio" in lt or "website" in lt or "personal" in lt) and not out.get("portfolio"):
            out["portfolio"] = link.url
    return out


def _candidate_contact_snapshot(db: Session, cand: Candidate, org_id: UUID) -> dict[str, Any]:
    """Build the contact set the Contact Finder shows for one candidate."""
    urls = _profile_urls(db, cand.id)
    # Enriched contacts (found by the enrich action) can supply values the base
    # record lacks. Scoped to the viewing organisation.
    extra_socials: list[dict[str, str]] = []
    enriched = db.execute(
        select(EnrichedContact).where(
            EnrichedContact.candidate_id == cand.id,
            EnrichedContact.organization_id == org_id,
        )
    ).scalars().all()

    contacts = {
        "email": cand.email or None,
        "phone": cand.phone or None,
        "linkedin": urls.get("linkedin"),
        "github": urls.get("github"),
        "portfolio": urls.get("portfolio"),
    }
    for e in enriched:
        val = e.enriched_value or e.original_value
        if not val:
            continue
        if e.contact_type in contacts and not contacts.get(e.contact_type):
            contacts[e.contact_type] = val
        elif e.contact_type not in contacts:
            extra_socials.append({"type": e.contact_type, "value": val})

    missing = [f for f in _CONTACT_FIELDS if not contacts.get(f)]
    return {
        "candidate_id": str(cand.id),
        "name": cand.full_name or "Candidate",
        "current_title": cand.current_title,
        "email": contacts["email"],
        "phone": contacts["phone"],
        "linkedin": contacts["linkedin"],
        "github": contacts["github"],
        "portfolio": contacts["portfolio"],
        "socials": extra_socials,
        "missing": missing,
        "complete": len(missing) == 0,
    }


def list_interview_candidates(db: Session, org_id: UUID) -> list[dict[str, Any]]:
    """Candidates who are in the interview process for this org, with their
    current contact info and which channels are still missing."""
    rows = db.execute(
        select(Interview.candidate_id)
        .where(
            Interview.organization_id == org_id,
            Interview.status != "cancelled",
        )
        .distinct()
    ).all()
    candidate_ids = [r[0] for r in rows]
    out: list[dict[str, Any]] = []
    for cid in candidate_ids:
        cand = db.get(Candidate, cid)
        if cand is None:
            continue
        out.append(_candidate_contact_snapshot(db, cand, org_id))
    # Show candidates with missing contact info first.
    out.sort(key=lambda c: (c["complete"], c["name"].lower()))
    return out


def _github_username_from(url: str | None) -> str | None:
    if not url:
        return None
    m = re.search(r"github\.com/([^/?#]+)", url, re.IGNORECASE)
    if m:
        return m.group(1).strip() or None
    # Bare handle stored without a URL.
    if re.fullmatch(r"[A-Za-z0-9-]{1,39}", url.strip()):
        return url.strip()
    return None


def _fetch_github_profile(username: str) -> dict[str, Any] | None:
    """Fetch a public GitHub profile (best-effort; honours optional token)."""
    s = get_settings()
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "PATHS-ContactFinder"}
    if s.github_token:
        headers["Authorization"] = f"Bearer {s.github_token}"
    url = f"{s.github_api_base.rstrip('/')}/users/{username}"
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(url, headers=headers)
        if r.status_code != 200:
            return None
        return r.json()
    except httpx.HTTPError as exc:
        logger.warning("[ContactFinder] GitHub fetch failed for %s: %s", username, exc)
        return None


def _normalize_url(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip()
    if not v:
        return None
    if not v.startswith(("http://", "https://")):
        v = "https://" + v
    return v


def enrich_candidate(db: Session, org_id: UUID, candidate_id: UUID) -> dict[str, Any]:
    """Best-effort enrichment of a candidate's missing contact channels.

    Uses the data already on file to search (the candidate's GitHub handle,
    and — when a LinkedIn MCP server is configured — their name). Found values
    are persisted; nothing is fabricated. Returns the refreshed snapshot plus
    a summary of what was found and what's still missing.
    """
    from app.core.candidate_access import org_can_view_candidate

    cand = db.get(Candidate, candidate_id)
    if cand is None or not org_can_view_candidate(db, org_id, candidate_id):
        raise HTTPException(status_code=404, detail="Candidate not found")

    before = _candidate_contact_snapshot(db, cand, org_id)
    found: list[str] = []
    notes: list[str] = []

    # 1) GitHub — if we know the handle, the public profile yields portfolio,
    #    a public email, and a Twitter/X handle. This is the "use the data we
    #    already have to search" path.
    gh_username = _github_username_from(before.get("github"))
    if gh_username:
        profile = _fetch_github_profile(gh_username)
        if profile:
            blog = _normalize_url(profile.get("blog"))
            if blog and not before.get("portfolio"):
                _set_profile_url(db, candidate_id, "portfolio", blog)
                found.append("portfolio")
            gh_email = profile.get("email")
            if gh_email and not cand.email:
                cand.email = gh_email
                _add_enriched(db, org_id, candidate_id, "email", gh_email, source="github_profile")
                found.append("email")
            tw = profile.get("twitter_username")
            if tw:
                tw_url = f"https://twitter.com/{tw}"
                _add_enriched(db, org_id, candidate_id, "twitter", tw_url, source="github_profile")
                found.append("twitter")
        else:
            notes.append("GitHub profile could not be read (rate limit or private).")
    elif "github" in before["missing"]:
        notes.append("No GitHub handle on file to search from.")

    # 2) LinkedIn — only if a LinkedIn MCP server is configured. Search by name.
    if not before.get("linkedin"):
        s = get_settings()
        if (s.linkedin_mcp_url or "").strip():
            li = _try_linkedin_mcp(cand.full_name, cand.current_title)
            if li:
                _set_profile_url(db, candidate_id, "linkedin", li)
                found.append("linkedin")
            else:
                notes.append("LinkedIn MCP returned no confident match.")
        else:
            notes.append("LinkedIn lookup needs an approved LinkedIn MCP/provider (not configured).")

    db.commit()
    db.refresh(cand)
    after = _candidate_contact_snapshot(db, cand, org_id)
    if not found:
        notes.insert(0, "No new contact details could be found from available sources.")
    return {
        "candidate": after,
        "found": found,
        "still_missing": after["missing"],
        "notes": notes,
    }


def _set_profile_url(db: Session, candidate_id: UUID, source: str, url: str) -> None:
    try:
        from app.services.skill_evidence.service import upsert_profile_url
        upsert_profile_url(db, candidate_id=candidate_id, source=source, url=url)
    except Exception:  # noqa: BLE001
        logger.warning("[ContactFinder] could not persist %s url", source, exc_info=True)


def _add_enriched(
    db: Session, org_id: UUID, candidate_id: UUID, contact_type: str, value: str, *, source: str,
) -> None:
    """Record a discovered contact value as an EnrichedContact (pending review)."""
    existing = db.scalar(
        select(EnrichedContact).where(
            EnrichedContact.organization_id == org_id,
            EnrichedContact.candidate_id == candidate_id,
            EnrichedContact.contact_type == contact_type,
            EnrichedContact.enriched_value == value,
        )
    )
    if existing:
        return
    db.add(
        EnrichedContact(
            candidate_id=candidate_id,
            organization_id=org_id,
            contact_type=contact_type,
            original_value=value,
            enriched_value=value,
            confidence=0.6,
            status="pending",
            source=source,
            provenance="contact_finder_enrich",
        )
    )


def _try_linkedin_mcp(name: str | None, title: str | None) -> str | None:
    """Best-effort LinkedIn profile URL via the configured MCP server."""
    if not name:
        return None
    try:
        import asyncio

        from app.services.source_candidate.providers.linkedin_mcp_provider import (
            LinkedInMcpSourcingProvider,
        )
        from app.services.source_candidate.provider import FetchOpenToWorkInput

        provider = LinkedInMcpSourcingProvider()
        kw = " ".join(filter(None, [name, title]))
        result = asyncio.run(
            provider.fetch_open_to_work_candidates(
                FetchOpenToWorkInput(
                    organization_id="contact-finder",
                    count=1,
                    role_category="technical",
                    keywords=[kw],
                )
            )
        )
        for c in result:
            if c.profile_url:
                return c.profile_url
    except Exception:  # noqa: BLE001
        logger.warning("[ContactFinder] LinkedIn MCP lookup failed", exc_info=True)
    return None

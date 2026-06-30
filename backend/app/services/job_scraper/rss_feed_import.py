"""
Compliant public RSS/Atom job feed import (no browser, no login walls).

Used when ``JOB_SCRAPER_SOURCE`` is ``remoteok_rss`` or ``weworkremotely_rss``.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html import unescape
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_TAG = re.compile(r"^(\{[^}]+\})?(.+)$")


def _local_name(el: ET.Element) -> str:
    m = _TAG.match(el.tag)
    return m.group(2) if m else el.tag


def _text(el: ET.Element | None) -> str:
    if el is None or el.text is None:
        return ""
    return unescape(el.text.strip())


def _strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = unescape(s)
    return re.sub(r"\s+", " ", s).strip()


@dataclass
class FeedItem:
    title: str
    link: str
    description: str
    published: str | None
    # Optional fields populated by extended RSS feeds (e.g. RemoteOK)
    company: str | None = None
    location: str | None = None
    tags: list[str] | None = None


def parse_feed_xml(xml_text: str) -> list[FeedItem]:
    root = ET.fromstring(xml_text)
    ln = _local_name(root)
    items: list[FeedItem] = []

    if ln == "rss":
        channel = root.find("channel")
        if channel is None:
            return []
        for node in channel:
            if _local_name(node) != "item":
                continue
            title = ""
            link = ""
            desc = ""
            pub = None
            company = None
            location = None
            tags: list[str] = []
            for child in node:
                cn = _local_name(child)
                if cn == "title":
                    title = _text(child)
                elif cn == "link":
                    link = (_text(child) or (child.get("href") or "")).strip()
                elif cn == "description":
                    desc = _text(child) or "".join(child.itertext())
                elif cn == "pubDate":
                    pub = _text(child) or None
                elif cn == "company":
                    company = _text(child) or None
                elif cn == "location":
                    location = _text(child) or None
                elif cn == "tags" or cn == "category":
                    raw = _text(child)
                    if raw:
                        tags.extend([t.strip() for t in raw.split(",") if t.strip()])
            if title and link:
                items.append(
                    FeedItem(
                        title=title,
                        link=link.strip(),
                        description=_strip_html(desc),
                        published=pub,
                        company=company,
                        location=location,
                        tags=tags or None,
                    ),
                )
        return items

    if ln == "feed":  # Atom
        for node in root:
            if _local_name(node) != "entry":
                continue
            title = ""
            link = ""
            desc = ""
            pub = None
            for child in node:
                cn = _local_name(child)
                if cn == "title":
                    title = "".join(child.itertext()).strip()
                elif cn == "link":
                    link = (child.get("href") or "").strip()
                elif cn in ("summary", "content"):
                    desc = "".join(child.itertext()).strip()
                elif cn == "published" or cn == "updated":
                    pub = _text(child) or pub
            if title and link:
                items.append(
                    FeedItem(
                        title=title,
                        link=link,
                        description=_strip_html(desc),
                        published=pub,
                    ),
                )
        return items

    logger.warning("[rss_feed_import] unknown root element: %s", ln)
    return []


async def fetch_feed_items(
    url: str,
    *,
    timeout: float = 60.0,
) -> list[FeedItem]:
    headers = {
        "User-Agent": "PATHS-JobImporter/1.0 (+https://paths.local; compliant RSS consumer)",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
    }
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
    return parse_feed_xml(r.text)


def feed_item_to_raw_job(item: FeedItem, *, source_platform: str) -> dict[str, Any] | None:
    title = item.title.strip()
    link = item.link.strip()
    if not title or not link:
        return None

    # Prefer the structured <company> tag (RemoteOK, etc.)
    company = (item.company or "").strip()
    job_title = title
    if not company:
        if " at " in title:
            job_title, company = title.rsplit(" at ", 1)
            job_title = job_title.strip()
            company = company.strip()
        elif " — " in title:
            job_title, company = title.split(" — ", 1)
            job_title = job_title.strip()
            company = company.strip()
    if not company:
        company = "Unknown Company"

    # Prefer the structured <location> tag, fall back to keyword sniffing.
    location = (item.location or "").strip()
    if not location:
        blob = (item.description + " " + title).lower()
        if "egypt" in blob or "cairo" in blob:
            location = "Egypt"
        elif "europe" in blob or "berlin" in blob or "uk" in blob:
            location = "Europe"
        else:
            location = "Remote"

    return {
        "company_name": company,
        "job_title": job_title[:250],
        "job_location": location,
        "job_url": link,
        "posting_date": item.published,
        "job_description": (item.description[:8000] if item.description else None),
        "platform": source_platform,
        "source_platform": source_platform,
        "source_url": link,
        "listing_source_url": link,
        "tags": item.tags or [],
        "raw": {
            "feed": source_platform,
            "link": link,
            "tags": item.tags or [],
        },
    }

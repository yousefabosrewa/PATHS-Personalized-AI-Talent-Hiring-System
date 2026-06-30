"""
LinkedIn account credentials helpers (fix6.md follow-up).

A recruiter pastes their ``li_at`` cookie (and optionally ``JSESSIONID``)
on the Organization settings page. These helpers:

  * encrypt + persist the cookies on ``organizations``
  * write ``~/.linkedin-mcp/cookies.json`` so the linkedin-mcp-server
    picks them up on its next browser-context creation
  * clear both on disconnect

The exact cookie format mirrors the format the upstream MCP server's
``LinkedInBrowser.import_cookies`` parses (``[{"name": "li_at", ...}]``).
"""

from __future__ import annotations

import json
import logging
import os
import platform
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.db.models.organization import Organization
from app.services.outreach_agent.token_crypto import decrypt_secret, encrypt_secret

logger = logging.getLogger(__name__)


def _mcp_auth_root() -> Path:
    """Path the MCP server reads ``cookies.json`` from.

    Mirrors ``linkedin_mcp_server.session_state.auth_root_dir`` for the
    default ``user_data_dir=~/.linkedin-mcp/profile`` config — the parent
    of the profile dir.
    """
    override = os.environ.get("LINKEDIN_MCP_AUTH_DIR")
    if override:
        return Path(override).expanduser()
    return Path("~/.linkedin-mcp").expanduser()


def cookies_json_path() -> Path:
    return _mcp_auth_root() / "cookies.json"


def write_mcp_cookies(*, li_at: str, jsessionid: str | None = None) -> Path:
    """Write the portable cookies file consumed by the linkedin-mcp-server."""

    cookies: list[dict[str, Any]] = [
        {
            "name": "li_at",
            "value": li_at,
            "domain": ".linkedin.com",
            "path": "/",
            "secure": True,
            "httpOnly": True,
            "sameSite": "None",
        },
    ]
    if jsessionid:
        cookies.append(
            {
                "name": "JSESSIONID",
                # LinkedIn wraps the JSESSIONID value in quotes; tolerate both.
                "value": jsessionid if jsessionid.startswith('"') else f'"{jsessionid}"',
                "domain": ".linkedin.com",
                "path": "/",
                "secure": True,
                "httpOnly": False,
                "sameSite": "None",
            }
        )

    target = cookies_json_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
    if platform.system() != "Windows":
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
    logger.info(
        "[LinkedInAccount] wrote MCP cookies file with %d cookies to %s",
        len(cookies), target,
    )
    return target


def clear_mcp_cookies() -> None:
    target = cookies_json_path()
    if target.exists():
        try:
            target.unlink()
            logger.info("[LinkedInAccount] removed MCP cookies file %s", target)
        except OSError as exc:
            logger.warning("Could not remove MCP cookies file: %s", exc)


def apply_org_credentials_to_mcp(org: Organization) -> bool:
    """Decrypt the org's stored cookies and (re)write the MCP cookies file."""
    li_at = decrypt_secret(org.linkedin_li_at_encrypted)
    if not li_at:
        return False
    jsessionid = decrypt_secret(org.linkedin_jsessionid_encrypted)
    write_mcp_cookies(li_at=li_at, jsessionid=jsessionid)
    return True


def store_credentials_on_org(
    org: Organization,
    *,
    email: str | None,
    li_at: str,
    jsessionid: str | None,
    connected_by_user_id: uuid.UUID,
) -> None:
    """Update the Organization row in-place with encrypted credentials."""
    org.linkedin_account_email = (email or "").strip() or None
    org.linkedin_li_at_encrypted = encrypt_secret(li_at)
    org.linkedin_jsessionid_encrypted = encrypt_secret(jsessionid) if jsessionid else None
    org.linkedin_connected_at = datetime.now(timezone.utc)
    org.linkedin_connected_by_user_id = connected_by_user_id


def clear_credentials_on_org(org: Organization) -> None:
    org.linkedin_account_email = None
    org.linkedin_li_at_encrypted = None
    org.linkedin_jsessionid_encrypted = None
    org.linkedin_connected_at = None
    org.linkedin_connected_by_user_id = None

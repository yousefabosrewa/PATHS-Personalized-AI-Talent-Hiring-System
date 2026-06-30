"""
PATHS Backend — RBAC constants.

Single source of truth for account types and organization roles. All
endpoints, dependencies, and seed scripts MUST use these symbols rather
than free-form string literals.

Added during the platform-admin / company-approval rollout.
"""

from __future__ import annotations

from enum import Enum


class AccountType(str, Enum):
    """High-level identity tier — present on every User row.

    - CANDIDATE: job-seeker. No organization context.
    - ORGANIZATION_MEMBER: belongs to one Organization. Has a role_code.
    - PLATFORM_ADMIN: created only via seed_platform_admins.py. Has no org.
    """

    CANDIDATE = "candidate"
    ORGANIZATION_MEMBER = "organization_member"
    PLATFORM_ADMIN = "platform_admin"


class OrgRole(str, Enum):
    """Role of an OrganizationMember inside its parent Organization.

    `platform_admin` is intentionally NOT a member role — platform admins
    sit above all organizations and are identified by AccountType.
    """

    ORG_ADMIN = "org_admin"
    HIRING_MANAGER = "hiring_manager"
    RECRUITER = "recruiter"
    HR = "hr"
    INTERVIEWER = "interviewer"


# Roles allowed to use the full hiring/recruiter API surface (jobs, applications,
# candidate search, etc.). Excludes interviewer (who only sees assigned scorecards).
HIRING_STAFF_ROLE_CODES: frozenset[str] = frozenset({
    OrgRole.ORG_ADMIN.value,
    OrgRole.HIRING_MANAGER.value,
    OrgRole.RECRUITER.value,
    OrgRole.HR.value,
    # Legacy values kept for backwards compatibility with rows that pre-date
    # the enum migration. seed_platform_admins / new code never write these.
    "hr_manager",
    "admin",
})

# All currently-valid role values that may be set on a new membership.
ALLOWED_ORG_ROLES: frozenset[str] = frozenset({r.value for r in OrgRole})

# Mapping from legacy role_code values to canonical OrgRole values. Used by
# any code that might still see old values from before the enum migration.
LEGACY_ROLE_REMAP: dict[str, str] = {
    "admin": OrgRole.ORG_ADMIN.value,
    "member": OrgRole.RECRUITER.value,
    "hr_manager": OrgRole.HR.value,
}


def normalize_role_code(role_code: str | None) -> str:
    """Map a possibly-legacy role_code to its canonical OrgRole value.

    Unknown values are returned as-is so callers can surface the conflict.
    """
    if not role_code:
        return OrgRole.RECRUITER.value
    return LEGACY_ROLE_REMAP.get(role_code, role_code)


__all__ = [
    "AccountType",
    "OrgRole",
    "HIRING_STAFF_ROLE_CODES",
    "ALLOWED_ORG_ROLES",
    "LEGACY_ROLE_REMAP",
    "normalize_role_code",
]

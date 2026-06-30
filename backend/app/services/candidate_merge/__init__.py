"""Candidate duplicate detection + merge (fix2_1.md Feature 2)."""

from app.services.candidate_merge.service import (
    DuplicateGroup,
    MergeOutcome,
    find_duplicate_groups,
    merge_group,
    normalize_email,
    normalize_name,
    normalize_phone,
)

__all__ = [
    "DuplicateGroup",
    "MergeOutcome",
    "find_duplicate_groups",
    "merge_group",
    "normalize_email",
    "normalize_name",
    "normalize_phone",
]

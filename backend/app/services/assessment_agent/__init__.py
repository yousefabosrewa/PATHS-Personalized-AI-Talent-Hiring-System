"""PATHS Assessment Agent (fix5.md).

Generates job-level assessment drafts using the existing OpenRouter
abstraction. Returns structured JSON the recruiter can review, edit,
and approve before any candidate sees it.

Public API:

    generate_assessment_draft(db, *, job, assessment_type, ...) -> dict
"""

from .service import (
    ASSESSMENT_TYPES,
    AssessmentType,
    generate_assessment_draft,
)

__all__ = [
    "ASSESSMENT_TYPES",
    "AssessmentType",
    "generate_assessment_draft",
]

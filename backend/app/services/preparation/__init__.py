"""
PATHS Preparation Agent (fix3.md §5–§6).

Helps a recruiter prepare for an interview by generating four structured
artifacts from an *anonymized* candidate + job context:

  * pre_analysis        — strengths / gaps / risks / interview strategy
  * technical_questions — role-specific tech questions with rubric
  * hr_questions        — structured behavioural questions
  * assessment          — practical task / work-sample idea

The agent input never contains the candidate's real name, email, phone, or
direct profile links unless the caller has already obtained a de-anon
approval AND explicitly requests an identity-aware run (currently we
always anonymize — see :pyfunc:`build_anonymized_context`).
"""

from .service import (
    PreparationOutputType,
    build_anonymized_context,
    generate_preparation,
    get_preparation_drafts,
    save_preparation_draft,
)

__all__ = [
    "PreparationOutputType",
    "build_anonymized_context",
    "generate_preparation",
    "get_preparation_drafts",
    "save_preparation_draft",
]

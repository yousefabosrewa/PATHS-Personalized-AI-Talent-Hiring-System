"""
PATHS Backend — Per-skill evidence collection (MCP-style tools).

Per the brief "use MCPs for each so the agent can check the evidence
to give each skill a score", this module exposes three evidence tools:

  * ``CVEvidenceTool``       — reads from the candidate's persisted CV
                               (Candidate, CandidateExperience, CandidateSkill,
                               CandidateSource raw blobs).
  * ``GithubEvidenceTool``   — calls the public GitHub REST API for the
                               candidate's profile, repos, languages, and
                               READMEs.
  * ``LinkedinEvidenceTool`` — best-effort public-profile fetch (LinkedIn
                               has no open API). Honours
                               ``LINKEDIN_MCP_SERVER_URL`` if set, so
                               operators with a real LinkedIn MCP server
                               can swap it in without code changes.

Each tool returns a uniform :class:`EvidenceResult` so the aggregator can
treat them as one of N pluggable sources.

The agent layer (:mod:`app.services.skill_evidence.service`) calls each
tool, hands the snippets to an LLM scorer, and produces a per-skill
0-100 aggregate that's persisted into ``evidence_items`` +
``candidate_skills.proficiency_score``.
"""

from app.services.skill_evidence.types import EvidenceResult, EvidenceSnippet
from app.services.skill_evidence.cv_tool import CVEvidenceTool
from app.services.skill_evidence.github_tool import GithubEvidenceTool
from app.services.skill_evidence.linkedin_tool import LinkedinEvidenceTool

__all__ = [
    "CVEvidenceTool",
    "EvidenceResult",
    "EvidenceSnippet",
    "GithubEvidenceTool",
    "LinkedinEvidenceTool",
]

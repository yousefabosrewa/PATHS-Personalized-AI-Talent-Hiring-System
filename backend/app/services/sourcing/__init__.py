"""
PATHS Backend — Open-to-Work Candidate Sourcing module.

Mirrors the architecture of `app/services/job_scraper`:

  providers/   pluggable sources (mock, linkedin, openresume, ...)
  normalizers/ raw-profile -> canonical NormalizedSourcedCandidate
  matchers/    sourced-candidate ranking against an org job
  agents/      Llama reasoning explanation (OpenRouter)

The module is **disabled by default** (CANDIDATE_SOURCING_ENABLED=false)
and never modifies the database schema. Existing flexible fields are
reused:
  Candidate.headline / summary / open_to_job_types / desired_*
  CandidateSource (source, url, raw_blob_uri)
  EvidenceItem.meta_json (per-source structured data)
  CandidateJobMatch (overall_score / explanation / evidence)
"""

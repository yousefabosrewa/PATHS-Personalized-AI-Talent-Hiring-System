"""PATHS — Candidate-side Job Description Analysis (fix8&9 Update 1).

The candidate pastes (or uploads) a job description; the agent compares
it against the candidate's own profile / skills / experience and returns
a structured, candidate-focused result (fit score, matching/missing
skills, alignment paragraphs, improvement + interview-prep + learning
recommendations).

The agent never hits the recruiter side; this is purely a self-service
tool for candidates.
"""

from .service import analyze_job_description_for_candidate

__all__ = ["analyze_job_description_for_candidate"]

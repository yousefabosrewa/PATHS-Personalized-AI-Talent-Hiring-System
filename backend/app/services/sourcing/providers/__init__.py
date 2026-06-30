"""Candidate sourcing providers (compliant, public/authorized data only)."""

from app.services.sourcing.providers.base_candidate_provider import (
    BaseCandidateProvider,
    RawSourcedCandidate,
    SourcingRunResult,
)
from app.services.sourcing.providers.linkedin_open_to_work_provider import (
    LinkedInOpenToWorkProvider,
)
from app.services.sourcing.providers.mock_open_to_work_provider import (
    MockOpenToWorkProvider,
)


__all__ = [
    "BaseCandidateProvider",
    "RawSourcedCandidate",
    "SourcingRunResult",
    "LinkedInOpenToWorkProvider",
    "MockOpenToWorkProvider",
]


def get_provider(name: str) -> BaseCandidateProvider:
    """Factory — return a provider by canonical name.

    Always falls back to the mock provider when an unknown name is
    requested. The caller can opt in to the LinkedIn connector explicitly
    by setting ``CANDIDATE_SOURCING_PROVIDER=linkedin``; even then the
    connector is stub-by-default and only reads compliant data
    (public-export / approved API).
    """
    key = (name or "").strip().lower()
    if key == "linkedin":
        return LinkedInOpenToWorkProvider()
    return MockOpenToWorkProvider()

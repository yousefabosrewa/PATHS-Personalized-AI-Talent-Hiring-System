"""External candidate sourcing — recruiter Source Candidate flow (fix6.md)."""

from app.services.source_candidate.provider import (
    CandidateSourcingProvider,
    ExternalCandidatePayload,
    FetchOpenToWorkInput,
    SourcingProviderError,
)
from app.services.source_candidate.providers import get_sourcing_provider
from app.services.source_candidate.service import (
    SourceCandidateService,
    is_technical_role,
)

__all__ = [
    "CandidateSourcingProvider",
    "ExternalCandidatePayload",
    "FetchOpenToWorkInput",
    "SourceCandidateService",
    "SourcingProviderError",
    "get_sourcing_provider",
    "is_technical_role",
]

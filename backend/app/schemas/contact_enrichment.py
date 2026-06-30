from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EnrichedContactOut(BaseModel):
    id: UUID
    candidate_id: UUID
    organization_id: UUID
    contact_type: str
    original_value: str
    enriched_value: str | None = None
    confidence: float
    status: str
    source: str
    provenance: str | None = None
    validated_at: datetime | None = None
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class EnrichmentStatusOut(BaseModel):
    total: int = 0
    pending: int = 0
    approved: int = 0
    rejected: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)


class ContactApprovalBody(BaseModel):
    reviewer_name: str | None = None

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DuplicateSuggestionOut(BaseModel):
    id: str
    candidate_id_a: str
    candidate_id_b: str
    organization_id: str
    match_reason: str
    match_value: str
    confidence: float
    status: str
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    notes: str | None = None
    merged_into_candidate_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DuplicateListOut(BaseModel):
    organization_id: str
    total: int
    items: list[DuplicateSuggestionOut]


class MergeReviewBody(BaseModel):
    notes: str | None = Field(None, description="Reviewer notes")


class MergeHistoryOut(BaseModel):
    id: str
    organization_id: str
    kept_candidate_id: str
    removed_candidate_id: str
    merged_by: str
    merged_at: datetime | None = None
    merge_reason: str | None = None
    audit_log: dict | None = None
    created_at: datetime | None = None


class MergeHistoryListOut(BaseModel):
    organization_id: str
    total: int
    items: list[MergeHistoryOut]

"""PATHS Backend — HITL approval schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class HITLApprovalOut(BaseModel):
    id: UUID
    organization_id: UUID
    action_type: str
    status: str
    priority: str
    entity_type: str
    entity_id: str
    entity_label: str
    requested_by_name: str
    requested_at: datetime
    reviewed_by_name: str | None = None
    reviewed_at: datetime | None = None
    decision: str | None = None
    reason: str | None = None
    expires_at: datetime | None = None
    meta_json: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class HITLDecideRequest(BaseModel):
    decision: str  # "approved" | "rejected"
    reason: str | None = None


class HITLCreateRequest(BaseModel):
    action_type: str
    entity_type: str
    entity_id: str
    entity_label: str
    priority: str = "medium"
    expires_at: datetime | None = None
    meta_json: dict[str, Any] | None = None

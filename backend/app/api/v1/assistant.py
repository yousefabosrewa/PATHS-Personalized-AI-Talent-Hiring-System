"""
PATHS Backend — In-app context-aware assistant (support chatbot) endpoints.

The floating widget sends the page context (``context_key`` + optional
``entity_id``) with each message. Memory is per (user, context_key, entity_id),
so every page/section/record keeps its own conversation thread.

Routes (mounted under /api/v1):
  POST   /assistant/chat              send a message, get a grounded reply
  GET    /assistant/history           load this context's thread
  DELETE /assistant/history           clear this context's thread
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import OrgContext, get_current_hiring_org_context
from app.services.assistant import service as assistant_service

router = APIRouter(prefix="/assistant", tags=["Assistant"])


class ChatRequest(BaseModel):
    context_key: str = Field(default="general", max_length=64)
    entity_id: str | None = Field(default=None, max_length=64)
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    reply: str
    context_key: str
    entity_id: str | None = None


class AssistantMessageOut(BaseModel):
    role: str
    content: str
    created_at: str | None = None


class HistoryResponse(BaseModel):
    context_key: str
    entity_id: str | None = None
    items: list[AssistantMessageOut]


@router.post("/chat", response_model=ChatResponse)
def post_chat(
    body: ChatRequest,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
) -> ChatResponse:
    reply = assistant_service.chat(
        db,
        organization_id=ctx.organization_id,
        user_id=ctx.user.id,
        context_key=body.context_key,
        entity_id=body.entity_id or "",
        message=body.message,
    )
    return ChatResponse(
        reply=reply,
        context_key=(body.context_key or "general").strip().lower(),
        entity_id=body.entity_id or None,
    )


@router.get("/history", response_model=HistoryResponse)
def get_history(
    context_key: str = Query("general", max_length=64),
    entity_id: str | None = Query(None, max_length=64),
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
) -> HistoryResponse:
    rows = assistant_service.load_history(
        db,
        user_id=ctx.user.id,
        context_key=(context_key or "general").strip().lower(),
        entity_id=entity_id or "",
        limit=50,
    )
    return HistoryResponse(
        context_key=(context_key or "general").strip().lower(),
        entity_id=entity_id or None,
        items=[
            AssistantMessageOut(
                role=m.role,
                content=m.content,
                created_at=m.created_at.isoformat() if m.created_at else None,
            )
            for m in rows
        ],
    )


@router.delete("/history", status_code=status.HTTP_204_NO_CONTENT)
def delete_history(
    context_key: str = Query("general", max_length=64),
    entity_id: str | None = Query(None, max_length=64),
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
) -> None:
    assistant_service.clear_history(
        db,
        user_id=ctx.user.id,
        context_key=(context_key or "general").strip().lower(),
        entity_id=entity_id or "",
    )
    return None

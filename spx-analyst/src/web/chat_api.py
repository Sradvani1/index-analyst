"""FastAPI routes for the research assistant chat API."""

from __future__ import annotations

import json
from typing import Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..chat_service import ChatServiceError, SessionNotFoundError, get_chat_service
from ..chat_sessions import get_session
from ..openai_assistant import ThreadMessage
from ..schemas import ChatSessionRecord
from .models import (
    ChatMessageResponse,
    ChatSessionResponse,
    CreateChatSessionRequest,
    PostChatMessageRequest,
    RenameChatSessionRequest,
)

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _session_response(record: ChatSessionRecord) -> ChatSessionResponse:
    return ChatSessionResponse(
        id=record.id,
        title=record.title,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _message_response(message: ThreadMessage) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=message.id,
        role=message.role,  # type: ignore[arg-type]
        content=message.content,
        created_at=message.created_at,
    )


@router.get("/sessions", response_model=list[ChatSessionResponse])
def list_chat_sessions() -> list[ChatSessionResponse]:
    service = get_chat_service()
    return [_session_response(s) for s in service.list_sessions()]


@router.post("/sessions", response_model=ChatSessionResponse, status_code=201)
def create_chat_session(body: CreateChatSessionRequest) -> ChatSessionResponse:
    service = get_chat_service()
    try:
        record = service.create_session(title=body.title)
    except ChatServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _session_response(record)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
def get_chat_messages(session_id: str) -> list[ChatMessageResponse]:
    service = get_chat_service()
    try:
        messages = service.get_messages(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ChatServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [_message_response(m) for m in messages]


@router.patch("/sessions/{session_id}", response_model=ChatSessionResponse)
def rename_chat_session(session_id: str, body: RenameChatSessionRequest) -> ChatSessionResponse:
    service = get_chat_service()
    try:
        record = service.rename_session(session_id, body.title)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ChatServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _session_response(record)


@router.delete("/sessions/{session_id}", status_code=204)
def delete_chat_session(session_id: str) -> None:
    service = get_chat_service()
    try:
        service.delete_session(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/messages")
def post_chat_message(session_id: str, body: PostChatMessageRequest) -> StreamingResponse:
    service = get_chat_service()
    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="message must not be empty")

    try:
        get_session(session_id, service.settings)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    def event_stream() -> Iterator[str]:
        try:
            for chunk in service.stream_reply(session_id, content):
                payload = json.dumps({"text": chunk}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
            yield "data: [DONE]\n\n"
        except ChatServiceError as exc:
            payload = json.dumps({"error": str(exc)}, ensure_ascii=False)
            yield f"data: {payload}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def clear_chat_service_cache() -> None:
    """Test helper — reset cached ChatService singleton."""
    get_chat_service.cache_clear()

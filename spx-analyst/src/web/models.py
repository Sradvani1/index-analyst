"""API view-models for the Phase 2 web viewer."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..schemas import DailyState, SignalAlignment


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str


class RunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    spx_close: float
    structural_bias: str
    posture_lead: str
    valuation_bucket: str
    recommended_action: str
    signal_alignment: SignalAlignment


class RunDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    report_markdown: str
    daily_state: DailyState


class ChatSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    created_at: str
    updated_at: str


class CreateChatSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = "New conversation"


class RenameChatSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1)


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: int | None = None


class PostChatMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(..., min_length=1)

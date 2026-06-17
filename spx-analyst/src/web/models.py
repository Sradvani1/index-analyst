"""API view-models for the Phase 2 web viewer."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ..schemas import DailyState, SignalAlignment


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str


class RunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    spx_close: float
    structural_bias: str
    trend_regime: str
    valuation_bucket: str
    recommended_action: str
    signal_alignment: SignalAlignment


class RunDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    report_markdown: str
    daily_state: DailyState

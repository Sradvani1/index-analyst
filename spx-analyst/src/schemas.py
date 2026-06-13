"""Pydantic models for every file contract in the engine.

These schemas are the source of truth for manifests, external context, daily
state, validation reports, and the future chat-session contract. Keep them
stable: Phase 2 reuses them without migration.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# --- Input contracts ---------------------------------------------------------


class ChartEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: int = Field(..., ge=1, description="1-based position in the chart pack.")
    file: str = Field(..., description="Filename within the run's charts/ folder.")
    label: str = Field(..., description="Concise description of the chart.")
    category: str = Field(..., description="e.g. technical, sentiment, macro.")
    timeframe: Optional[str] = None


class DailyManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    index_symbol: str
    instrument_symbol: str
    close: float
    chart_count: int
    charts: List[ChartEntry]

    @model_validator(mode="after")
    def _check_charts(self) -> "DailyManifest":
        if not self.charts:
            raise ValueError("manifest must list at least one chart")
        orders = [c.order for c in self.charts]
        if len(set(orders)) != len(orders):
            raise ValueError(f"chart 'order' values must be unique, got {orders}")
        expected = list(range(1, len(orders) + 1))
        if sorted(orders) != expected:
            raise ValueError(
                f"chart 'order' values must be contiguous starting at 1, got {sorted(orders)}"
            )
        if self.chart_count != len(self.charts):
            raise ValueError(
                f"chart_count ({self.chart_count}) does not match number of charts ({len(self.charts)})"
            )
        return self

    def ordered_charts(self) -> List[ChartEntry]:
        return sorted(self.charts, key=lambda c: c.order)


class MetricReading(BaseModel):
    """A single indicator expressed as a numeric value plus its zone reading."""

    model_config = ConfigDict(extra="forbid")

    value: Optional[float] = None
    reading: Optional[str] = None


class FearGreedComponents(BaseModel):
    """The seven CNN Fear & Greed sub-indicators, each as value + reading.

    Notable underlying values: market_volatility is the VIX, put_call_options is
    the 5-day put/call ratio, junk_bond_demand is the high-yield vs investment
    grade spread (percent).
    """

    model_config = ConfigDict(extra="forbid")

    market_momentum: MetricReading = Field(default_factory=MetricReading)
    stock_price_strength: MetricReading = Field(default_factory=MetricReading)
    stock_price_breadth: MetricReading = Field(default_factory=MetricReading)
    put_call_options: MetricReading = Field(default_factory=MetricReading)
    market_volatility: MetricReading = Field(default_factory=MetricReading)
    safe_haven_demand: MetricReading = Field(default_factory=MetricReading)
    junk_bond_demand: MetricReading = Field(default_factory=MetricReading)


class ExternalContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    us10y: Optional[float] = None
    forward_eps: Optional[float] = None
    fear_greed_index: MetricReading = Field(default_factory=MetricReading)
    fear_greed_components: FearGreedComponents = Field(default_factory=FearGreedComponents)


# --- Output contracts --------------------------------------------------------


class DecisionMatrix(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valuation: str
    technicals: str
    sentiment: str
    risk: str
    recommended_action: str


class SignalSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pct_vs_50dma: Optional[float] = None
    pct_vs_200dma: Optional[float] = None
    bollinger_position: Optional[str] = None
    rsi14: Optional[float] = None
    mfi: Optional[float] = None
    vix: Optional[float] = None
    vix_regime: Optional[str] = None
    fear_greed: Optional[int] = None
    fear_greed_zone: Optional[str] = None
    put_call: Optional[float] = None
    high_yield_spread: Optional[float] = None
    monte_carlo_probability: Optional[float] = None


class DailyState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    framework_version: str
    spx_close: float
    schk_close: Optional[float] = None
    base_case: str
    trend_regime: str
    valuation_bucket: str
    signals: SignalSet
    what_changed_today: List[str]
    narrative_summary: str
    open_questions: List[str]
    decision_matrix: DecisionMatrix

    @field_validator("narrative_summary")
    @classmethod
    def _normalize_narrative(cls, v: str) -> str:
        # Collapse stray literal "\n" escapes and real newlines into a single
        # clean paragraph so the compact summary stays compact and renders well.
        return " ".join(v.replace("\\n", " ").replace("\n", " ").replace("\\r", " ").split())


# --- Validation contract -----------------------------------------------------


Severity = Literal["error", "warning"]


class ValidationIssue(BaseModel):
    severity: Severity
    code: str
    message: str


class ValidationReport(BaseModel):
    date: str
    target: str
    passed: bool
    issues: List[ValidationIssue] = Field(default_factory=list)

    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]


# --- Phase 2 (future-ready) --------------------------------------------------


class ChatSessionContext(BaseModel):
    """Retrieval contract for the future Phase 2 conversational layer.

    Loaded read-only from canonical artifacts; never mutates daily-state memory.
    """

    date: str
    report_markdown: str
    daily_state: DailyState
    recent_states: List[DailyState] = Field(default_factory=list)
    recent_summary: Optional[str] = None

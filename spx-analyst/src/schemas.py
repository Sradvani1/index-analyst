"""Pydantic models for every file contract in the engine."""

from __future__ import annotations

import datetime as dt
from typing import Dict, List, Literal, Optional

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
    index_symbol: str = "SPX"
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


class EpsHistoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    effective_from: str
    forward_eps: float = Field(..., gt=0)
    trailing_eps: float = Field(..., gt=0)
    notes: Optional[str] = None

    @field_validator("effective_from")
    @classmethod
    def _validate_effective_from(cls, v: str) -> str:
        dt.date.fromisoformat(v)
        return v


class EpsHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: List[EpsHistoryEntry] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _check_unique_effective_from(self) -> "EpsHistory":
        dates = [e.effective_from for e in self.entries]
        if len(set(dates)) != len(dates):
            raise ValueError(f"duplicate effective_from values in EPS history: {dates}")
        return self


class ResolvedEps(BaseModel):
    """In-memory EPS carrier resolved from master history (not a run-dir artifact)."""

    model_config = ConfigDict(extra="forbid")

    forward_eps: float
    trailing_eps: float
    effective_from: str
    source: Literal["master"] = "master"


# --- Precompute contract (analysis_context.json) -----------------------------


class MarketDataContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spx_close: float
    vix: float
    us10y: float
    as_of_date: str
    pct_above_200dma: float
    realized_vol_20d: float
    sma_50: float
    sma_200: float
    precompute_warnings: List[str] = Field(default_factory=list)


ERPTrend = Literal["expanding", "stable", "contracting"]
RallyExhaustionScore = Literal["Low", "Moderate", "High"]
UpsideTargetRule = Literal["active_swing_high", "next_local_max", "pct_extension"]
DownsideTargetRule = Literal[
    "fib_382",
    "fib_500",
    "first_liquidation_zone",
    "reanchor_liquidation",
    "reanchor_erp_floor",
    "reanchor_sma200",
    "reanchor_margin_call",
    "reanchor_fallback_pct",
]
SwingConfirmation = Literal["pullback_3pct", "five_sessions", "rally_5pct", "above_50dma"]


class ValuationContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    forward_pe: Optional[float] = None
    trailing_pe: Optional[float] = None
    forward_earnings_yield: Optional[float] = None
    erp: Optional[float] = None
    erp_trend: Optional[ERPTrend] = None
    erp_reentry_floor_at_0_5pct: Optional[float] = None


class StructureContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_swing_high_date: str
    active_swing_high_price: float
    swing_high_confirmation: SwingConfirmation
    active_swing_low_date: str
    active_swing_low_price: float
    swing_low_confirmation: SwingConfirmation
    fib_236: float
    fib_382: float
    fib_500: float
    fib_618: float
    liquidation_caution: float
    liquidation_nervous: float
    liquidation_margin_call: float
    liquidation_cascade: float
    upside_target: float
    upside_target_rule: UpsideTargetRule
    downside_target: float
    downside_target_rule: DownsideTargetRule


class ThresholdEvaluationRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adjusted_prob_up_first: float = Field(..., ge=0.0, le=1.0)
    actionable: bool


class MonteCarloContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sigma: float
    mu: float
    rally_exhaustion_score: RallyExhaustionScore
    exhaustion_discount: float
    upside_target: float
    downside_target: float
    upside_target_rule: UpsideTargetRule
    downside_target_rule: DownsideTargetRule
    prob_up_first_raw: float = Field(..., ge=0.0, le=1.0)
    prob_down_first_raw: float = Field(..., ge=0.0, le=1.0)
    prob_up_first_adjusted: float = Field(..., ge=0.0, le=1.0)
    prob_down_first_adjusted: float = Field(..., ge=0.0, le=1.0)
    cascades: str
    median_days: str
    drift_path: str
    cash_drag_prob: float = Field(..., ge=0.0, le=1.0)
    threshold_evaluation: Dict[str, ThresholdEvaluationRow]


class AnalysisContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    market_data: MarketDataContext
    valuation: ValuationContext
    structure: StructureContext
    monte_carlo: MonteCarloContext


# --- Output contracts --------------------------------------------------------


class DecisionMatrixRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_layer: str
    current_reading: str
    signal: str


class DecisionMatrix(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows: List[DecisionMatrixRow]

    @property
    def recommended_action(self) -> str:
        for row in self.rows:
            if row.signal_layer.strip().lower() == "recommended action":
                return row.signal or row.current_reading
        if self.rows:
            return self.rows[-1].signal or self.rows[-1].current_reading
        return "hold_and_monitor"


class SignalSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pct_vs_50dma: Optional[float] = None
    pct_vs_200dma: Optional[float] = None
    bollinger_position: Optional[str] = None
    rsi14: Optional[float] = None
    mfi: Optional[float] = None
    vix_regime: Optional[str] = Field(
        default=None,
        description=(
            "Single string: VIX zone label plus level and moving-average context. "
            "Do not add vix_regime_detail or signals.vix."
        ),
    )
    fear_greed: Optional[int] = None
    fear_greed_zone: Optional[str] = Field(
        default=None,
        description="Fear & Greed zone label; the only allowed score+label pair with fear_greed.",
    )
    put_call: Optional[float] = Field(
        default=None,
        description="Numeric put/call ratio only; no put_call_zone or zone label field.",
    )
    high_yield_spread: Optional[float] = None
    intraday_close_position: Optional[str] = None
    middle_band_regime: Optional[str] = None


SignalAlignmentOverall = Literal["aligned_trim", "aligned_buy", "mixed", "neutral"]
EffectiveThreshold = Literal[65, 70, 75]
DivergenceWeight = Literal["high", "medium", "low"]
StructuralBias = Literal[
    "Early Bull",
    "Mid Bull",
    "Late Bull / Topping",
    "Bear Market",
]


class SignalAlignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trim_signals_met: int = Field(..., ge=0, le=5)
    buy_signals_met: int = Field(..., ge=0, le=5)
    overall: SignalAlignmentOverall


class Divergence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    layers: List[str]
    bullish_read: str
    bearish_read: str
    framework_rule: str
    weight: DivergenceWeight
    chart_refs: List[str]


class MonteCarloDetail(BaseModel):
    """Pass 1 selection from precomputed analysis_context.monte_carlo."""

    model_config = ConfigDict(extra="forbid")

    effective_threshold: EffectiveThreshold
    meets_threshold: bool
    prob_up_first_raw: float = Field(..., ge=0.0, le=1.0)
    prob_down_first_raw: float = Field(..., ge=0.0, le=1.0)
    prob_up_first_adjusted: float = Field(..., ge=0.0, le=1.0)
    prob_down_first_adjusted: float = Field(..., ge=0.0, le=1.0)
    sigma: float
    mu: float
    upside_target: float
    downside_target: float
    rally_exhaustion_score: RallyExhaustionScore
    conditional_cascade: str
    median_days: str
    drift_path: str
    cash_drag_prob: float = Field(..., ge=0.0, le=1.0)


class DailyState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    framework_version: str
    spx_close: float
    structural_bias: StructuralBias
    base_case: str
    trend_regime: str
    valuation_bucket: str
    signals: SignalSet
    what_changed_today: List[str] = Field(
        description="Array of 3–5 change bullets; never a single string."
    )
    narrative_summary: str
    open_questions: List[str] = Field(
        description="Array of strings; never a single string."
    )
    decision_matrix: DecisionMatrix
    signal_alignment: SignalAlignment
    confirming_evidence: List[str]
    conflicting_evidence: List[Divergence]
    primary_tension: str
    monte_carlo: MonteCarloDetail

    @field_validator("narrative_summary")
    @classmethod
    def _normalize_narrative(cls, v: str) -> str:
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


# --- Chat preload (PR-15 compact contract) -------------------------------------


class CurrentBriefCaps:
    MAX_OPENING_CHARS = 220
    MAX_SETUP_TENSION_CHARS = 260
    MAX_RISK_BULLETS = 4
    MAX_RISK_BULLET_CHARS = 160
    MAX_MATRIX_ROWS = 6
    MAX_TREND_REGIME_CHARS = 240
    MAX_TRIGGER_BULLETS = 5
    MAX_TRIGGER_BULLET_CHARS = 100
    MAX_VIEW_CHANGE_BULLETS = 3
    MAX_VIEW_CHANGE_BULLET_CHARS = 110
    MAX_RENDERED_CHARS = 2100


class ArcBriefCaps:
    MAX_SESSIONS = 8
    MAX_TENSION_FRAGMENT_CHARS = 110
    MAX_STILL_OPEN_BULLETS = 3
    MAX_STILL_OPEN_BULLET_CHARS = 140
    MAX_INFLECTION_BULLETS = 3
    MAX_INFLECTION_BULLET_CHARS = 130
    MAX_RENDERED_CHARS = 1800


class ConstitutionCaps:
    MAX_RENDERED_CHARS = 2000


class ChatPreloadBudget:
    MAX_ADDITIONAL_INSTRUCTIONS_CHARS = 6500
    MAX_ADDITIONAL_INSTRUCTIONS_TOKENS = 1500


class CurrentBriefRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_layer: str
    signal: str


class CurrentBrief(BaseModel):
    """Authoritative present-tense slice from latest DailyState."""

    model_config = ConfigDict(extra="forbid")

    latest_run_date: str
    spx_close: float
    structural_bias: StructuralBias
    recommended_action: str
    overall_signal_balance: str
    opening_house_view: str
    setup_tension: str
    key_risks_or_tensions: List[str]
    key_trigger_levels: List[str]
    view_change_bullets: List[str]
    authoritative_rows: List[CurrentBriefRow]


class ArcBriefSessionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    bias: StructuralBias
    action: str
    tension_fragment: str


class ArcBrief(BaseModel):
    """Compressed multi-day continuity from rolling memory primitives."""

    model_config = ConfigDict(extra="forbid")

    regime_arc: str
    session_snapshots: List[ArcBriefSessionSnapshot]
    still_open_bullets: List[str]
    inflection_bullets: List[str]


class ChatPreloadContext(BaseModel):
    """Deterministic preload assembled for every Responses chat turn (compact contract)."""

    model_config = ConfigDict(extra="forbid")

    instructions: str
    current_brief: CurrentBrief
    arc_brief: ArcBrief
    additional_instructions: str


class ChatSessionRecord(BaseModel):
    """Local session index row — maps to an OpenAI conversation."""

    model_config = ConfigDict(extra="forbid")

    id: str
    openai_conversation_id: str
    title: str
    created_at: str
    updated_at: str


class ChatSessionIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sessions: List[ChatSessionRecord] = Field(default_factory=list)


# --- Phase 2 (future-ready) --------------------------------------------------


class ChatSessionContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    report_markdown: str
    daily_state: DailyState
    recent_states: List[DailyState] = Field(default_factory=list)
    recent_summary: Optional[str] = None

/** TypeScript mirror of the Layer 1 FastAPI view-models and DailyState schema. */

export type SignalAlignmentOverall =
  | "aligned_trim"
  | "aligned_buy"
  | "mixed"
  | "neutral";

export interface SignalAlignment {
  trim_signals_met: number;
  buy_signals_met: number;
  overall: SignalAlignmentOverall;
}

export interface RunSummary {
  date: string;
  spx_close: number;
  trend_regime: string;
  valuation_bucket: string;
  recommended_action: string;
  signal_alignment: SignalAlignment;
}

export interface MetricReading {
  value?: number | null;
  reading?: string | null;
}

export interface SignalSet {
  pct_vs_50dma?: number | null;
  pct_vs_200dma?: number | null;
  bollinger_position?: string | null;
  rsi14?: number | null;
  mfi?: number | null;
  vix?: number | null;
  vix_regime?: string | null;
  fear_greed?: number | null;
  fear_greed_zone?: string | null;
  put_call?: number | null;
  high_yield_spread?: number | null;
  monte_carlo_probability?: number | null;
}

export interface DecisionMatrix {
  valuation: string;
  technicals: string;
  sentiment: string;
  risk: string;
  recommended_action: string;
}

export interface Divergence {
  id: string;
  layers: string[];
  bullish_read: string;
  bearish_read: string;
  framework_rule: string;
  weight: "high" | "medium" | "low";
  chart_refs: string[];
}

export interface MonteCarloDetail {
  prob_up_first: number;
  prob_down_first: number;
  conditional_cascade: string;
  median_days: string;
  cash_drag_prob: number;
  meets_threshold: boolean;
}

export interface DailyState {
  date: string;
  framework_version: string;
  spx_close: number;
  schk_close?: number | null;
  base_case: string;
  trend_regime: string;
  valuation_bucket: string;
  signals: SignalSet;
  what_changed_today: string[];
  narrative_summary: string;
  open_questions: string[];
  decision_matrix: DecisionMatrix;
  signal_alignment: SignalAlignment;
  confirming_evidence: string[];
  conflicting_evidence: Divergence[];
  primary_tension: string;
  monte_carlo: MonteCarloDetail;
}

export interface RunDetail {
  date: string;
  report_markdown: string;
  daily_state: DailyState;
}

export interface HealthResponse {
  status: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** TypeScript mirror of the FastAPI view-models and DailyState schema. */

export type SignalAlignmentOverall =
  | "aligned_trim"
  | "aligned_buy"
  | "mixed"
  | "neutral";

export type StructuralBias =
  | "Early Bull"
  | "Mid Bull"
  | "Late Bull / Topping"
  | "Bear Market";

export interface SignalAlignment {
  trim_signals_met: number;
  buy_signals_met: number;
  overall: SignalAlignmentOverall;
}

export interface RunSummary {
  date: string;
  spx_close: number;
  structural_bias?: StructuralBias;
  trend_regime: string;
  valuation_bucket: string;
  recommended_action: string;
  signal_alignment: SignalAlignment;
}

export interface SignalSet {
  pct_vs_50dma?: number | null;
  pct_vs_200dma?: number | null;
  bollinger_position?: string | null;
  rsi14?: number | null;
  mfi?: number | null;
  vix_regime?: string | null;
  fear_greed?: number | null;
  fear_greed_zone?: string | null;
  put_call?: number | null;
  high_yield_spread?: number | null;
  intraday_close_position?: string | null;
  middle_band_regime?: string | null;
}

export interface DecisionMatrixRow {
  signal_layer: string;
  current_reading: string;
  signal: string;
}

export interface DecisionMatrix {
  rows: DecisionMatrixRow[];
}

export function getRecommendedAction(matrix: DecisionMatrix): string {
  const action = matrix.rows.find((r) =>
    r.signal_layer.trim().toLowerCase() === "recommended action",
  );
  if (action) {
    return action.signal || action.current_reading;
  }
  const last = matrix.rows[matrix.rows.length - 1];
  return last?.signal || last?.current_reading || "hold_and_monitor";
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
  effective_threshold: 65 | 70 | 75;
  meets_threshold: boolean;
  prob_up_first_raw: number;
  prob_down_first_raw: number;
  prob_up_first_adjusted: number;
  prob_down_first_adjusted: number;
  sigma: number;
  mu: number;
  upside_target: number;
  downside_target: number;
  rally_exhaustion_score: "Low" | "Moderate" | "High";
  conditional_cascade: string;
  median_days: string;
  drift_path: string;
  cash_drag_prob: number;
}

export interface DailyState {
  date: string;
  framework_version: string;
  spx_close: number;
  structural_bias: StructuralBias;
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

export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: number | null;
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

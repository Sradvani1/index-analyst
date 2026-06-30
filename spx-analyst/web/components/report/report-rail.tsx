import { SignalGrid } from "@/components/signal-grid";
import { DecisionMatrix } from "@/components/decision-matrix";
import { TruncatedFact } from "@/components/report/truncated-fact";
import { formatPercent } from "@/lib/format";
import { TONE_SURFACE } from "@/lib/report";
import { cn } from "@/lib/utils";
import type { DailyState } from "@/lib/types";

interface ReportRailProps {
  state: DailyState;
}

export function ReportRail({ state }: ReportRailProps) {
  return (
    <aside className="flex flex-col gap-4 lg:sticky lg:top-[calc(4rem+1rem)] lg:max-h-[calc(100vh-5rem)] lg:overflow-y-auto">
      <TodaysStateModule state={state} />
      <SignalSnapshotModule state={state} />
      <MatrixSnapshotModule state={state} />
      <MonteCarloSummaryModule state={state} />
    </aside>
  );
}

function RailModule({
  title,
  children,
  className,
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "rounded-[14px] border border-border-soft bg-surface-0 p-4 shadow-editorial-1",
        className,
      )}
    >
      <h3 className="text-xs font-medium uppercase tracking-wide text-ink-500">
        {title}
      </h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function TodaysStateModule({ state }: { state: DailyState }) {
  return (
    <RailModule title="Today's state">
      <div className="grid gap-3">
        <TruncatedFact label="Structural bias" value={state.structural_bias} />
        <TruncatedFact label="Trend regime" value={state.trend_regime} />
        <TruncatedFact label="Valuation bucket" value={state.valuation_bucket} />
      </div>
      <p className="mt-4 text-sm leading-relaxed text-ink-700">{state.primary_tension}</p>
    </RailModule>
  );
}

function SignalSnapshotModule({ state }: { state: DailyState }) {
  return (
    <RailModule title="Signal snapshot">
      <SignalGrid state={state} compact />
    </RailModule>
  );
}

function MatrixSnapshotModule({ state }: { state: DailyState }) {
  return (
    <RailModule title="Decision matrix">
      <DecisionMatrix matrix={state.decision_matrix} />
    </RailModule>
  );
}

function MonteCarloSummaryModule({ state }: { state: DailyState }) {
  const mc = state.monte_carlo;
  const upTone = mc.meets_threshold ? "bull" : "caution";

  return (
    <RailModule title="Monte Carlo">
      <div className="grid gap-2">
        <MetricRow label="Upside target" value={mc.upside_target.toLocaleString()} />
        <MetricRow label="Downside target" value={mc.downside_target.toLocaleString()} />
        <div
          className={cn(
            "rounded-lg p-3 ring-1 ring-inset",
            TONE_SURFACE[upTone],
          )}
        >
          <p className="text-[0.65rem] font-medium uppercase tracking-wide opacity-70">
            Prob up first (adj.)
          </p>
          <p className="mt-1 text-xl font-semibold tabular-nums">
            {formatPercent(mc.prob_up_first_adjusted)}
          </p>
          <p className="mt-1 text-[0.7rem] opacity-80">
            {mc.meets_threshold
              ? `Meets ${mc.effective_threshold}% threshold`
              : `Below ${mc.effective_threshold}% threshold`}
          </p>
        </div>
        <MetricRow
          label="Prob down first (adj.)"
          value={formatPercent(mc.prob_down_first_adjusted)}
        />
        <MetricRow label="Rally exhaustion" value={mc.rally_exhaustion_score} />
        <MetricRow label="Median days" value={mc.median_days} />
      </div>
    </RailModule>
  );
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2 text-sm">
      <span className="text-ink-500">{label}</span>
      <span className="font-medium tabular-nums text-ink-900">{value}</span>
    </div>
  );
}

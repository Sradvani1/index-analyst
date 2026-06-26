import { SignalGrid } from "@/components/signal-grid";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { formatClose, humanizeAction } from "@/lib/format";
import { TONE_SURFACE, parseHeader, toneFor } from "@/lib/report";
import { cn } from "@/lib/utils";
import { getRecommendedAction, type DailyState } from "@/lib/types";

interface RunHeaderProps {
  state: DailyState;
  reportMarkdown: string;
}

export function RunHeader({ state, reportMarkdown }: RunHeaderProps) {
  const header = parseHeader(reportMarkdown);
  const close = formatClose(state.spx_close);
  const actionTone = toneFor(getRecommendedAction(state.decision_matrix));

  return (
    <header className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-ink-500">
            {state.date}
            {header.instrument ? ` · ${header.instrument}` : ""}
          </p>
          <h1 className="mt-1 font-display text-3xl font-semibold tracking-tight text-ink-900 sm:text-4xl">
            SPX Daily Tactical Analysis
          </h1>
        </div>
        <div className="text-right">
          <div className="flex items-baseline justify-end gap-2">
            <span className="text-4xl font-bold tabular-nums tracking-tight text-ink-900">
              {close}
            </span>
            {header.changePct && (
              <span
                className={cn(
                  "text-sm font-semibold tabular-nums",
                  header.changeDirection === "down" ? "text-risk-red" : "text-market-green",
                )}
              >
                {header.change} ({header.changePct})
              </span>
            )}
          </div>
          <p className="text-xs text-ink-500">SPX close</p>
        </div>
      </div>

      <div className={cn("rounded-[14px] p-4 ring-1 ring-inset", TONE_SURFACE[actionTone])}>
        <p className="text-[0.65rem] font-medium uppercase tracking-wide opacity-70">
          Recommended action
        </p>
        <p className="mt-1 text-base font-semibold leading-snug">
          {humanizeAction(getRecommendedAction(state.decision_matrix))}
        </p>
        <p className="mt-2 text-sm leading-relaxed opacity-90">{state.primary_tension}</p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <TruncatedFact label="Structural bias" value={state.structural_bias} />
        <TruncatedFact label="Trend regime" value={state.trend_regime} />
        <TruncatedFact label="Valuation bucket" value={state.valuation_bucket} />
      </div>

      <SignalGrid state={state} />
    </header>
  );
}

function TruncatedFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border-soft bg-surface-0 p-3">
      <p className="text-[0.65rem] font-medium uppercase tracking-wide text-ink-500">
        {label}
      </p>
      <Tooltip>
        <TooltipTrigger
          render={
            <p className="mt-1 line-clamp-2 cursor-default text-sm leading-snug" />
          }
        >
          {value}
        </TooltipTrigger>
        <TooltipContent className="max-w-sm text-left">{value}</TooltipContent>
      </Tooltip>
    </div>
  );
}

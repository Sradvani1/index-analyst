import { SignalGrid } from "@/components/signal-grid";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { TONE_SURFACE, parseHeader, toneFor } from "@/lib/report";
import { getRecommendedAction, type DailyState } from "@/lib/types";

interface RunHeaderProps {
  state: DailyState;
  reportMarkdown: string;
}

function humanizeAction(action: string): string {
  return action.replaceAll("_", " ");
}

export function RunHeader({ state, reportMarkdown }: RunHeaderProps) {
  const header = parseHeader(reportMarkdown);
  const close = state.spx_close.toLocaleString(undefined, {
    maximumFractionDigits: 2,
  });
  const actionTone = toneFor(getRecommendedAction(state.decision_matrix));

  return (
    <header className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {state.date}
            {header.instrument ? ` · ${header.instrument}` : ""}
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">
            SPX Daily Tactical Analysis
          </h1>
        </div>
        <div className="text-right">
          <div className="flex items-baseline gap-2">
            <span className="text-4xl font-semibold tabular-nums tracking-tight">
              {close}
            </span>
            {header.changePct && (
              <span
                className={cn(
                  "text-sm font-semibold tabular-nums",
                  header.changeDirection === "down"
                    ? "text-rose-600 dark:text-rose-400"
                    : "text-emerald-600 dark:text-emerald-400",
                )}
              >
                {header.change} ({header.changePct})
              </span>
            )}
          </div>
          <p className="text-xs text-muted-foreground">SPX close</p>
        </div>
      </div>

      <div
        className={cn(
          "rounded-xl p-4 ring-1 ring-inset",
          TONE_SURFACE[actionTone],
        )}
      >
        <p className="text-[0.65rem] font-medium uppercase tracking-wide opacity-70">
          Recommended action
        </p>
        <p className="mt-1 text-base font-semibold leading-snug">
          {humanizeAction(getRecommendedAction(state.decision_matrix))}
        </p>
        <p className="mt-2 text-sm leading-relaxed opacity-90">
          {state.primary_tension}
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
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
    <div className="rounded-lg border p-3">
      <p className="text-[0.65rem] font-medium uppercase tracking-wide text-muted-foreground">
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

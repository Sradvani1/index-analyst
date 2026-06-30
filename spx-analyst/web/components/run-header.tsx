import { MetadataChipFromText } from "@/components/archive/metadata-chip";
import { formatClose, humanizeAction } from "@/lib/format";
import { parseHeader, toneFor } from "@/lib/report";
import { cn } from "@/lib/utils";
import { getRecommendedAction, type DailyState } from "@/lib/types";

interface RunHeaderProps {
  state: DailyState;
  reportMarkdown: string;
}

export function RunHeader({ state, reportMarkdown }: RunHeaderProps) {
  const header = parseHeader(reportMarkdown);
  const close = formatClose(state.spx_close);
  const action = getRecommendedAction(state.decision_matrix);

  return (
    <header className="flex flex-col gap-4">
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

      <div className="flex flex-wrap gap-2">
        {state.structural_bias && (
          <MetadataChipFromText text={state.structural_bias} />
        )}
        <MetadataChipFromText text={humanizeAction(action)} tone={toneFor(action)} />
      </div>
    </header>
  );
}

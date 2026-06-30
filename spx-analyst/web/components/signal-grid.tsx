import { cn } from "@/lib/utils";
import { TONE_SURFACE, type Tone, toneFor } from "@/lib/report";
import type { DailyState } from "@/lib/types";

interface SignalGridProps {
  state: DailyState;
  /** Narrow rail layout — 2-col grid instead of 6-col at lg */
  compact?: boolean;
}

interface Tile {
  label: string;
  value: string;
  hint?: string;
  tone: Tone;
}

function fmt(value: number | null | undefined, suffix = ""): string {
  if (value == null) {
    return "—";
  }
  return `${value}${suffix}`;
}

function pct(value: number | null | undefined): string {
  if (value == null) {
    return "—";
  }
  return `${Math.round(value * 100)}%`;
}

function buildTiles(state: DailyState): Tile[] {
  const { signals, monte_carlo: mc } = state;
  const tiles: Tile[] = [];

  tiles.push({
    label: "VIX regime",
    value: signals.vix_regime ?? "—",
    tone: signals.vix_regime ? toneFor(signals.vix_regime) : "neutral",
  });

  tiles.push({
    label: "Fear & Greed",
    value: fmt(signals.fear_greed),
    hint: signals.fear_greed_zone ?? undefined,
    tone: signals.fear_greed_zone ? toneFor(signals.fear_greed_zone) : "neutral",
  });

  tiles.push({ label: "RSI-14", value: fmt(signals.rsi14), tone: "neutral" });
  tiles.push({ label: "MFI", value: fmt(signals.mfi), tone: "neutral" });

  tiles.push({
    label: "Monte Carlo edge",
    value: pct(mc.prob_up_first_adjusted),
    hint: mc.meets_threshold
      ? `meets ${mc.effective_threshold}% threshold`
      : `below ${mc.effective_threshold}% threshold`,
    tone: mc.meets_threshold ? "bull" : "caution",
  });

  return tiles;
}

export function SignalGrid({ state, compact = false }: SignalGridProps) {
  const tiles = buildTiles(state);
  const { signal_alignment: alignment } = state;

  return (
    <div
      className={cn(
        "grid grid-cols-2 gap-2",
        compact ? "sm:grid-cols-2" : "sm:grid-cols-3 lg:grid-cols-6",
      )}
    >
      {tiles.map((tile) => (
        <div
          key={tile.label}
          className={cn(
            "flex flex-col gap-1 rounded-lg p-3 ring-1 ring-inset",
            TONE_SURFACE[tile.tone],
          )}
        >
          <span className="text-[0.65rem] font-medium uppercase tracking-wide opacity-70">
            {tile.label}
          </span>
          <span className="text-xl font-semibold tabular-nums leading-none">
            {tile.value}
          </span>
          {tile.hint && (
            <span className="truncate text-[0.7rem] opacity-70">{tile.hint}</span>
          )}
        </div>
      ))}

      <AlignmentTile
        buy={alignment.buy_signals_met}
        trim={alignment.trim_signals_met}
        overall={alignment.overall}
      />
    </div>
  );
}

function AlignmentTile({
  buy,
  trim,
  overall,
}: {
  buy: number;
  trim: number;
  overall: string;
}) {
  return (
    <div className="flex flex-col gap-1 rounded-lg bg-muted p-3 ring-1 ring-inset ring-border">
      <span className="text-[0.65rem] font-medium uppercase tracking-wide text-muted-foreground">
        3-of-5 Alignment
      </span>
      <div className="flex items-baseline gap-2 text-sm font-semibold tabular-nums">
        <span className="text-market-green">Buy {buy}</span>
        <span className="text-muted-foreground">/</span>
        <span className="text-risk-red">Trim {trim}</span>
      </div>
      <span className="text-[0.7rem] capitalize text-muted-foreground">
        {overall.replaceAll("_", " ")}
      </span>
    </div>
  );
}

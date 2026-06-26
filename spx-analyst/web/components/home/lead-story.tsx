import Link from "next/link";

import { MetadataChipFromText } from "@/components/archive/metadata-chip";
import { humanizeAction, formatClose, formatDateLong } from "@/lib/format";
import { toneFor } from "@/lib/report";
import type { RunSummary } from "@/lib/types";

interface LeadStoryProps {
  run: RunSummary;
}

export function LeadStory({ run }: LeadStoryProps) {
  const action = humanizeAction(run.recommended_action);

  return (
    <section className="rounded-[14px] border border-border-soft bg-surface-0 p-6 shadow-editorial-1 sm:p-8">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-500">Latest analysis</p>
      <h1 className="mt-2 font-display text-3xl font-semibold leading-tight text-ink-900 sm:text-4xl">
        {formatDateLong(run.date)}
      </h1>
      <p className="mt-3 text-4xl font-bold tabular-nums text-ink-900 sm:text-5xl">
        {formatClose(run.spx_close)}
        <span className="ml-2 text-base font-medium text-ink-500">SPX close</span>
      </p>

      <div className="mt-5 flex flex-wrap gap-2">
        {run.structural_bias && <MetadataChipFromText text={run.structural_bias} />}
        <MetadataChipFromText text={action} tone={toneFor(run.recommended_action)} />
        <MetadataChipFromText text={run.valuation_bucket} />
      </div>

      <p className="mt-4 max-w-2xl text-base leading-relaxed text-ink-700">{run.trend_regime}</p>

      <Link
        href={`/runs/${run.date}`}
        className="mt-6 inline-flex items-center rounded-[10px] bg-market-green px-[18px] py-3 text-sm font-semibold text-white transition-colors hover:bg-market-green-hover"
      >
        Read full report
      </Link>
    </section>
  );
}

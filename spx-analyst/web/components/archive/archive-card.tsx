import Link from "next/link";

import { MetadataChipFromText } from "@/components/archive/metadata-chip";
import { humanizeAction, formatClose, formatDateLong, runCardSummary } from "@/lib/format";
import { toneFor } from "@/lib/report";
import type { RunSummary } from "@/lib/types";

interface ArchiveCardProps {
  run: RunSummary;
  latest?: boolean;
}

export function ArchiveCard({ run, latest = false }: ArchiveCardProps) {
  const action = humanizeAction(run.recommended_action);

  return (
    <Link
      href={`/runs/${run.date}`}
      className="group flex flex-col gap-4 rounded-[14px] border border-border-soft bg-surface-0 p-5 shadow-editorial-1 transition-all hover:border-ink-500/30 hover:shadow-editorial-2"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-xs font-medium uppercase tracking-wide text-ink-500">
              {formatDateLong(run.date)}
            </p>
            {latest && (
              <span className="rounded-full bg-market-green/10 px-2 py-0.5 text-[0.65rem] font-semibold uppercase tracking-wide text-market-green">
                Latest
              </span>
            )}
          </div>
          <p className="mt-1 font-display text-lg font-semibold text-ink-900">{run.date}</p>
        </div>
        <p className="text-right text-2xl font-bold tabular-nums text-ink-900">
          {formatClose(run.spx_close)}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {run.structural_bias && (
          <MetadataChipFromText text={run.structural_bias} />
        )}
        <MetadataChipFromText text={action} tone={toneFor(run.recommended_action)} />
        <span className="ml-auto text-xs font-medium text-market-green transition-colors group-hover:text-market-green-hover">
          Read report →
        </span>
      </div>

      <p className="line-clamp-3 text-sm leading-relaxed text-ink-500">{runCardSummary(run)}</p>
    </Link>
  );
}

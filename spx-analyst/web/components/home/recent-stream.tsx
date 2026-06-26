import Link from "next/link";

import { MetadataChipFromText } from "@/components/archive/metadata-chip";
import { formatClose, formatDateLong } from "@/lib/format";
import type { RunSummary } from "@/lib/types";

interface RecentStreamProps {
  runs: RunSummary[];
}

export function RecentStream({ runs }: RecentStreamProps) {
  if (runs.length === 0) {
    return null;
  }

  return (
    <section>
      <h2 className="font-display text-2xl font-semibold text-ink-900">Recent reports</h2>
      <ul className="mt-4 divide-y divide-border-soft rounded-[14px] border border-border-soft bg-surface-0">
        {runs.map((run) => (
          <li key={run.date}>
            <Link
              href={`/runs/${run.date}`}
              className="flex flex-wrap items-center justify-between gap-3 px-4 py-4 transition-colors hover:bg-surface-1 sm:px-5"
            >
              <div>
                <p className="font-medium text-ink-900">{run.date}</p>
                <p className="text-sm text-ink-500">{formatDateLong(run.date)}</p>
              </div>
              <div className="flex items-center gap-3">
                {run.structural_bias && (
                  <MetadataChipFromText text={run.structural_bias} />
                )}
                <span className="text-lg font-semibold tabular-nums text-ink-900">
                  {formatClose(run.spx_close)}
                </span>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

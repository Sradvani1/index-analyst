import { ArchiveCard } from "@/components/archive/archive-card";
import type { RunSummary } from "@/lib/types";

interface ArchiveGridProps {
  runs: RunSummary[];
}

export function ArchiveGrid({ runs }: ArchiveGridProps) {
  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3">
      {runs.map((run) => (
        <ArchiveCard key={run.date} run={run} />
      ))}
    </div>
  );
}

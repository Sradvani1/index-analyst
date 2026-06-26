"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { ScrollArea } from "@/components/ui/scroll-area";
import { formatClose } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { RunSummary } from "@/lib/types";

interface RunListProps {
  runs: RunSummary[];
}

export function RunList({ runs }: RunListProps) {
  const pathname = usePathname();

  if (runs.length === 0) {
    return (
      <div className="px-4 py-6 text-sm text-ink-500">
        No archived runs in memory yet. Run the analysis engine first.
      </div>
    );
  }

  return (
    <ScrollArea className="h-[calc(100vh-4.5rem)]">
      <nav className="flex flex-col gap-1 p-2">
        {runs.map((run) => {
          const href = `/runs/${run.date}`;
          const active = pathname === href;

          return (
            <Link
              key={run.date}
              href={href}
              className={cn(
                "flex items-center justify-between gap-2 rounded-lg border px-3 py-2 transition-colors",
                active
                  ? "border-market-green/30 bg-surface-1"
                  : "border-transparent hover:border-border-soft hover:bg-paper-100",
              )}
            >
              <span className="font-medium text-ink-900">{run.date}</span>
              <span className="text-sm tabular-nums text-ink-500">
                {formatClose(run.spx_close)}
              </span>
            </Link>
          );
        })}
      </nav>
    </ScrollArea>
  );
}

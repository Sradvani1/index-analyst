"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import type { RunSummary } from "@/lib/types";

interface RunListProps {
  runs: RunSummary[];
}

export function RunList({ runs }: RunListProps) {
  const pathname = usePathname();

  if (runs.length === 0) {
    return (
      <div className="px-4 py-6 text-sm text-muted-foreground">
        No archived runs in memory yet. Run the analysis engine first.
      </div>
    );
  }

  return (
    <ScrollArea className="h-full">
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
                  ? "border-primary/30 bg-accent"
                  : "border-transparent hover:border-border hover:bg-muted/60",
              )}
            >
              <span className="font-medium">{run.date}</span>
              <span className="text-sm tabular-nums text-muted-foreground">
                {run.spx_close.toLocaleString(undefined, {
                  maximumFractionDigits: 2,
                })}
              </span>
            </Link>
          );
        })}
      </nav>
    </ScrollArea>
  );
}

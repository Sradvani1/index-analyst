"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import type { RunSummary } from "@/lib/types";

interface RunListProps {
  runs: RunSummary[];
}

function formatAction(action: string): string {
  return action.replaceAll("_", " ");
}

function alignmentVariant(
  overall: RunSummary["signal_alignment"]["overall"],
): "default" | "secondary" | "destructive" | "outline" {
  switch (overall) {
    case "aligned_buy":
      return "default";
    case "aligned_trim":
      return "destructive";
    case "mixed":
      return "secondary";
    default:
      return "outline";
  }
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
                "rounded-lg border px-3 py-2 transition-colors",
                active
                  ? "border-primary/30 bg-accent"
                  : "border-transparent hover:border-border hover:bg-muted/60",
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{run.date}</span>
                <span className="text-xs text-muted-foreground">
                  {run.spx_close.toLocaleString(undefined, {
                    maximumFractionDigits: 2,
                  })}
                </span>
              </div>
              <div className="mt-2 flex flex-wrap gap-1">
                <Badge variant={alignmentVariant(run.signal_alignment.overall)}>
                  {run.signal_alignment.overall.replaceAll("_", " ")}
                </Badge>
              </div>
              <p className="mt-2 line-clamp-2 text-xs text-muted-foreground">
                {formatAction(run.recommended_action)}
              </p>
            </Link>
          );
        })}
      </nav>
    </ScrollArea>
  );
}

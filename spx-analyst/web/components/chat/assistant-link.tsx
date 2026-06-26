"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

export function AssistantLink({ className }: { className?: string }) {
  const pathname = usePathname();
  const active = pathname === "/assistant" || pathname.startsWith("/assistant/");

  return (
    <Link
      href="/assistant"
      aria-current={active ? "page" : undefined}
      className={cn(
        "rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors",
        active
          ? "border-market-green bg-market-green/5 text-market-green"
          : "border-border-soft bg-surface-0 text-ink-700 hover:border-market-green hover:text-market-green",
        className,
      )}
    >
      Assistant
    </Link>
  );
}

import Link from "next/link";

import { AssistantLink } from "@/components/chat/assistant-link";
import { RunList } from "@/components/run-list";
import { Separator } from "@/components/ui/separator";
import { listRuns } from "@/lib/api";
import type { RunSummary } from "@/lib/types";

export default async function ReaderLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  let runs: RunSummary[] = [];
  let backendError = false;

  try {
    runs = await listRuns();
  } catch {
    backendError = true;
  }

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-72 shrink-0 flex-col border-r border-border-soft bg-surface-0">
        <div className="flex items-start justify-between gap-2 px-4 py-4">
          <Link href="/" className="block min-w-0 flex-1">
            <h1 className="font-display text-lg font-semibold tracking-tight text-ink-900">
              SPX Analyst
            </h1>
          </Link>
          <AssistantLink />
        </div>
        <Separator />
        {backendError ? (
          <div className="px-4 py-6 text-sm text-ink-500">
            Cannot reach API at{" "}
            <code className="rounded bg-surface-1 px-1">127.0.0.1:8000</code>.
          </div>
        ) : (
          <div className="min-h-0 flex-1">
            <RunList runs={runs} />
          </div>
        )}
      </aside>
      <main className="min-w-0 flex-1">{children}</main>
    </div>
  );
}

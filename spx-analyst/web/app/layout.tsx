import type { Metadata } from "next";
import Link from "next/link";

import { RunList } from "@/components/run-list";
import { Separator } from "@/components/ui/separator";
import { TooltipProvider } from "@/components/ui/tooltip";
import { listRuns } from "@/lib/api";
import type { RunSummary } from "@/lib/types";

import "./globals.css";

export const metadata: Metadata = {
  title: "SPX Analyst Viewer",
  description: "Browse daily SPX tactical analysis reports",
};

export default async function RootLayout({
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
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full bg-background text-foreground">
        <TooltipProvider>
        <div className="flex min-h-screen">
          <aside className="flex w-72 shrink-0 flex-col border-r bg-sidebar text-sidebar-foreground">
            <div className="px-4 py-4">
              <Link href="/" className="block">
                <h1 className="text-lg font-semibold tracking-tight">
                  SPX Analyst
                </h1>
                <p className="text-xs text-muted-foreground">Phase 2 viewer</p>
              </Link>
            </div>
            <Separator />
            {backendError ? (
              <div className="px-4 py-6 text-sm text-muted-foreground">
                Cannot reach API at{" "}
                <code className="rounded bg-muted px-1">127.0.0.1:8000</code>.
              </div>
            ) : (
              <div className="min-h-0 flex-1">
                <RunList runs={runs} />
              </div>
            )}
          </aside>
          <main className="min-w-0 flex-1">{children}</main>
        </div>
        </TooltipProvider>
      </body>
    </html>
  );
}

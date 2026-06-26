import type { Metadata } from "next";
import Link from "next/link";
import { Inter, Newsreader } from "next/font/google";

import { RunList } from "@/components/run-list";
import { Separator } from "@/components/ui/separator";
import { TooltipProvider } from "@/components/ui/tooltip";
import { listRuns } from "@/lib/api";
import type { RunSummary } from "@/lib/types";

import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const newsreader = Newsreader({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

export const metadata: Metadata = {
  title: "SPX Analyst",
  description: "Daily SPX tactical analysis — editorial archive and reports",
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
    <html lang="en" className={`${inter.variable} ${newsreader.variable} h-full antialiased`}>
      <body className="min-h-full bg-background font-sans text-foreground">
        <TooltipProvider>
          <div className="flex min-h-screen">
            <aside className="flex w-72 shrink-0 flex-col border-r border-border-soft bg-surface-0">
              <div className="px-4 py-4">
                <Link href="/" className="block">
                  <h1 className="font-display text-lg font-semibold tracking-tight text-ink-900">
                    SPX Analyst
                  </h1>
                </Link>
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
        </TooltipProvider>
      </body>
    </html>
  );
}

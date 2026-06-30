import type { Metadata } from "next";
import { Inter, Newsreader } from "next/font/google";
import { cache } from "react";

import { SiteHeader } from "@/components/site-header";
import { TooltipProvider } from "@/components/ui/tooltip";
import { listRuns } from "@/lib/api";

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

const getShellRuns = cache(async () => {
  try {
    const runs = await listRuns();
    return { runs, backendError: false };
  } catch {
    return { runs: [] as Awaited<ReturnType<typeof listRuns>>, backendError: true };
  }
});

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const { runs, backendError } = await getShellRuns();

  return (
    <html lang="en" className={`${inter.variable} ${newsreader.variable} h-full antialiased`}>
      <body className="min-h-full bg-background font-sans text-foreground">
        <TooltipProvider>
          <SiteHeader runs={runs} backendError={backendError} />
          <main className="min-h-[calc(100vh-4rem)]">{children}</main>
        </TooltipProvider>
      </body>
    </html>
  );
}

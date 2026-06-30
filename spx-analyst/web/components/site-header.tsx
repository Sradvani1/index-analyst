"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import type { RunSummary } from "@/lib/types";

interface SiteHeaderProps {
  runs: RunSummary[];
  backendError: boolean;
}

const NAV_LINKS = [
  {
    href: "/runs/latest",
    label: "Latest",
    match: (path: string) => path.startsWith("/runs/"),
    resolveHref: (latestDate?: string) =>
      latestDate ? `/runs/${latestDate}` : "/archive",
  },
  { href: "/archive", label: "Archive", match: (path: string) => path === "/archive" },
  {
    href: "/assistant",
    label: "Assistant",
    match: (path: string) => path.startsWith("/assistant"),
  },
  { href: "/about", label: "About", match: (path: string) => path === "/about" },
] as const;

export function SiteHeader({ runs, backendError }: SiteHeaderProps) {
  const pathname = usePathname();
  const latestDate = runs[0]?.date;
  const [mobileOpen, setMobileOpen] = useState(false);

  const links = NAV_LINKS.map((link) => ({
    label: link.label,
    href: "resolveHref" in link ? link.resolveHref(latestDate) : link.href,
    active: link.match(pathname),
  }));

  return (
    <header className="sticky top-0 z-40 border-b border-border-soft bg-paper-50/95 shadow-editorial-2 backdrop-blur-sm">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4">
        <Link
          href="/"
          className="font-display text-lg font-semibold tracking-tight text-ink-900 hover:text-market-green"
        >
          SPX Analyst
        </Link>

        <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
          {backendError && (
            <span
              className="mr-1 text-xs text-ink-500"
              title="Cannot reach API at 127.0.0.1:8000"
            >
              API offline
            </span>
          )}
          {links.map((link) => (
            <NavLink key={link.label} href={link.href} active={link.active}>
              {link.label}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center gap-2 md:hidden">
          {backendError && (
            <span className="text-xs text-ink-500" title="Cannot reach API at 127.0.0.1:8000">
              Offline
            </span>
          )}
          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetTrigger
              render={
                <Button variant="outline" size="icon" aria-label="Open menu" />
              }
            >
              <Menu />
            </SheetTrigger>
            <SheetContent side="right" className="w-[min(100vw,20rem)]">
              <SheetHeader>
                <SheetTitle className="font-display">Navigation</SheetTitle>
              </SheetHeader>
              <nav className="flex flex-col gap-1 px-4 pb-6" aria-label="Mobile">
                {links.map((link) => (
                  <Link
                    key={link.label}
                    href={link.href}
                    onClick={() => setMobileOpen(false)}
                    className={cn(
                      "min-h-11 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                      link.active
                        ? "bg-surface-1 text-market-green"
                        : "text-ink-700 hover:bg-surface-1 hover:text-ink-900",
                    )}
                  >
                    {link.label}
                  </Link>
                ))}
              </nav>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
}

function NavLink({
  href,
  active,
  children,
}: {
  href: string;
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "min-h-11 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
        active
          ? "bg-surface-1 text-market-green"
          : "text-ink-700 hover:bg-surface-1 hover:text-ink-900",
      )}
    >
      {children}
    </Link>
  );
}

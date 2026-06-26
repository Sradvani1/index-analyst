import Link from "next/link";

import { Separator } from "@/components/ui/separator";

export default function AssistantLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex shrink-0 items-center gap-4 border-b border-border-soft bg-surface-0 px-6 py-3">
        <Link
          href="/"
          className="font-display text-sm font-semibold tracking-tight text-ink-900 hover:text-market-green"
        >
          ← Reports
        </Link>
        <Separator orientation="vertical" className="h-5" />
        <p className="text-sm text-ink-500">Research assistant</p>
      </header>
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
    </div>
  );
}

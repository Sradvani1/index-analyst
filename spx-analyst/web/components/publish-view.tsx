"use client";

import { useState } from "react";

import { ReportMarkdown } from "@/components/report-markdown";

interface PublishViewProps {
  markdown: string;
  html?: string;
}

export function PublishView({ markdown, html }: PublishViewProps) {
  const [copied, setCopied] = useState(false);

  async function copyArticle() {
    const richHtml = html ? `<article>${html}</article>` : markdown;
    try {
      if ("ClipboardItem" in window && navigator.clipboard?.write) {
        await navigator.clipboard.write([
          new ClipboardItem({
            "text/html": new Blob([richHtml], { type: "text/html" }),
            "text/plain": new Blob([markdown], { type: "text/plain" }),
          }),
        ]);
      } else {
        await navigator.clipboard.writeText(markdown);
      }
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  }

  return (
    <section className="border-t border-border-soft bg-paper-100 px-4 py-12">
      <div className="mx-auto max-w-[70ch]">
        <div className="mb-6 flex items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-market-green">
              Substack draft
            </p>
            <h2 className="mt-2 font-display text-3xl font-semibold text-ink-900">Daily editorial</h2>
          </div>
          <button
            type="button"
            onClick={copyArticle}
            className="rounded-[10px] bg-market-green px-4 py-3 text-sm font-semibold text-white hover:bg-market-green-hover"
          >
            {copied ? "Copied" : "Copy Article"}
          </button>
        </div>
        <p className="mb-8 text-sm leading-relaxed text-ink-500">
          Review this shorter narrative, then copy it into a new Substack post.
        </p>
        <div className="rounded-[14px] border border-border-soft bg-surface-0 p-6 shadow-editorial-1 sm:p-8">
          <ReportMarkdown markdown={markdown} variant="article" />
        </div>
      </div>
    </section>
  );
}

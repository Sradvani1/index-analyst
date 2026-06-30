"use client";

import { Copy, Check } from "lucide-react";
import { useState } from "react";

import { ReportMarkdown } from "@/components/report-markdown";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/lib/types";

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard unavailable — ignore.
    }
  }

  return (
    <div
      className={cn(
        "group relative rounded-[14px] border px-4 py-3 shadow-editorial-1",
        isUser
          ? "ml-4 border-border-soft bg-surface-0 sm:ml-8"
          : "mr-4 border-market-green/20 bg-surface-0 sm:mr-8",
      )}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-[0.65rem] font-medium uppercase tracking-wide text-ink-500">
          {isUser ? "You" : "Assistant"}
        </p>
        {!isUser && message.content && message.id !== "streaming" && (
          <Button
            type="button"
            variant="ghost"
            size="icon-xs"
            aria-label="Copy message"
            className="opacity-0 transition-opacity group-hover:opacity-100"
            onClick={() => void handleCopy()}
          >
            {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
          </Button>
        )}
      </div>
      {isUser ? (
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-900">
          {message.content}
        </p>
      ) : (
        <ReportMarkdown markdown={message.content} variant="compact" />
      )}
    </div>
  );
}

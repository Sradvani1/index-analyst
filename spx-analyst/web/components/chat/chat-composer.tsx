"use client";

import { Send, Square } from "lucide-react";
import { useRef } from "react";

import { Button } from "@/components/ui/button";

interface ChatComposerProps {
  draft: string;
  onDraftChange: (value: string) => void;
  onSubmit: () => void;
  onStop: () => void;
  streaming: boolean;
  placeholder?: string;
}

export function ChatComposer({
  draft,
  onDraftChange,
  onSubmit,
  onStop,
  streaming,
  placeholder = "Write a message…",
}: ChatComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!streaming && draft.trim()) {
        onSubmit();
      }
    }
  }

  function handleInput() {
    const el = textareaRef.current;
    if (!el) {
      return;
    }
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }

  return (
    <div className="border-t border-border-soft bg-surface-0 px-4 py-4 sm:px-6">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (!streaming && draft.trim()) {
            onSubmit();
          }
        }}
        className="mx-auto flex max-w-3xl flex-col gap-2"
      >
        <label htmlFor="chat-input" className="sr-only">
          Message
        </label>
        <textarea
          ref={textareaRef}
          id="chat-input"
          value={draft}
          onChange={(event) => onDraftChange(event.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          placeholder={placeholder}
          rows={2}
          disabled={streaming}
          className="w-full resize-none rounded-lg border border-border-soft bg-surface-0 px-3 py-2 text-sm text-ink-900 outline-none focus-visible:border-market-green focus-visible:ring-2 focus-visible:ring-market-green/20"
        />
        <div className="flex justify-end gap-2">
          {streaming ? (
            <Button type="button" variant="outline" onClick={onStop}>
              <Square className="size-3.5 fill-current" />
              Stop
            </Button>
          ) : (
            <Button type="submit" disabled={!draft.trim()}>
              <Send className="size-3.5" />
              Send
            </Button>
          )}
        </div>
      </form>
    </div>
  );
}

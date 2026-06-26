"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ReportMarkdown } from "@/components/report-markdown";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  createChatSession,
  deleteChatSession,
  getChatMessages,
  listChatSessions,
  streamChatMessage,
} from "@/lib/chat-api";
import { ApiError, type ChatMessage, type ChatSession } from "@/lib/types";
import { cn } from "@/lib/utils";

interface AssistantWorkspaceProps {
  sessionId?: string;
}

export function AssistantWorkspace({ sessionId }: AssistantWorkspaceProps) {
  const router = useRouter();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [error, setError] = useState<string | null>(null);

  const activeSession = useMemo(
    () => sessions.find((s) => s.id === sessionId),
    [sessions, sessionId],
  );

  const refreshSessions = useCallback(async () => {
    setLoadingSessions(true);
    try {
      setSessions(await listChatSessions());
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load sessions");
    } finally {
      setLoadingSessions(false);
    }
  }, []);

  useEffect(() => {
    void refreshSessions();
  }, [refreshSessions]);

  useEffect(() => {
    if (!sessionId) {
      setMessages([]);
      return;
    }

    let cancelled = false;
    setLoadingMessages(true);
    getChatMessages(sessionId)
      .then((data) => {
        if (!cancelled) {
          setMessages(data);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Failed to load messages");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingMessages(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  async function handleNewSession() {
    setError(null);
    try {
      const session = await createChatSession();
      await refreshSessions();
      router.push(`/assistant/${session.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create session");
    }
  }

  async function handleDeleteSession(id: string) {
    if (!window.confirm("Delete this conversation?")) {
      return;
    }
    try {
      await deleteChatSession(id);
      await refreshSessions();
      if (sessionId === id) {
        router.push("/assistant");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete session");
    }
  }

  async function handleSend(event: React.FormEvent) {
    event.preventDefault();
    if (!sessionId || !draft.trim() || streaming) {
      return;
    }

    const content = draft.trim();
    setDraft("");
    setStreaming(true);
    setStreamText("");
    setError(null);

    const optimisticId = `local-user-${Date.now()}`;
    const optimisticUser: ChatMessage = {
      id: optimisticId,
      role: "user",
      content,
      created_at: null,
    };
    setMessages((prev) => [...prev, optimisticUser]);

    try {
      await streamChatMessage(sessionId, content, {
        onChunk: (text) => setStreamText((prev) => prev + text),
        onError: (message) => setError(message),
        onDone: () => undefined,
      });
      const latest = await getChatMessages(sessionId);
      setMessages(latest);
      await refreshSessions();
    } catch (err) {
      setMessages((prev) => prev.filter((message) => message.id !== optimisticId));
      setError(err instanceof ApiError ? err.message : "Failed to send message");
    } finally {
      setStreamText("");
      setStreaming(false);
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="flex shrink-0 items-center justify-between gap-4 border-b border-border-soft bg-surface-0 px-6 py-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-ink-500">
            Research assistant
          </p>
          <h1 className="font-display text-2xl font-semibold tracking-tight text-ink-900">
            Ask about published runs
          </h1>
          <p className="mt-1 text-sm text-ink-500">
            Current posture comes from latest-run preload; historical answers use retrieved report
            sections.
          </p>
        </div>
        <Button type="button" onClick={() => void handleNewSession()}>
          New conversation
        </Button>
      </header>

      <div className="flex min-h-0 flex-1">
        <aside className="flex w-72 shrink-0 flex-col border-r border-border-soft bg-surface-1">
          <div className="px-4 py-3">
            <p className="text-xs font-medium uppercase tracking-wide text-ink-500">
              Conversations
            </p>
          </div>
          <Separator />
          <ScrollArea className="min-h-0 flex-1">
            <div className="flex flex-col gap-1 p-2">
              {loadingSessions && (
                <p className="px-2 py-3 text-sm text-ink-500">Loading…</p>
              )}
              {!loadingSessions && sessions.length === 0 && (
                <p className="px-2 py-3 text-sm text-ink-500">No conversations yet.</p>
              )}
              {sessions.map((session) => {
                const selected = session.id === sessionId;
                return (
                  <div
                    key={session.id}
                    className={cn(
                      "group flex items-start gap-1 rounded-lg border px-2 py-2",
                      selected
                        ? "border-market-green bg-surface-0"
                        : "border-transparent hover:border-border-soft hover:bg-surface-0",
                    )}
                  >
                    <Link
                      href={`/assistant/${session.id}`}
                      className="min-w-0 flex-1"
                    >
                      <p className="truncate text-sm font-medium text-ink-900">
                        {session.title}
                      </p>
                      <p className="mt-0.5 truncate text-xs text-ink-500">
                        {formatSessionTime(session.updated_at)}
                      </p>
                    </Link>
                    <button
                      type="button"
                      aria-label={`Delete ${session.title}`}
                      className="rounded px-1 text-xs text-ink-500 opacity-0 transition-opacity group-hover:opacity-100 hover:text-risk-red"
                      onClick={() => void handleDeleteSession(session.id)}
                    >
                      ×
                    </button>
                  </div>
                );
              })}
            </div>
          </ScrollArea>
        </aside>

        <section className="flex min-w-0 flex-1 flex-col bg-paper-50">
          {!sessionId ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
              <p className="max-w-md text-sm text-ink-500">
                Select a conversation or start a new one to ask about current posture or compare
                historical report sections.
              </p>
              <Button type="button" onClick={() => void handleNewSession()}>
                Start conversation
              </Button>
            </div>
          ) : (
            <>
              <ScrollArea className="min-h-0 flex-1">
                <div className="mx-auto flex max-w-3xl flex-col gap-4 px-6 py-6">
                  {loadingMessages && (
                    <p className="text-sm text-ink-500">Loading messages…</p>
                  )}
                  {messages.map((message) => (
                    <MessageBubble key={message.id} message={message} />
                  ))}
                  {streaming && (
                    <MessageBubble
                      message={{
                        id: "streaming",
                        role: "assistant",
                        content: streamText || "Thinking…",
                        created_at: null,
                      }}
                    />
                  )}
                  {error && (
                    <div className="rounded-lg border border-risk-red/30 bg-risk-red/5 px-4 py-3 text-sm text-risk-red">
                      {error}
                    </div>
                  )}
                </div>
              </ScrollArea>

              <div className="border-t border-border-soft bg-surface-0 px-6 py-4">
                <form
                  onSubmit={(event) => void handleSend(event)}
                  className="mx-auto flex max-w-3xl flex-col gap-2"
                >
                  <label htmlFor="chat-input" className="sr-only">
                    Message
                  </label>
                  <textarea
                    id="chat-input"
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    placeholder={
                      activeSession
                        ? `Message in “${activeSession.title}”…`
                        : "Write a message…"
                    }
                    rows={3}
                    disabled={streaming}
                    className="w-full resize-none rounded-lg border border-border-soft bg-surface-0 px-3 py-2 text-sm text-ink-900 outline-none focus-visible:border-market-green focus-visible:ring-2 focus-visible:ring-market-green/20"
                  />
                  <div className="flex justify-end">
                    <Button type="submit" disabled={streaming || !draft.trim()}>
                      {streaming ? "Thinking…" : "Send"}
                    </Button>
                  </div>
                </form>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "rounded-[14px] border px-4 py-3 shadow-editorial-1",
        isUser
          ? "ml-8 border-border-soft bg-surface-0"
          : "mr-8 border-market-green/20 bg-surface-0",
      )}
    >
      <p className="mb-2 text-[0.65rem] font-medium uppercase tracking-wide text-ink-500">
        {isUser ? "You" : "Assistant"}
      </p>
      {isUser ? (
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-900">
          {message.content}
        </p>
      ) : (
        <ReportMarkdown markdown={message.content} />
      )}
    </div>
  );
}

function formatSessionTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

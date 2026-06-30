"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Menu, Pencil, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ChatComposer } from "@/components/chat/chat-composer";
import { MessageBubble } from "@/components/chat/message-bubble";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  createChatSession,
  deleteChatSession,
  getChatMessages,
  listChatSessions,
  renameChatSession,
  streamChatMessage,
} from "@/lib/chat-api";
import { ApiError, type ChatMessage, type ChatSession } from "@/lib/types";
import { cn } from "@/lib/utils";

const SUGGESTED_PROMPTS = [
  "What is today's recommended action?",
  "Summarize recent arc",
  "Compare VIX regime to prior week",
] as const;

interface AssistantWorkspaceProps {
  sessionId?: string;
}

export function AssistantWorkspace({ sessionId }: AssistantWorkspaceProps) {
  const router = useRouter();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sessionSheetOpen, setSessionSheetOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState("");

  const pendingPromptRef = useRef<string | null>(null);

  const activeSession = useMemo(
    () => sessions.find((s) => s.id === sessionId),
    [sessions, sessionId],
  );

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamText, scrollToBottom]);

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
    // Initial session list load on mount.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- data fetch on mount
    void refreshSessions();
  }, [refreshSessions]);

  useEffect(() => {
    if (!sessionId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- reset when leaving a session
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

  async function startWithPrompt(prompt: string) {
    setError(null);
    try {
      const session = await createChatSession();
      pendingPromptRef.current = prompt;
      await refreshSessions();
      router.push(`/assistant/${session.id}`);
      setSessionSheetOpen(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create session");
    }
  }

  async function handleNewSession() {
    setError(null);
    try {
      const session = await createChatSession();
      await refreshSessions();
      router.push(`/assistant/${session.id}`);
      setSessionSheetOpen(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create session");
    }
  }

  async function confirmDeleteSession() {
    if (!deleteTarget) {
      return;
    }
    const id = deleteTarget;
    setDeleteTarget(null);
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

  const sendMessage = useCallback(
    async (content: string) => {
      if (!sessionId || !content.trim() || streaming) {
        return;
      }

      const trimmed = content.trim();
      setDraft("");
      setStreaming(true);
      setStreamText("");
      setError(null);

      const controller = new AbortController();
      abortRef.current = controller;

      const optimisticId = `local-user-${Date.now()}`;
      const optimisticUser: ChatMessage = {
        id: optimisticId,
        role: "user",
        content: trimmed,
        created_at: null,
      };
      setMessages((prev) => [...prev, optimisticUser]);

      try {
        await streamChatMessage(
          sessionId,
          trimmed,
          {
            onChunk: (text) => setStreamText((prev) => prev + text),
            onError: (message) => setError(message),
            onDone: () => undefined,
          },
          { signal: controller.signal },
        );
        const latest = await getChatMessages(sessionId);
        setMessages(latest);
        await refreshSessions();
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
        setMessages((prev) => prev.filter((message) => message.id !== optimisticId));
        setError(err instanceof ApiError ? err.message : "Failed to send message");
      } finally {
        abortRef.current = null;
        setStreamText("");
        setStreaming(false);
      }
    },
    [sessionId, streaming, refreshSessions],
  );

  useEffect(() => {
    if (!sessionId || !pendingPromptRef.current || loadingMessages) {
      return;
    }
    const prompt = pendingPromptRef.current;
    pendingPromptRef.current = null;
    void sendMessage(prompt);
  }, [sessionId, loadingMessages, sendMessage]);

  function handleStop() {
    abortRef.current?.abort();
    abortRef.current = null;
    setStreaming(false);
    setStreamText("");
  }

  async function saveRename(id: string) {
    const title = renameDraft.trim();
    if (!title) {
      setRenamingId(null);
      return;
    }
    try {
      await renameChatSession(id, title);
      await refreshSessions();
      setRenamingId(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to rename session");
    }
  }

  const sessionListProps = {
    sessions,
    sessionId,
    loading: loadingSessions,
    renamingId,
    renameDraft,
    onRenameStart: (session: ChatSession) => {
      setRenamingId(session.id);
      setRenameDraft(session.title);
    },
    onRenameDraftChange: setRenameDraft,
    onRenameSave: saveRename,
    onRenameCancel: () => setRenamingId(null),
    onDelete: (id: string) => setDeleteTarget(id),
    onNavigate: () => setSessionSheetOpen(false),
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border-soft bg-surface-0 px-4 py-3 sm:px-6">
        <div className="flex min-w-0 items-center gap-2">
          <Sheet open={sessionSheetOpen} onOpenChange={setSessionSheetOpen}>
            <SheetTrigger
              render={
                <Button
                  variant="outline"
                  size="sm"
                  className="md:hidden"
                  aria-label="Open conversations"
                />
              }
            >
              <Menu className="size-4" />
              Conversations
            </SheetTrigger>
            <SheetContent side="left" className="w-[min(100vw,20rem)] p-0">
              <SheetHeader className="border-b border-border-soft px-4 py-3">
                <SheetTitle className="font-display">Conversations</SheetTitle>
              </SheetHeader>
              <SessionList {...sessionListProps} />
            </SheetContent>
          </Sheet>
          <p className="truncate text-sm text-ink-500">
            {activeSession ? activeSession.title : "Select or start a conversation"}
          </p>
        </div>
        <Button type="button" size="sm" onClick={() => void handleNewSession()}>
          New conversation
        </Button>
      </div>

      <div className="flex min-h-0 flex-1">
        <aside className="hidden w-72 shrink-0 flex-col border-r border-border-soft bg-surface-1 md:flex">
          <div className="px-4 py-3">
            <p className="text-xs font-medium uppercase tracking-wide text-ink-500">
              Conversations
            </p>
          </div>
          <Separator />
          <SessionList {...sessionListProps} />
        </aside>

        <section className="flex min-w-0 flex-1 flex-col bg-paper-50">
          {!sessionId ? (
            <EmptyState
              onNewSession={() => void handleNewSession()}
              onPrompt={(prompt) => void startWithPrompt(prompt)}
            />
          ) : (
            <>
              <ScrollArea className="min-h-0 flex-1">
                <div className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-6 sm:px-6">
                  {loadingMessages && <MessageSkeleton />}
                  {!loadingMessages && messages.length === 0 && !streaming && (
                    <PromptChips onSelect={(prompt) => void sendMessage(prompt)} />
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
                  <div ref={messagesEndRef} />
                </div>
              </ScrollArea>

              <ChatComposer
                draft={draft}
                onDraftChange={setDraft}
                onSubmit={() => void sendMessage(draft)}
                onStop={handleStop}
                streaming={streaming}
                placeholder={
                  activeSession
                    ? `Message in “${activeSession.title}”…`
                    : "Write a message…"
                }
              />
            </>
          )}
        </section>
      </div>

      <AlertDialog open={deleteTarget !== null} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete conversation?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently removes the conversation and its messages.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => void confirmDeleteSession()}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function SessionList({
  sessions,
  sessionId,
  loading,
  renamingId,
  renameDraft,
  onRenameStart,
  onRenameDraftChange,
  onRenameSave,
  onRenameCancel,
  onDelete,
  onNavigate,
}: {
  sessions: ChatSession[];
  sessionId?: string;
  loading: boolean;
  renamingId: string | null;
  renameDraft: string;
  onRenameStart: (session: ChatSession) => void;
  onRenameDraftChange: (value: string) => void;
  onRenameSave: (id: string) => void;
  onRenameCancel: () => void;
  onDelete: (id: string) => void;
  onNavigate: () => void;
}) {
  if (loading) {
    return (
      <div className="flex flex-col gap-2 p-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-14 animate-pulse rounded-lg bg-surface-0" />
        ))}
      </div>
    );
  }

  if (sessions.length === 0) {
    return <p className="px-4 py-3 text-sm text-ink-500">No conversations yet.</p>;
  }

  return (
    <ScrollArea className="min-h-0 flex-1">
      <div className="flex flex-col gap-1 p-2">
        {sessions.map((session) => {
          const selected = session.id === sessionId;
          const renaming = renamingId === session.id;

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
              {renaming ? (
                <form
                  className="flex min-w-0 flex-1 flex-col gap-1"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void onRenameSave(session.id);
                  }}
                >
                  <input
                    value={renameDraft}
                    onChange={(event) => onRenameDraftChange(event.target.value)}
                    className="w-full rounded border border-border-soft bg-surface-0 px-2 py-1 text-sm"
                    autoFocus
                  />
                  <div className="flex gap-1">
                    <Button type="submit" size="xs">
                      Save
                    </Button>
                    <Button type="button" size="xs" variant="ghost" onClick={onRenameCancel}>
                      Cancel
                    </Button>
                  </div>
                </form>
              ) : (
                <>
                  <Link
                    href={`/assistant/${session.id}`}
                    onClick={onNavigate}
                    className="min-w-0 flex-1"
                  >
                    <p className="truncate text-sm font-medium text-ink-900">{session.title}</p>
                    <p className="mt-0.5 truncate text-xs text-ink-500">
                      {formatSessionTime(session.updated_at)}
                    </p>
                  </Link>
                  <button
                    type="button"
                    aria-label={`Rename ${session.title}`}
                    className="rounded p-1 text-ink-500 opacity-0 transition-opacity group-hover:opacity-100 hover:text-ink-900"
                    onClick={() => onRenameStart(session)}
                  >
                    <Pencil className="size-3.5" />
                  </button>
                  <button
                    type="button"
                    aria-label={`Delete ${session.title}`}
                    className="rounded p-1 text-ink-500 opacity-0 transition-opacity group-hover:opacity-100 hover:text-risk-red"
                    onClick={() => onDelete(session.id)}
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                </>
              )}
            </div>
          );
        })}
      </div>
    </ScrollArea>
  );
}

function EmptyState({
  onNewSession,
  onPrompt,
}: {
  onNewSession: () => void;
  onPrompt: (prompt: string) => void;
}) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
      <p className="max-w-md text-sm text-ink-500">
        Start a conversation to ask about current posture or compare historical report sections.
      </p>
      <div className="flex flex-wrap justify-center gap-2">
        {SUGGESTED_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => onPrompt(prompt)}
            className="rounded-full border border-border-soft bg-surface-0 px-3 py-1.5 text-sm text-ink-700 transition-colors hover:border-market-green/40 hover:text-market-green"
          >
            {prompt}
          </button>
        ))}
      </div>
      <Button type="button" onClick={onNewSession}>
        Start conversation
      </Button>
    </div>
  );
}

function PromptChips({ onSelect }: { onSelect: (prompt: string) => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      {SUGGESTED_PROMPTS.map((prompt) => (
        <button
          key={prompt}
          type="button"
          onClick={() => onSelect(prompt)}
          className="rounded-full border border-border-soft bg-surface-0 px-3 py-1.5 text-sm text-ink-700 transition-colors hover:border-market-green/40 hover:text-market-green"
        >
          {prompt}
        </button>
      ))}
    </div>
  );
}

function MessageSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <div className="ml-8 h-20 animate-pulse rounded-[14px] bg-surface-0" />
      <div className="mr-8 h-28 animate-pulse rounded-[14px] bg-surface-0" />
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

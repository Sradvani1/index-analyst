import { ApiError, type ChatMessage, type ChatSession } from "@/lib/types";

function apiBase(): string {
  if (typeof window === "undefined") {
    return process.env.API_BASE_URL ?? "http://127.0.0.1:8000";
  }
  return "";
}

function parseErrorDetail(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) {
    return "Request failed";
  }
  try {
    const payload = JSON.parse(trimmed) as { detail?: string | { msg?: string }[] };
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
    if (Array.isArray(payload.detail) && payload.detail[0]?.msg) {
      return payload.detail[0].msg;
    }
  } catch {
    // Not JSON — use raw text.
  }
  return trimmed;
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, {
    cache: "no-store",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const detail = parseErrorDetail(await response.text());
    throw new ApiError(detail || response.statusText, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export async function listChatSessions(): Promise<ChatSession[]> {
  return fetchJson<ChatSession[]>("/api/chat/sessions");
}

export async function createChatSession(title = "New conversation"): Promise<ChatSession> {
  return fetchJson<ChatSession>("/api/chat/sessions", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}

export async function renameChatSession(
  sessionId: string,
  title: string,
): Promise<ChatSession> {
  return fetchJson<ChatSession>(`/api/chat/sessions/${sessionId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

export async function deleteChatSession(sessionId: string): Promise<void> {
  await fetchJson<void>(`/api/chat/sessions/${sessionId}`, { method: "DELETE" });
}

export async function getChatMessages(sessionId: string): Promise<ChatMessage[]> {
  return fetchJson<ChatMessage[]>(`/api/chat/sessions/${sessionId}/messages`);
}

export interface StreamChatHandlers {
  onChunk: (text: string) => void;
  onError: (message: string) => void;
  onDone: () => void;
}

export async function streamChatMessage(
  sessionId: string,
  content: string,
  handlers: StreamChatHandlers,
): Promise<void> {
  const response = await fetch(`${apiBase()}/api/chat/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });

  if (!response.ok) {
    const detail = parseErrorDetail(await response.text());
    throw new ApiError(detail || response.statusText, response.status);
  }

  if (!response.body) {
    throw new ApiError("Empty response body", response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) {
        continue;
      }
      const data = line.slice(6).trim();
      if (data === "[DONE]") {
        handlers.onDone();
        return;
      }
      try {
        const payload = JSON.parse(data) as { text?: string; error?: string };
        if (payload.error) {
          handlers.onError(payload.error);
          throw new ApiError(payload.error, 502);
        }
        if (payload.text) {
          handlers.onChunk(payload.text);
        }
      } catch (error) {
        if (error instanceof ApiError) {
          throw error;
        }
        handlers.onError("Invalid stream payload");
        throw new ApiError("Invalid stream payload", 502);
      }
    }
  }

  handlers.onDone();
}

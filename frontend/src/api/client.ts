// The only module that knows the wire protocol.
// Note: the message stream is POST + SSE, so it is consumed with
// fetch() + ReadableStream (EventSource is GET-only).

import type {
  ApiError, AppConfig, Artifact, Message, Session, StreamEvent,
} from "./types";

const BASE = "/api/v1";

export class RequestError extends Error {
  code: string;
  status: number;
  constructor(status: number, err: ApiError) {
    super(err.message);
    this.code = err.code;
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new RequestError(
      resp.status,
      body?.error ?? { code: "network_error", message: `HTTP ${resp.status}` },
    );
  }
  return resp.json() as Promise<T>;
}

export const getConfig = () => request<AppConfig>("/config");
export const listSessions = () =>
  request<{ sessions: Session[] }>("/sessions").then((r) => r.sessions);
export const createSession = (provider?: string) =>
  request<Session>("/sessions", {
    method: "POST",
    body: JSON.stringify(provider ? { provider } : {}),
  });
export const listMessages = (sessionId: string) =>
  request<{ messages: Message[] }>(`/sessions/${sessionId}/messages`).then((r) => r.messages);
export const getArtifact = (artifactId: string, raw = false) =>
  request<Artifact>(`/artifacts/${artifactId}${raw ? "?raw=true" : ""}`);

/** Stream an assistant reply; invokes onEvent per SSE frame. Resolves when the
 * stream closes (a terminal done/error frame is guaranteed by the backend). */
export async function streamMessage(
  sessionId: string,
  content: string,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch(`${BASE}/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
    signal,
  });
  if (!resp.ok || !resp.body) {
    const body = await resp.json().catch(() => null);
    throw new RequestError(
      resp.status,
      body?.error ?? { code: "network_error", message: `HTTP ${resp.status}` },
    );
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    // SSE frames are separated by a blank line
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const event = parseFrame(frame);
      if (event) onEvent(event);
    }
  }
}

function parseFrame(frame: string): StreamEvent | null {
  let eventType = "";
  let data = "";
  for (const line of frame.split("\n")) {
    if (line.startsWith(":")) continue; // heartbeat comment
    if (line.startsWith("event: ")) eventType = line.slice(7).trim();
    else if (line.startsWith("data: ")) data += line.slice(6);
  }
  if (!eventType || !data) return null;
  try {
    return { type: eventType, ...JSON.parse(data) } as StreamEvent;
  } catch {
    return null;
  }
}

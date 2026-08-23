// Central chat state: sessions, messages, the in-flight streaming draft, and
// the artifact panel. Plain hooks — the app is small enough that a store
// library would be ceremony.

import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "../api/client";
import type {
  AppConfig, Citation, Message, Session, StreamEvent, Usage,
} from "../api/types";

export interface StreamDraft {
  content: string;
  tools: string[]; // activity notes: "search_transcripts: …"
  citations: Citation[];
  usage: Usage | null;
}

export interface StreamFailure {
  code: string;
  message: string;
  recoverable: boolean;
}

const EMPTY_DRAFT: StreamDraft = { content: "", tools: [], citations: [], usage: null };

export function useChat() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState<StreamDraft | null>(null);
  const [failure, setFailure] = useState<StreamFailure | null>(null);
  const [artifactId, setArtifactId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const refreshSessions = useCallback(async () => {
    setSessions(await api.listSessions());
  }, []);

  useEffect(() => {
    api.getConfig().then(setConfig).catch((e) => setConfigError(String(e.message ?? e)));
    refreshSessions().catch(() => setConfigError("Backend unreachable — is the stack running?"));
  }, [refreshSessions]);

  const selectSession = useCallback(async (id: string) => {
    setActiveId(id);
    setFailure(null);
    setArtifactId(null);
    setMessages(await api.listMessages(id));
  }, []);

  const newSession = useCallback(
    async (provider?: string) => {
      const session = await api.createSession(provider);
      await refreshSessions();
      setActiveId(session.id);
      setMessages([]);
      setFailure(null);
      setArtifactId(null);
      return session;
    },
    [refreshSessions],
  );

  const send = useCallback(
    async (content: string) => {
      if (!activeId) return;
      setFailure(null);
      // optimistic user message
      setMessages((prev) => [
        ...prev,
        {
          id: `optimistic-${Date.now()}`,
          role: "user",
          content,
          citations: [],
          artifact_id: null,
          usage: null,
          created_at: new Date().toISOString(),
        },
      ]);
      setDraft({ ...EMPTY_DRAFT });

      const controller = new AbortController();
      abortRef.current = controller;
      try {
        await api.streamMessage(activeId, content, (event: StreamEvent) => {
          if (event.type === "token") {
            setDraft((d) => d && { ...d, content: d.content + event.text });
          } else if (event.type === "tool_use") {
            setDraft((d) => d && { ...d, tools: [...d.tools, `${event.tool}: ${event.summary}`] });
          } else if (event.type === "citation") {
            setDraft((d) => d && { ...d, citations: [...d.citations, event.citation] });
          } else if (event.type === "artifact") {
            setArtifactId(event.artifact_id);
          } else if (event.type === "done") {
            setDraft((d) => d && { ...d, usage: event.usage });
          } else if (event.type === "error") {
            setFailure(event);
          }
        }, controller.signal);
      } catch (e) {
        const err = e as api.RequestError;
        setFailure({
          code: err.code ?? "network_error",
          message: err.message ?? "Connection lost.",
          recoverable: true,
        });
      } finally {
        abortRef.current = null;
        // reload authoritative state (persisted ids, citations, usage, title)
        try {
          setMessages(await api.listMessages(activeId));
          await refreshSessions();
        } catch {
          /* backend down: failure banner already shown */
        }
        setDraft(null);
      }
    },
    [activeId, refreshSessions],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  return {
    config, configError, sessions, activeId, messages, draft, failure, artifactId,
    selectSession, newSession, send, stop,
    openArtifact: setArtifactId,
    closeArtifact: () => setArtifactId(null),
    streaming: draft !== null,
  };
}

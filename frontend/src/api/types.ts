// Mirrors backend/app/models/api.py and the SSE event protocol.

export type Provider = "anthropic" | "local";

export interface Citation {
  index: number;
  episode_slug: string;
  episode_title: string;
  guest: string;
  ts_seconds: number;
  youtube_url: string | null;
  quote: string;
}

export interface Usage {
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  latency_ms: number;
  provider: string;
  model: string;
}

export interface Session {
  id: string;
  title: string;
  provider: Provider;
  model: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  artifact_id: string | null;
  usage: Usage | null;
  created_at: string;
}

export interface Artifact {
  id: string;
  session_id: string;
  kind: "markdown" | "html";
  title: string;
  content: string;
  created_at: string;
}

export interface AppConfig {
  default_provider: string;
  providers: {
    anthropic: { configured: boolean; model: string };
    local: { reachable: boolean; detail: string; model: string; host: string };
  };
  embedding_model: string;
  kb: {
    episodes: number;
    chunks: number;
    last_ingest: { status: string; finished_at: string | null; chunks_written: number } | null;
  };
}

export interface ApiError {
  code: string;
  message: string;
  request_id?: string;
}

// SSE stream events (POST /sessions/{id}/messages)
export type StreamEvent =
  | { type: "token"; text: string }
  | { type: "tool_use"; tool: string; summary: string }
  | { type: "citation"; citation: Citation }
  | { type: "artifact"; artifact_id: string; kind: "markdown" | "html"; title: string }
  | { type: "done"; usage: Usage }
  | { type: "error"; code: string; message: string; recoverable: boolean };

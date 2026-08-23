// The understandable-states kit: empty/welcome, streaming activity,
// failure banner, and the no-provider setup card.

import type { AppConfig } from "../api/types";
import type { StreamFailure } from "../state/useChat";

export function WelcomeState({ onSuggest }: { onSuggest: (q: string) => void }) {
  const suggestions = [
    "What do guests say about finding product-market fit?",
    "How should an early-stage startup pick a North Star metric?",
    "Write a Ship 30 essay about improving activation",
    "Make an HTML one-pager on Brian Chesky's founder-mode advice",
  ];
  return (
    <div className="mx-auto max-w-xl py-14 text-center">
      <p className="text-3xl">🎙️</p>
      <h2 className="mt-3 text-lg font-semibold text-slate-800">The Lenny Growth Assistant</h2>
      <p className="mt-1 text-sm text-slate-500">
        Grounded answers, essays, and artifacts — built from {""}
        Lenny's Podcast transcripts, with sources you can verify.
      </p>
      <div className="mt-6 grid gap-2 sm:grid-cols-2">
        {suggestions.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => onSuggest(q)}
            className="rounded-xl border border-slate-200 bg-white p-3 text-left text-xs text-slate-600 shadow-sm hover:border-indigo-300 hover:text-slate-900"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}

export function StreamingActivity({ tools }: { tools: string[] }) {
  const last = tools[tools.length - 1];
  return (
    <div className="flex items-center gap-2 text-xs text-slate-500">
      <span className="inline-flex gap-1">
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-400 [animation-delay:0ms]" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-400 [animation-delay:120ms]" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-400 [animation-delay:240ms]" />
      </span>
      {last ? <span className="truncate">{last}</span> : <span>Thinking…</span>}
    </div>
  );
}

export function FailureBanner({
  failure, onRetryLocal,
}: { failure: StreamFailure; onRetryLocal?: () => void }) {
  return (
    <div role="alert" className="mx-auto max-w-3xl rounded-xl border border-red-200 bg-red-50 p-3 text-sm">
      <p className="font-medium text-red-800">
        {failure.code.replaceAll("_", " ")}
      </p>
      <p className="mt-0.5 text-red-700">{failure.message}</p>
      {failure.recoverable && onRetryLocal && failure.code !== "ollama_unreachable" && (
        <button
          type="button"
          onClick={onRetryLocal}
          className="mt-2 rounded-lg border border-red-300 bg-white px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-100"
        >
          Start a new chat on the local model
        </button>
      )}
    </div>
  );
}

export function NoProviderCard({ config }: { config: AppConfig | null }) {
  return (
    <div className="mx-auto max-w-lg rounded-2xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
      <h2 className="font-semibold">No model provider is available</h2>
      <p className="mt-2">The assistant needs at least one of:</p>
      <ul className="mt-2 list-disc pl-5 leading-relaxed">
        <li>
          <strong>Cloud:</strong> set <code>ANTHROPIC_API_KEY</code> in <code>.env</code> and
          restart (<code>docker compose up -d</code>).
        </li>
        <li>
          <strong>Local:</strong> start Ollama — <code>brew services start ollama</code>, then{" "}
          <code>ollama pull {config?.providers.local.model ?? "qwen3:4b"}</code>.
        </li>
      </ul>
      <p className="mt-2 text-amber-700">{config?.providers.local.detail}</p>
    </div>
  );
}

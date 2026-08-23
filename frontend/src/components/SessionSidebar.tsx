import type { AppConfig, Session } from "../api/types";

interface Props {
  sessions: Session[];
  activeId: string | null;
  config: AppConfig | null;
  onSelect: (id: string) => void;
  onNew: (provider?: string) => void;
}

export default function SessionSidebar({ sessions, activeId, config, onSelect, onNew }: Props) {
  const anthropicOk = config?.providers.anthropic.configured ?? false;
  const localOk = config?.providers.local.reachable ?? false;

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-slate-200 bg-slate-50 max-md:hidden">
      <div className="space-y-1.5 p-3">
        <button
          type="button"
          onClick={() => onNew()}
          className="w-full rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          + New chat
        </button>
        {/* explicit-provider session creation; default follows the fallback chain */}
        <div className="flex gap-1.5">
          <button
            type="button"
            onClick={() => onNew("anthropic")}
            disabled={!anthropicOk}
            title={anthropicOk ? `Claude (${config?.providers.anthropic.model})` : "Set ANTHROPIC_API_KEY to enable"}
            className="flex-1 rounded-md border border-slate-300 bg-white px-2 py-1 text-[11px] text-slate-600 hover:border-indigo-300 disabled:opacity-40"
          >
            ☁ Claude
          </button>
          <button
            type="button"
            onClick={() => onNew("local")}
            disabled={!localOk}
            title={localOk ? `Ollama (${config?.providers.local.model})` : config?.providers.local.detail}
            className="flex-1 rounded-md border border-slate-300 bg-white px-2 py-1 text-[11px] text-slate-600 hover:border-indigo-300 disabled:opacity-40"
          >
            💻 Local
          </button>
        </div>
      </div>
      <nav className="flex-1 overflow-y-auto px-2 pb-2" aria-label="Conversations">
        {sessions.length === 0 && (
          <p className="px-2 py-4 text-xs text-slate-400">No conversations yet.</p>
        )}
        {sessions.map((s) => (
          <button
            type="button"
            key={s.id}
            onClick={() => onSelect(s.id)}
            className={`mb-0.5 block w-full rounded-lg px-2.5 py-2 text-left text-sm ${
              s.id === activeId
                ? "bg-indigo-100 text-indigo-900"
                : "text-slate-700 hover:bg-slate-100"
            }`}
          >
            <span className="block truncate">{s.title}</span>
            <span className="mt-0.5 flex items-center gap-1 text-[10px] text-slate-400">
              {s.provider === "anthropic" ? "☁" : "💻"} {s.model} · {s.message_count} msgs
            </span>
          </button>
        ))}
      </nav>
      {config && (
        <div className="border-t border-slate-200 p-3 text-[11px] text-slate-500">
          <p className="font-medium text-slate-600">Knowledge base</p>
          <p>
            {config.kb.episodes} episodes · {config.kb.chunks} chunks
          </p>
          {config.kb.last_ingest && (
            <p className="text-slate-400">last ingest: {config.kb.last_ingest.status}</p>
          )}
        </div>
      )}
    </aside>
  );
}

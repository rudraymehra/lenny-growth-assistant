// Always-visible answer to "which model am I talking to?" — the session's
// stamped provider/model, plus overall provider availability from /config.

import type { AppConfig, Session } from "../api/types";

export default function ProviderBadge({
  session, config,
}: { session: Session | null; config: AppConfig | null }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      {session ? (
        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium ${
            session.provider === "anthropic"
              ? "bg-violet-100 text-violet-800"
              : "bg-emerald-100 text-emerald-800"
          }`}
          title={`This session is pinned to ${session.provider} — provider is resolved once at session creation and never switches silently.`}
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              session.provider === "anthropic" ? "bg-violet-500" : "bg-emerald-500"
            }`}
          />
          {session.provider === "anthropic" ? "Claude" : "Local"} · {session.model}
        </span>
      ) : (
        <span className="text-slate-400">no active chat</span>
      )}
      {config && (
        <span className="hidden items-center gap-2 text-[11px] text-slate-400 sm:flex">
          <span title={config.providers.anthropic.configured ? "Anthropic API key configured" : "ANTHROPIC_API_KEY not set"}>
            ☁ {config.providers.anthropic.configured ? "ready" : "off"}
          </span>
          <span title={config.providers.local.detail}>
            💻 {config.providers.local.reachable ? "ready" : "off"}
          </span>
        </span>
      )}
    </div>
  );
}

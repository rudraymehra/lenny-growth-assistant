// Citation chips with an expandable quote + YouTube deep link. Citations are
// backend-verified (built from actually-retrieved chunks), so everything here
// is safe to link out.

import { useState } from "react";
import type { Citation } from "../api/types";

function formatTs(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return h > 0
    ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
    : `${m}:${String(s).padStart(2, "0")}`;
}

function Chip({ citation }: { citation: Citation }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="inline-flex items-center gap-1 rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-xs text-indigo-700 hover:bg-indigo-100 focus:outline-2 focus:outline-indigo-400"
      >
        <span className="font-semibold">[{citation.index}]</span>
        <span className="max-w-40 truncate">{citation.guest}</span>
        <span className="text-indigo-400">{formatTs(citation.ts_seconds)}</span>
      </button>
      {open && (
        <div
          role="dialog"
          className="absolute bottom-full left-0 z-20 mb-1 w-80 rounded-lg border border-slate-200 bg-white p-3 text-xs shadow-lg"
        >
          <p className="font-semibold text-slate-800">{citation.episode_title}</p>
          <p className="mt-0.5 text-slate-500">
            {citation.guest} · {formatTs(citation.ts_seconds)}
          </p>
          <p className="mt-2 italic text-slate-600">“{citation.quote}”</p>
          {citation.youtube_url && (
            <a
              href={citation.youtube_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-block font-medium text-indigo-600 hover:underline"
            >
              ▶ Watch this moment on YouTube
            </a>
          )}
        </div>
      )}
    </span>
  );
}

export default function CitationChips({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5">
      <span className="text-xs font-medium uppercase tracking-wide text-slate-400">Sources</span>
      {citations.map((c) => (
        <Chip key={`${c.index}-${c.episode_slug}`} citation={c} />
      ))}
    </div>
  );
}

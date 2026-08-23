// Side panel rendering generated artifacts next to the chat (the "Claude
// Artifacts" pattern). Preview tab: markdown via react-markdown (no raw HTML)
// or HTML via the sandboxed iframe. Source tab: the raw document as text,
// fetched with ?raw=true so what-the-sanitizer-removed is auditable.

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getArtifact } from "../api/client";
import type { Artifact } from "../api/types";
import SandboxFrame from "./SandboxFrame";

interface Props {
  artifactId: string;
  onClose: () => void;
}

export default function ArtifactViewer({ artifactId, onClose }: Props) {
  const [artifact, setArtifact] = useState<Artifact | null>(null);
  const [rawSource, setRawSource] = useState<string | null>(null);
  const [tab, setTab] = useState<"preview" | "source">("preview");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setArtifact(null);
    setRawSource(null);
    setTab("preview");
    setError(null);
    getArtifact(artifactId)
      .then(setArtifact)
      .catch((e) => setError(e.message));
  }, [artifactId]);

  useEffect(() => {
    if (tab === "source" && rawSource === null) {
      getArtifact(artifactId, true)
        .then((a) => setRawSource(a.content))
        .catch((e) => setError(e.message));
    }
  }, [tab, rawSource, artifactId]);

  return (
    <section
      aria-label="Artifact viewer"
      className="flex h-full w-[46%] min-w-80 shrink-0 flex-col border-l border-slate-200 bg-white max-lg:absolute max-lg:inset-y-0 max-lg:right-0 max-lg:z-10 max-lg:w-full max-lg:shadow-2xl"
    >
      <header className="flex items-center gap-2 border-b border-slate-200 px-4 py-2.5">
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-sm font-semibold text-slate-800">
            {artifact?.title ?? "Artifact"}
          </h2>
          <p className="text-[11px] text-slate-400">
            {artifact?.kind === "html" ? "HTML · sandboxed preview" : "Markdown"}
          </p>
        </div>
        <div role="tablist" className="flex rounded-lg border border-slate-200 p-0.5 text-xs">
          {(["preview", "source"] as const).map((t) => (
            <button
              key={t}
              role="tab"
              aria-selected={tab === t}
              onClick={() => setTab(t)}
              className={`rounded-md px-2.5 py-1 capitalize ${
                tab === t ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close artifact viewer"
          className="rounded-md px-2 py-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
        >
          ✕
        </button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {error && <p className="p-4 text-sm text-red-600">{error}</p>}
        {!artifact && !error && <p className="p-4 text-sm text-slate-400">Loading artifact…</p>}
        {artifact && tab === "preview" && artifact.kind === "html" && (
          <SandboxFrame html={artifact.content} title={artifact.title} />
        )}
        {artifact && tab === "preview" && artifact.kind === "markdown" && (
          <div className="prose-chat p-5 text-sm text-slate-800">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{artifact.content}</ReactMarkdown>
          </div>
        )}
        {artifact && tab === "source" && (
          <pre className="overflow-x-auto p-4 text-xs leading-relaxed text-slate-700">
            {rawSource ?? "Loading source…"}
          </pre>
        )}
      </div>
    </section>
  );
}

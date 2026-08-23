import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Citation, Usage } from "../api/types";
import CitationChips from "./CitationChips";

interface Props {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  usage?: Usage | null;
  artifactId?: string | null;
  artifactTitle?: string;
  onOpenArtifact?: (id: string) => void;
  grounded?: boolean; // false ⇒ show the zero-citation notice on assistant answers
}

function UsageFooter({ usage }: { usage: Usage }) {
  const cost =
    usage.cost_usd > 0 ? `$${usage.cost_usd.toFixed(4)}` : "$0.00 (local)";
  return (
    <p className="mt-2 text-[11px] text-slate-400">
      {usage.model} · {(usage.latency_ms / 1000).toFixed(1)}s ·{" "}
      {usage.input_tokens + usage.output_tokens} tokens · {cost}
    </p>
  );
}

export default function MessageBubble({
  role, content, citations = [], usage, artifactId, onOpenArtifact, grounded = true,
}: Props) {
  if (role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-indigo-600 px-4 py-2.5 text-sm text-white whitespace-pre-wrap">
          {content}
        </div>
      </div>
    );
  }
  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 shadow-sm">
        {/* react-markdown does NOT render raw HTML by default — model output
            stays inert text unless it goes through the sanitized artifact path */}
        <div className="prose-chat">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </div>
        {artifactId && onOpenArtifact && (
          <button
            type="button"
            onClick={() => onOpenArtifact(artifactId)}
            className="mt-2 flex w-full items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-left text-xs font-medium text-slate-700 hover:border-indigo-300 hover:bg-indigo-50"
          >
            <span aria-hidden>📄</span> Open artifact in viewer
          </button>
        )}
        <CitationChips citations={citations} />
        {!grounded && content && (
          <p className="mt-2 rounded-md bg-amber-50 px-2 py-1 text-[11px] text-amber-700">
            No transcript sources were cited for this answer.
          </p>
        )}
        {usage && <UsageFooter usage={usage} />}
      </div>
    </div>
  );
}

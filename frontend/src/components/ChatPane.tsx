import { useEffect, useRef } from "react";
import type { Message } from "../api/types";
import type { StreamDraft, StreamFailure } from "../state/useChat";
import MessageBubble from "./MessageBubble";
import { FailureBanner, StreamingActivity, WelcomeState } from "./StatusStates";

interface Props {
  messages: Message[];
  draft: StreamDraft | null;
  failure: StreamFailure | null;
  hasSession: boolean;
  onOpenArtifact: (id: string) => void;
  onSuggest: (q: string) => void;
  onRetryLocal: () => void;
}

export default function ChatPane({
  messages, draft, failure, hasSession, onOpenArtifact, onSuggest, onRetryLocal,
}: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, draft?.content, draft?.tools.length, failure]);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto bg-slate-50 px-4 py-4">
      <div className="mx-auto max-w-3xl space-y-4">
        {!hasSession && messages.length === 0 && <WelcomeState onSuggest={onSuggest} />}
        {hasSession && messages.length === 0 && !draft && (
          <WelcomeState onSuggest={onSuggest} />
        )}
        {messages.map((m) => (
          <MessageBubble
            key={m.id}
            role={m.role}
            content={m.content}
            citations={m.citations}
            usage={m.usage}
            artifactId={m.artifact_id}
            onOpenArtifact={onOpenArtifact}
            grounded={m.role !== "assistant" || m.citations.length > 0}
          />
        ))}
        {draft && (
          <div className="space-y-2">
            {draft.content ? (
              <MessageBubble
                role="assistant"
                content={draft.content}
                citations={draft.citations}
              />
            ) : null}
            {!draft.usage && <StreamingActivity tools={draft.tools} />}
          </div>
        )}
        {failure && <FailureBanner failure={failure} onRetryLocal={onRetryLocal} />}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

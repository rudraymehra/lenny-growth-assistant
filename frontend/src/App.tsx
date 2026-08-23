import { useCallback } from "react";
import ArtifactViewer from "./components/ArtifactViewer";
import ChatPane from "./components/ChatPane";
import Composer from "./components/Composer";
import ProviderBadge from "./components/ProviderBadge";
import SessionSidebar from "./components/SessionSidebar";
import { NoProviderCard } from "./components/StatusStates";
import { useChat } from "./state/useChat";

export default function App() {
  const chat = useChat();
  const activeSession = chat.sessions.find((s) => s.id === chat.activeId) ?? null;
  const noProvider =
    chat.config !== null &&
    !chat.config.providers.anthropic.configured &&
    !chat.config.providers.local.reachable;

  // Sending from the welcome state auto-creates a session first; the fresh
  // session id is passed explicitly (state updates land on the next render).
  const sendSmart = useCallback(
    async (content: string) => {
      if (chat.activeId) {
        chat.send(content);
      } else {
        const session = await chat.newSession();
        chat.send(content, session.id);
      }
    },
    [chat],
  );

  return (
    <div className="flex h-screen flex-col bg-white text-slate-900">
      <header className="flex items-center justify-between border-b border-slate-200 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span aria-hidden className="text-lg">🎙️</span>
          <div>
            <h1 className="text-sm font-semibold leading-tight">The Lenny Growth Assistant</h1>
            <p className="text-[11px] text-slate-400">
              grounded in Lenny's Podcast transcripts
            </p>
          </div>
        </div>
        <ProviderBadge session={activeSession} config={chat.config} />
      </header>

      <div className="relative flex min-h-0 flex-1">
        <SessionSidebar
          sessions={chat.sessions}
          activeId={chat.activeId}
          config={chat.config}
          onSelect={chat.selectSession}
          onNew={chat.newSession}
        />
        <main className="flex min-w-0 flex-1 flex-col">
          {chat.configError && (
            <p role="alert" className="bg-red-50 px-4 py-2 text-xs text-red-700">
              {chat.configError}
            </p>
          )}
          {noProvider ? (
            <div className="flex flex-1 items-center px-4">
              <NoProviderCard config={chat.config} />
            </div>
          ) : (
            <>
              <ChatPane
                messages={chat.messages}
                draft={chat.draft}
                failure={chat.failure}
                hasSession={chat.activeId !== null}
                onOpenArtifact={chat.openArtifact}
                onSuggest={sendSmart}
                onRetryLocal={() => chat.newSession("local")}
              />
              <Composer
                disabled={noProvider}
                streaming={chat.streaming}
                onSend={sendSmart}
                onStop={chat.stop}
              />
            </>
          )}
        </main>
        {chat.artifactId && (
          <ArtifactViewer artifactId={chat.artifactId} onClose={chat.closeArtifact} />
        )}
      </div>
    </div>
  );
}

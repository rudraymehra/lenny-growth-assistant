import { useState } from "react";

interface Props {
  disabled: boolean;
  streaming: boolean;
  onSend: (content: string) => void;
  onStop: () => void;
}

export default function Composer({ disabled, streaming, onSend, onStop }: Props) {
  const [value, setValue] = useState("");

  const submit = () => {
    const content = value.trim();
    if (!content || disabled || streaming) return;
    setValue("");
    onSend(content);
  };

  return (
    <div className="border-t border-slate-200 bg-white p-3">
      <div className="mx-auto flex max-w-3xl items-end gap-2">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          rows={Math.min(6, Math.max(1, value.split("\n").length))}
          placeholder={
            disabled
              ? "Start a new chat to begin"
              : "Ask about product & growth… (Enter to send, Shift+Enter for newline)"
          }
          disabled={disabled}
          aria-label="Message"
          className="flex-1 resize-none rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 disabled:bg-slate-50"
        />
        {streaming ? (
          <button
            type="button"
            onClick={onStop}
            className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
          >
            Stop
          </button>
        ) : (
          <button
            type="button"
            onClick={submit}
            disabled={disabled || !value.trim()}
            className="rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-40"
          >
            Send
          </button>
        )}
      </div>
      <p className="mx-auto mt-1.5 max-w-3xl text-[11px] text-slate-400">
        Try: “What do guests say about activation metrics?” · “Write a Ship 30 essay on retention”
        · “Turn that into an HTML one-pager”
      </p>
    </div>
  );
}

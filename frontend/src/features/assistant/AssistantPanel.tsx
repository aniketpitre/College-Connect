import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { ASSISTANT_STRINGS } from "../../i18n/assistant";
import { useAskAssistant } from "../../lib/assistant";
import { useMe } from "../../lib/auth";
import { useLanguage } from "../../lib/language";
import type { ChatMessage } from "../../lib/types";
import "./assistant.css";

let next = 0;
const uid = () => `m${++next}`;

/** The help desk inside every portal: answers from the documents and notices this person may see, with sources. */
export function AssistantPanel() {
  const [language] = useLanguage();
  const t = ASSISTANT_STRINGS[language];
  const { data: me } = useMe();
  const mine = me?.kind === "student" || me?.kind === "parent";
  const ask = useAskAssistant();
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo?.({ top: listRef.current.scrollHeight });
  }, [messages, ask.isPending]);
  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const send = (text: string) => {
    const question = text.trim();
    if (!question || ask.isPending) return;
    setMessages((m) => [...m, { id: uid(), role: "user", text: question }]);
    setInput("");
    ask.mutate(
      { question, language },
      {
        onSuccess: (r) => setMessages((m) => [...m, { id: uid(), role: "assistant", text: r.answer, sources: r.sources, grounded: r.grounded }]),
        onError: (e) => setMessages((m) => [...m, { id: uid(), role: "assistant", text: e.message || t.error, isError: true }]),
      },
    );
  };

  if (!open)
    return (
      <button type="button" className="assistant-fab" onClick={() => setOpen(true)} aria-haspopup="dialog">
        <span aria-hidden="true">✦</span> {t.open}
      </button>
    );

  return (
    <aside className="assistant-panel" role="dialog" aria-label={t.title} lang={language}>
      <header className="assistant-head">
        <b>{t.title}</b>
        <span className="row-actions">
          {messages.length > 0 && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setMessages([])} disabled={ask.isPending}>
              {t.clear}
            </button>
          )}
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setOpen(false)} aria-label={t.close}>
            ✕
          </button>
        </span>
      </header>
      <div className="assistant-list" ref={listRef} aria-live="polite">
        {messages.length === 0 && (
          <div className="assistant-intro">
            <p className="small">{mine ? t.introMine : t.intro}</p>
            {(mine ? t.examplesMine : t.examples).map((q) => (
              <button key={q} type="button" className="assistant-chip" onClick={() => send(q)}>
                {q}
              </button>
            ))}
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`assistant-msg ${m.role}${m.isError ? " error" : ""}`}>
            <div className="assistant-text">{m.text}</div>
            {m.role === "assistant" && !m.isError && !m.grounded && <div className="small muted">{t.notFound}</div>}
            {m.sources?.map((s, i) => (
              <div key={i} className="assistant-source small">
                <span className="muted">{t.source}: </span>
                {s.link ? (
                  <Link to={s.link} onClick={() => setOpen(false)}>
                    {s.title}
                  </Link>
                ) : (
                  s.title
                )}
                <span className="muted"> · {s.section}</span>
              </div>
            ))}
          </div>
        ))}
        {ask.isPending && <div className="assistant-msg assistant small muted">{t.thinking}</div>}
      </div>
      <form
        className="assistant-form"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <textarea
          ref={inputRef}
          rows={2}
          maxLength={500}
          value={input}
          placeholder={t.placeholder}
          aria-label={t.placeholder}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(input);
            }
          }}
        />
        <button type="submit" className="btn btn-primary btn-sm" disabled={ask.isPending || !input.trim()}>
          {t.send}
        </button>
      </form>
      <p className="assistant-foot small muted">{t.disclaimer}</p>
    </aside>
  );
}

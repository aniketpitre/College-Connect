import { useEffect, useRef, useState } from "react";
import { askQuestion } from "./api";
import type { Strings } from "./i18n";
import type { Category, ChatMessage, Language } from "./types";

function uid() {
  return Math.random().toString(36).slice(2, 10);
}

interface Props {
  t: Strings;
  language: Language;
  category?: Category;
  onClearCategory: () => void;
}

export default function Chat({ t, language, category, onClearCategory }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    boxRef.current?.scrollTo({ top: boxRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  const activeDept = t.depts.find((d) => d.category === category);

  async function send(question: string) {
    const q = question.trim();
    if (!q || loading) return;
    setMessages((prev) => [...prev, { id: uid(), role: "user", text: q }]);
    setInput("");
    setLoading(true);
    try {
      const res = await askQuestion(q, language, category);
      setMessages((prev) => [
        ...prev,
        {
          id: uid(),
          role: "assistant",
          text: res.answer,
          sources: res.sources,
          grounded: res.grounded,
          confidence: res.confidence,
        },
      ]);
    } catch {
      setMessages((prev) => [...prev, { id: uid(), role: "assistant", text: t.backendOffline, isError: true }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="demo-wrap">
      <div className="demo-side">
        <h4>{t.demo_side_h}</h4>
        <p>{t.demo_side_p}</p>
        {t.chips.map((c) => (
          <button key={c} type="button" className="chip" onClick={() => send(c)} disabled={loading}>
            {c}
          </button>
        ))}
      </div>
      <div className="demo-main">
        {activeDept && (
          <div className="filter-bar">
            <span>
              {t.filtering} <b>{activeDept.title}</b>
            </span>
            <button type="button" onClick={onClearCategory}>
              {t.clearFilter} ×
            </button>
          </div>
        )}
        <div className="demo-messages" ref={boxRef} aria-live="polite">
          <div className="bubble bot">{t.welcome}</div>
          {messages.map((m) =>
            m.role === "user" ? (
              <div key={m.id} className="bubble user">
                {m.text}
              </div>
            ) : (
              <div key={m.id} className={`bubble bot${m.isError ? " error" : ""}`}>
                <span className="answer">{m.text}</span>
                {m.sources?.map((s, i) => (
                  <span className="cite" key={i}>
                    {t.source}: {s.title} · {s.section}
                    <span className="cite-doc">{s.document}</span>
                  </span>
                ))}
                {!m.isError && (
                  <span className="meta-row">
                    <span className={m.grounded ? "badge grounded" : "badge ungrounded"}>
                      {m.grounded ? t.grounded : t.notGrounded}
                    </span>
                    {m.grounded && typeof m.confidence === "number" && (
                      <span className="badge">
                        {t.confidence}: {Math.round(m.confidence * 100)}%
                      </span>
                    )}
                  </span>
                )}
              </div>
            ),
          )}
          {loading && (
            <div className="typing" aria-label={t.thinking}>
              <span className="typing-dots">
                <span />
                <span />
                <span />
              </span>
              {t.thinking}
            </div>
          )}
        </div>
        <form
          className="demo-input"
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
        >
          <input
            type="text"
            value={input}
            placeholder={t.demo_placeholder}
            onChange={(e) => setInput(e.target.value)}
            maxLength={500}
            autoComplete="off"
            aria-label={t.demo_placeholder}
          />
          <button type="submit" disabled={loading || !input.trim()}>
            {t.demo_send}
          </button>
        </form>
      </div>
    </div>
  );
}

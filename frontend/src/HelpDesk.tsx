import { useEffect, useRef, useState } from "react";
import { askQuestion } from "./api";
import { UI_STRINGS } from "./i18n";
import type { Category, ChatMessage, Language } from "./types";

const LANGUAGES: { code: Language; label: string }[] = [
  { code: "en", label: "EN" },
  { code: "hi", label: "हि" },
  { code: "mr", label: "मर" },
];

function uid() {
  return Math.random().toString(36).slice(2, 10);
}

export default function HelpDesk() {
  const [language, setLanguage] = useState<Language>("en");
  const [category, setCategory] = useState<Category | undefined>(undefined);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const t = UI_STRINGS[language];
  const office = t.officesList.find((o) => o.category === category);
  const suggestions = office ? office.questions : t.generalQuestions;

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  function pickOffice(cat: Category | undefined) {
    setCategory(cat);
    inputRef.current?.focus();
  }

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
        { id: uid(), role: "assistant", text: res.answer, sources: res.sources, grounded: res.grounded, confidence: res.confidence },
      ]);
    } catch {
      setMessages((prev) => [...prev, { id: uid(), role: "assistant", text: t.backendOffline, isError: true }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="desk" lang={language}>
      <header className="topbar">
        <div className="brand">
          <span className="seal">CC</span>
          <span>
            CollegeConnect AI
            <span className="brand-sub">{t.tagline}</span>
          </span>
        </div>
        <div className="topbar-right">
          {messages.length > 0 && (
            <button type="button" className="btn btn-ghost btn-sm new-chat" onClick={() => setMessages([])} disabled={loading} aria-label={t.newChat}>
              <span aria-hidden="true">+</span>
              <span className="new-chat-label">{t.newChat}</span>
            </button>
          )}
          <div className="lang-toggle" role="group" aria-label="Language">
            {LANGUAGES.map((l) => (
              <button
                key={l.code}
                type="button"
                className={l.code === language ? "active" : ""}
                aria-pressed={l.code === language}
                onClick={() => setLanguage(l.code)}
              >
                {l.label}
              </button>
            ))}
          </div>
        </div>
      </header>

      <div className="desk-body">
        <aside className="sidebar" aria-label={t.offices}>
          <div className="sidebar-label">{t.offices}</div>
          <nav className="office-list">
            <button type="button" className={!category ? "office active" : "office"} aria-pressed={!category} onClick={() => pickOffice(undefined)}>
              <span className="office-title">{t.allOffices}</span>
              <span className="office-desc">{t.allOfficesDesc}</span>
            </button>
            {t.officesList.map((o) => (
              <button
                key={o.category}
                type="button"
                className={category === o.category ? "office active" : "office"}
                aria-pressed={category === o.category}
                onClick={() => pickOffice(o.category)}
              >
                <span className="office-title">{o.title}</span>
                <span className="office-desc">{o.desc}</span>
              </button>
            ))}
          </nav>
          <div className="sidebar-foot">
            <p>{t.disclaimer}</p>
            <a href="#/admin">{t.admin} →</a>
          </div>
        </aside>

        {/* Phones: offices become a scrollable chip row */}
        <div className="office-chips" role="group" aria-label={t.offices}>
          <button type="button" className={!category ? "ochip active" : "ochip"} onClick={() => pickOffice(undefined)}>
            {t.allOffices}
          </button>
          {t.officesList.map((o) => (
            <button key={o.category} type="button" className={category === o.category ? "ochip active" : "ochip"} onClick={() => pickOffice(o.category)}>
              {o.title}
            </button>
          ))}
        </div>

        <main className="chat-pane">
          <div className="chat-scroll" ref={scrollRef} aria-live="polite">
            <div className="chat-col">
              {messages.length === 0 ? (
                <div className="empty">
                  <h1>{office ? office.title : t.welcomeTitle}</h1>
                  <p>{t.welcome}</p>
                  <div className="suggest-label">{t.tryAsking}</div>
                  <div className="suggestions">
                    {suggestions.map((q) => (
                      <button key={q} type="button" className="suggestion" onClick={() => send(q)}>
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                messages.map((m) =>
                  m.role === "user" ? (
                    <div key={m.id} className="msg user">
                      {m.text}
                    </div>
                  ) : (
                    <div key={m.id} className={m.isError ? "msg bot error" : "msg bot"}>
                      <div className="msg-text">{m.text}</div>
                      {m.sources && m.sources.length > 0 && (
                        <div className="sources">
                          {m.sources.map((s, i) => (
                            <div className="source" key={i}>
                              <span className="source-k">{t.source}</span>
                              <span className="source-title">{s.title}</span>
                              <span className="source-meta">
                                {s.document} · {s.section}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                      {!m.isError && (
                        <div className="meta-row">
                          <span className={m.grounded ? "badge grounded" : "badge ungrounded"}>{m.grounded ? t.grounded : t.notGrounded}</span>
                          {m.grounded && typeof m.confidence === "number" && (
                            <span className="badge">
                              {t.confidence}: {Math.round(m.confidence * 100)}%
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  ),
                )
              )}
              {loading && (
                <div className="typing">
                  <span className="typing-dots" aria-hidden="true">
                    <span />
                    <span />
                    <span />
                  </span>
                  {t.thinking}
                </div>
              )}
            </div>
          </div>

          <form
            className="composer"
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
          >
            <div className="composer-inner">
              {office && (
                <div className="asking">
                  {t.askingOffice} <b>{office.title}</b>
                  <button type="button" onClick={() => pickOffice(undefined)} aria-label={t.allOffices}>
                    ×
                  </button>
                </div>
              )}
              <div className="composer-box">
                <textarea
                  ref={inputRef}
                  rows={1}
                  value={input}
                  maxLength={500}
                  placeholder={t.placeholder}
                  aria-label={t.placeholder}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                      e.preventDefault();
                      send(input);
                    }
                  }}
                />
                <button type="submit" disabled={loading || !input.trim()}>
                  {t.send}
                </button>
              </div>
            </div>
          </form>
        </main>
      </div>
    </div>
  );
}

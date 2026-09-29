import { useEffect, useRef, useState } from "react";
import "./App.css";
import { askQuestion, fetchCategories } from "./api";
import { UI_STRINGS } from "./i18n";
import type { Category, CategoryInfo, ChatMessage, Language } from "./types";

const LANGUAGES: { code: Language; label: string }[] = [
  { code: "en", label: "EN" },
  { code: "hi", label: "हिं" },
  { code: "mr", label: "मर" },
];

function uid() {
  return Math.random().toString(36).slice(2, 10);
}

function App() {
  const [language, setLanguage] = useState<Language>("en");
  const [categories, setCategories] = useState<CategoryInfo[]>([]);
  const [activeCategory, setActiveCategory] = useState<Category | undefined>(undefined);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [backendOnline, setBackendOnline] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  const t = UI_STRINGS[language];

  useEffect(() => {
    fetchCategories()
      .then(setCategories)
      .catch(() => setBackendOnline(false));
  }, []);

  useEffect(() => {
    setMessages((prev) => {
      if (prev.length > 0) return prev;
      return [{ id: uid(), role: "assistant", text: t.welcome }];
    });
  }, [t.welcome]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  function categoryLabel(cat: CategoryInfo) {
    if (language === "hi") return cat.label_hi;
    if (language === "mr") return cat.label_mr;
    return cat.label_en;
  }

  async function handleSend(question?: string) {
    const q = (question ?? input).trim();
    if (!q || loading) return;

    setMessages((prev) => [...prev, { id: uid(), role: "user", text: q }]);
    setInput("");
    setLoading(true);

    try {
      const res = await askQuestion(q, language, activeCategory);
      setBackendOnline(true);
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
      setBackendOnline(false);
      setMessages((prev) => [
        ...prev,
        { id: uid(), role: "assistant", text: t.backendOffline, isError: true },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark">CC</span>
          <div>
            <h1>{t.appName}</h1>
            <p className="tagline">{t.tagline}</p>
          </div>
        </div>
        <div className="lang-switcher" role="group" aria-label="Language">
          {LANGUAGES.map((lng) => (
            <button
              key={lng.code}
              className={lng.code === language ? "lang-btn active" : "lang-btn"}
              onClick={() => setLanguage(lng.code)}
            >
              {lng.label}
            </button>
          ))}
        </div>
      </header>

      {!backendOnline && <div className="banner banner-error">{t.backendOffline}</div>}
      <div className="banner banner-info">{t.demoNotice}</div>

      {categories.length > 0 && (
        <div className="categories">
          <span className="categories-label">{t.categoriesLabel}</span>
          <div className="chip-row">
            <button
              className={!activeCategory ? "chip active" : "chip"}
              onClick={() => setActiveCategory(undefined)}
            >
              All
            </button>
            {categories.map((cat) => (
              <button
                key={cat.id}
                className={activeCategory === cat.id ? "chip active" : "chip"}
                onClick={() => setActiveCategory(cat.id)}
              >
                {categoryLabel(cat)}
              </button>
            ))}
          </div>
        </div>
      )}

      <main className="chat" ref={scrollRef}>
        {messages.map((m) => (
          <div key={m.id} className={`msg-row ${m.role}`}>
            <div className={`msg-bubble ${m.role} ${m.isError ? "error" : ""}`}>
              <p>{m.text}</p>
              {m.role === "assistant" && m.sources && m.sources.length > 0 && (
                <div className="sources">
                  {m.sources.map((s, i) => (
                    <div className="source-card" key={i}>
                      <div className="source-title">{s.title}</div>
                      <div className="source-meta">
                        {s.document} · {s.section}
                      </div>
                    </div>
                  ))}
                  <div className="meta-row">
                    <span className={m.grounded ? "badge grounded" : "badge ungrounded"}>
                      {m.grounded ? t.grounded : t.notGrounded}
                    </span>
                    {typeof m.confidence === "number" && (
                      <span className="badge confidence">
                        {t.confidence}: {Math.round(m.confidence * 100)}%
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="msg-row assistant">
            <div className="msg-bubble assistant thinking">{t.thinking}</div>
          </div>
        )}
      </main>

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
      >
        <input
          type="text"
          value={input}
          placeholder={t.inputPlaceholder}
          onChange={(e) => setInput(e.target.value)}
        />
        <button type="submit" disabled={loading || !input.trim()}>
          {t.send}
        </button>
      </form>
    </div>
  );
}

export default App;

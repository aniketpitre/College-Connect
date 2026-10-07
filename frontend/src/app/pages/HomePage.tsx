import { useState } from "react";
import { Link } from "react-router";
import { HOME_STRINGS } from "../../i18n/home";
import { useMe } from "../../lib/auth";
import { saveLanguage, savedLanguage } from "../../lib/language";
import type { Language } from "../../lib/types";
import LanguageToggle from "../LanguageToggle";
import "./home.css";

const ICONS = { student: "🎓", parent: "👪", staff: "🏛️", apply: "📝" } as const;

/** The public home page: sign-in panels for each kind of user, and CollegeConnect AI (after sign-in only). */
export default function HomePage() {
  const [language, setLanguage] = useState<Language>(savedLanguage);
  const t = HOME_STRINGS[language];
  const { data: me } = useMe();
  return (
    <div className="home" lang={language}>
      <header className="home-top">
        <Link className="brand" to="/">
          <span className="seal">CC</span> CollegeConnect
        </Link>
        <div className="home-top-right">
          <LanguageToggle
            value={language}
            onChange={(l) => {
              setLanguage(l);
              saveLanguage(l);
            }}
          />
          <Link className="btn btn-primary btn-sm" to={me ? "/app" : "/login"}>
            {me ? t.goToPortal : t.signIn}
          </Link>
        </div>
      </header>

      <section className="home-hero">
        <h1>{t.heroTitle}</h1>
        <p>{t.heroText}</p>
      </section>

      <main className="home-grid">
        <section aria-labelledby="portals">
          <h2 id="portals" className="home-subhead">
            {t.portalsTitle}
          </h2>
          <div className="home-panels">
            {t.panels.map((p) => (
              <Link key={p.key} className="home-panel" to={p.key === "apply" ? "/apply" : `/login?as=${p.key}`}>
                <span className="home-panel-icon" aria-hidden="true">
                  {ICONS[p.key]}
                </span>
                <span className="home-panel-title">{p.title}</span>
                <span className="home-panel-text">{p.text}</span>
                <span className="home-panel-action">{p.action} →</span>
              </Link>
            ))}
          </div>
        </section>

        <aside className="home-ai" aria-labelledby="ai">
          <div className="home-ai-badge" aria-hidden="true">
            ✦
          </div>
          <h2 id="ai">{t.aiTitle}</h2>
          <p>{t.aiText}</p>
          <ul className="home-ai-examples">
            {t.aiExamples.map((q) => (
              <li key={q}>“{q}”</li>
            ))}
          </ul>
          {me ? (
            <Link className="btn btn-primary" to="/app">
              {t.aiOpen}
            </Link>
          ) : (
            <>
              <p className="home-ai-locked">
                <span aria-hidden="true">🔒</span> {t.aiLocked}
              </p>
              <Link className="btn btn-primary" to="/login">
                {t.aiSignIn}
              </Link>
            </>
          )}
          <p className="small muted">{t.aiLanguages}</p>
        </aside>
      </main>

      <footer className="home-foot">
        <p>{t.verify}</p>
        <p className="muted">{t.footer}</p>
      </footer>
    </div>
  );
}

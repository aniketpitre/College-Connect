import { useEffect, useState } from "react";
import Admin from "./Admin";
import "./App.css";
import Chat from "./Chat";
import { UI_STRINGS } from "./i18n";
import type { Category, Language } from "./types";

const LANGUAGES: { code: Language; label: string }[] = [
  { code: "en", label: "EN" },
  { code: "hi", label: "हि" },
  { code: "mr", label: "मर" },
];

const isAdminRoute = () => window.location.hash.startsWith("#/admin");

function App() {
  const [admin, setAdmin] = useState(isAdminRoute);

  useEffect(() => {
    const onHash = () => setAdmin(isAdminRoute());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  return admin ? <Admin /> : <Site />;
}

function Site() {
  const [language, setLanguage] = useState<Language>("en");
  const [category, setCategory] = useState<Category | undefined>(undefined);
  const t = UI_STRINGS[language];

  function askOffice(cat: Category) {
    setCategory(cat);
    document.getElementById("demo")?.scrollIntoView({ behavior: "smooth" });
  }

  return (
    <div lang={language}>
      <header className="nav">
        <div className="nav-inner">
          <a className="brand" href="#top">
            <span className="seal">CC</span> CollegeConnect AI
          </a>
          <nav className="links">
            <a href="#departments">{t.nav_features}</a>
            <a href="#how">{t.nav_how}</a>
            <a href="#demo">{t.nav_demo}</a>
            <a href="#dashboards">{t.nav_dash}</a>
          </nav>
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

      <section className="hero" id="top">
        <div className="wrap hero-grid">
          <div>
            <div className="eyebrow">{t.hero_eyebrow}</div>
            <h1>
              {t.hero_h1_plain}
              <em>{t.hero_h1_em}</em>
            </h1>
            <p className="lede">{t.hero_lede}</p>
            <div className="hero-ctas">
              <a href="#demo" className="btn btn-primary">
                {t.hero_cta1}
              </a>
              <a href="#how" className="btn btn-ghost">
                {t.hero_cta2}
              </a>
            </div>
            <div className="hero-stats">
              <div>
                <div className="num">24×7</div>
                <div className="label">{t.stat1}</div>
              </div>
              <div>
                <div className="num">3</div>
                <div className="label">{t.stat2}</div>
              </div>
              <div>
                <div className="num">100%</div>
                <div className="label">{t.stat3}</div>
              </div>
            </div>
          </div>
          <div>
            <div className="id-card" aria-hidden="true">
              <div className="id-card-top">
                <span className="tag">{t.card_tag}</span>
                <span className="stamp">{t.card_stamp}</span>
              </div>
              <div className="chat-preview">
                <div className="bubble user">{t.heroPreview.user}</div>
                <div className="bubble bot">
                  {t.heroPreview.bot}
                  <span className="cite">{t.heroPreview.cite}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <div className="ledger">
        <div className="wrap">
          {t.ledger.map((item, i) => (
            <div key={i}>
              <span className="ledger-n">0{i + 1}</span>
              {item}
            </div>
          ))}
        </div>
      </div>

      <section id="departments">
        <div className="wrap">
          <div className="section-head">
            <div className="eyebrow">{t.dept_eyebrow}</div>
            <h2>{t.dept_h2}</h2>
            <p>{t.dept_p}</p>
          </div>
          <div className="dept-grid">
            {t.depts.map((d) => (
              <button key={d.category} type="button" className="dept-card" onClick={() => askOffice(d.category)}>
                <span className="mark">{d.mark}</span>
                <h3>{d.title}</h3>
                <p>{d.desc}</p>
                <span className="dept-ask">{t.dept_ask}</span>
              </button>
            ))}
          </div>
        </div>
      </section>

      <section id="how" className="alt">
        <div className="wrap">
          <div className="section-head">
            <div className="eyebrow">{t.how_eyebrow}</div>
            <h2>{t.how_h2}</h2>
            <p>{t.how_p}</p>
          </div>
          <div className="flow">
            {t.flow.map((f, i) => (
              <div className="flow-step" key={i}>
                <div className="n">{i + 1}</div>
                <h4>{f.title}</h4>
                <p>{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="demo">
        <div className="wrap">
          <div className="section-head">
            <div className="eyebrow">{t.demo_eyebrow}</div>
            <h2>{t.demo_h2}</h2>
            <p>{t.demo_p}</p>
          </div>
          <Chat t={t} language={language} category={category} onClearCategory={() => setCategory(undefined)} />
        </div>
      </section>

      <section id="dashboards" className="alt">
        <div className="wrap">
          <div className="section-head">
            <div className="eyebrow">{t.dash_eyebrow}</div>
            <h2>{t.dash_h2}</h2>
            <p>{t.dash_p}</p>
          </div>
          <div className="dash-grid">
            {[
              { eyebrow: t.dash1_eyebrow, h: t.dash1_h, p: t.dash1_p, rows: t.dash1_rows, link: "" },
              { eyebrow: t.dash2_eyebrow, h: t.dash2_h, p: t.dash2_p, rows: t.dash2_rows, link: t.dash2_link },
            ].map((card) => (
              <div className="dash-card" key={card.h}>
                <div className="dash-top">
                  <div className="eyebrow">{card.eyebrow}</div>
                  <span className="preview-stamp">{t.dash_preview}</span>
                </div>
                <h3>{card.h}</h3>
                <p>{card.p}</p>
                {card.rows.map(([label, value]) => (
                  <div className="row-mock" key={label}>
                    <span>{label}</span>
                    <b>{value}</b>
                  </div>
                ))}
                {card.link && (
                  <a className="dash-link" href="#/admin">
                    {card.link}
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      <footer>
        <div className="wrap">
          <div className="brand">
            <span className="seal">CC</span> CollegeConnect AI
          </div>
          <div>{t.footer_note}</div>
        </div>
      </footer>
    </div>
  );
}

export default App;

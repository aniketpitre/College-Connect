import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router";
import { HOME_STRINGS, type HomeStrings } from "../../i18n/home";
import { apiFetch } from "../../lib/api";
import { useMe } from "../../lib/auth";
import { saveLanguage, savedLanguage } from "../../lib/language";
import type { Language } from "../../lib/types";
import LanguageToggle from "../LanguageToggle";
import "./home.css";

interface CollegeProfile {
  name: string;
  short_name: string;
  address: string;
  phone: string;
  email: string;
  website: string;
  university: string;
  departments: number;
  programmes: { code: string; name: string; level: string; duration_years: number | null; department: string }[];
}

const CAMPUS_ICONS: Record<HomeStrings["campusItems"][number]["key"], string> = {
  library: "📚",
  hostel: "🏠",
  placement: "💼",
  exams: "📝",
  scholarship: "🎖️",
  care: "🤝",
};
const PORTAL_ICONS = { student: "🎓", staff: "🏛️", parent: "👪" } as const;

const reducedMotion = () => typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** Adds `is-visible` to elements with `data-reveal` as they scroll into view (all at once without IntersectionObserver). */
function useReveal(root: React.RefObject<HTMLElement | null>, deps: unknown[]) {
  useEffect(() => {
    const items = Array.from(root.current?.querySelectorAll<HTMLElement>("[data-reveal]:not(.is-visible)") ?? []);
    if (typeof IntersectionObserver === "undefined" || reducedMotion()) {
      items.forEach((el) => el.classList.add("is-visible"));
      return;
    }
    const io = new IntersectionObserver(
      (entries) =>
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("is-visible");
            io.unobserve(e.target);
          }
        }),
      { threshold: 0.15, rootMargin: "0px 0px -40px 0px" },
    );
    items.forEach((el) => io.observe(el));
    return () => io.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

/** Counts up to `to` once it is on screen. */
function CountUp({ to, suffix = "" }: { to: number; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [value, setValue] = useState(() => (typeof IntersectionObserver === "undefined" || reducedMotion() ? to : 0));
  useEffect(() => {
    if (typeof IntersectionObserver === "undefined" || reducedMotion() || !ref.current) {
      setValue(to);
      return;
    }
    let frame = 0;
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      io.disconnect();
      const start = performance.now();
      const tick = (now: number) => {
        const p = Math.min(1, (now - start) / 1200);
        setValue(Math.round(to * (1 - Math.pow(1 - p, 3))));
        if (p < 1) frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
    });
    io.observe(ref.current);
    return () => {
      io.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [to]);
  return (
    <span ref={ref}>
      {value}
      {suffix}
    </span>
  );
}

function Section({ id, eyebrow, title, children, tone }: { id: string; eyebrow: string; title: string; children: ReactNode; tone?: "soft" }) {
  return (
    <section id={id} className={`hp-section${tone ? ` hp-${tone}` : ""}`} aria-labelledby={`${id}-title`}>
      <div className="hp-wrap">
        <div className="hp-eyebrow" data-reveal>
          {eyebrow}
        </div>
        <h2 id={`${id}-title`} className="hp-title" data-reveal>
          {title}
        </h2>
        {children}
      </div>
    </section>
  );
}

/** The college's public home page: who we are, what we teach, campus life, admissions, and the login. */
export default function HomePage() {
  const [language, setLanguage] = useState<Language>(savedLanguage);
  const [scrolled, setScrolled] = useState(false);
  const t = HOME_STRINGS[language];
  const { data: me } = useMe();
  const college = useQuery({ queryKey: ["public", "college"], queryFn: () => apiFetch<CollegeProfile>("/setup/public"), staleTime: 10 * 60_000, retry: false });
  const info = college.data;
  const name = info?.name || t.collegeFallback;
  const programmes = info?.programmes ?? [];
  const root = useRef<HTMLDivElement>(null);
  useReveal(root, [language, programmes.length]);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const loginTo = me ? "/app" : "/login";
  return (
    <div className="hp" lang={language} ref={root}>
      <header className={`hp-top${scrolled ? " is-scrolled" : ""}`}>
        <Link className="hp-brand" to="/">
          <span className="hp-crest" aria-hidden="true">
            <CrestIcon />
          </span>
          <span className="hp-brand-name">{info?.short_name || name}</span>
        </Link>
        <nav className="hp-nav" aria-label="Sections">
          <a href="#about">{t.nav.about}</a>
          <a href="#academics">{t.nav.academics}</a>
          <a href="#campus">{t.nav.campus}</a>
          <a href="#admissions">{t.nav.admissions}</a>
        </nav>
        <div className="hp-top-right">
          <LanguageToggle
            value={language}
            onChange={(l) => {
              setLanguage(l);
              saveLanguage(l);
            }}
          />
          <Link className="hp-login" to={loginTo}>
            {me ? t.goToPortal : t.login}
          </Link>
        </div>
      </header>

      <section className="hp-hero" aria-labelledby="hero-title">
        <div className="hp-hero-bg" aria-hidden="true">
          <span className="hp-orb hp-orb-1" />
          <span className="hp-orb hp-orb-2" />
          <span className="hp-orb hp-orb-3" />
          <span className="hp-grid-lines" />
          <span className="hp-float hp-float-1">✦</span>
          <span className="hp-float hp-float-2">📖</span>
          <span className="hp-float hp-float-3">🎓</span>
          <span className="hp-float hp-float-4">✦</span>
        </div>
        <div className="hp-hero-inner">
          <div className="hp-hero-copy">
            <p className="hp-hero-eyebrow">{t.heroEyebrow}</p>
            <h1 id="hero-title" className="hp-hero-title">
              {name}
            </h1>
            {info?.university && (
              <p className="hp-hero-uni">
                {t.affiliated} {info.university}
              </p>
            )}
            <p className="hp-hero-words" aria-label={t.heroWords.join(" ")}>
              {t.heroWords.map((w, i) => (
                <span key={w} style={{ animationDelay: `${0.5 + i * 0.25}s` }} aria-hidden="true">
                  {w}
                </span>
              ))}
            </p>
            <p className="hp-hero-text">{t.heroText}</p>
            <div className="hp-hero-actions">
              <Link className="hp-btn hp-btn-gold" to={loginTo}>
                {me ? t.goToPortal : t.login}
              </Link>
              <Link className="hp-btn hp-btn-line" to="/apply">
                {t.apply}
              </Link>
            </div>
          </div>
          <div className="hp-hero-art" aria-hidden="true">
            <CampusArt />
          </div>
        </div>
        <a className="hp-scroll" href="#about" aria-label={t.explore}>
          <span />
        </a>
      </section>

      <div className="hp-stats" role="list">
        {[
          { n: programmes.length, label: t.stats.programmes },
          { n: info?.departments ?? 0, label: t.stats.departments },
          { n: 3, label: t.stats.languages },
          { n: 20, label: t.stats.online, suffix: "+" },
        ].map((s, i) => (
          <div key={s.label} className="hp-stat" role="listitem" data-reveal style={{ transitionDelay: `${i * 0.08}s` }}>
            <b>
              <CountUp to={s.n} suffix={s.suffix} />
            </b>
            <span>{s.label}</span>
          </div>
        ))}
      </div>

      <Section id="about" eyebrow={t.aboutEyebrow} title={t.aboutTitle}>
        <p className="hp-lead" data-reveal>
          {t.aboutText}
        </p>
        <div className="hp-pillars">
          {t.pillars.map((p, i) => (
            <article key={p.title} className="hp-pillar" data-reveal style={{ transitionDelay: `${i * 0.1}s` }}>
              <span className="hp-pillar-num">{String(i + 1).padStart(2, "0")}</span>
              <h3>{p.title}</h3>
              <p>{p.text}</p>
            </article>
          ))}
        </div>
      </Section>

      <Section id="academics" eyebrow={t.academicsEyebrow} title={t.academicsTitle} tone="soft">
        <p className="hp-lead" data-reveal>
          {t.academicsText}
        </p>
        {programmes.length === 0 ? (
          <p className="hp-muted" data-reveal>
            {college.isLoading ? "…" : t.noProgrammes}
          </p>
        ) : (
          <div className="hp-programmes">
            {programmes.map((p, i) => (
              <article key={p.code} className="hp-programme" data-reveal style={{ transitionDelay: `${(i % 4) * 0.08}s` }}>
                <span className="hp-programme-code">{p.code}</span>
                <h3>{p.name}</h3>
                <p>{[p.level, p.duration_years ? t.years(p.duration_years) : null, p.department].filter(Boolean).join(" · ")}</p>
              </article>
            ))}
          </div>
        )}
      </Section>

      <Section id="campus" eyebrow={t.campusEyebrow} title={t.campusTitle}>
        <div className="hp-campus">
          {t.campusItems.map((c, i) => (
            <article key={c.key} className="hp-campus-card" data-reveal style={{ transitionDelay: `${(i % 3) * 0.1}s` }}>
              <span className="hp-campus-icon" aria-hidden="true">
                {CAMPUS_ICONS[c.key]}
              </span>
              <h3>{c.title}</h3>
              <p>{c.text}</p>
            </article>
          ))}
        </div>
      </Section>

      <section id="admissions" className="hp-admissions" aria-labelledby="admissions-title">
        <div className="hp-wrap hp-admissions-inner">
          <div data-reveal>
            <h2 id="admissions-title">{t.admissionsTitle}</h2>
            <p>{t.admissionsText}</p>
            <Link className="hp-btn hp-btn-gold" to="/apply">
              {t.apply}
            </Link>
          </div>
          <ol className="hp-steps">
            {t.admissionsSteps.map((s, i) => (
              <li key={s} data-reveal style={{ transitionDelay: `${i * 0.12}s` }}>
                <span>{i + 1}</span>
                {s}
              </li>
            ))}
          </ol>
        </div>
      </section>

      <Section id="portals" eyebrow={t.portalsEyebrow} title={t.portalsTitle}>
        <div className="hp-portals">
          {t.portals.map((p, i) => (
            <Link key={p.key} className="hp-portal" to={`/login?as=${p.key}`} data-reveal style={{ transitionDelay: `${i * 0.1}s` }}>
              <span className="hp-portal-icon" aria-hidden="true">
                {PORTAL_ICONS[p.key]}
              </span>
              <span className="hp-portal-title">{p.title}</span>
              <span className="hp-portal-text">{p.text}</span>
              <span className="hp-portal-action">{p.action} →</span>
            </Link>
          ))}
        </div>

        <aside className="hp-ai" aria-labelledby="ai-title" data-reveal>
          <span className="hp-ai-spark" aria-hidden="true">
            ✦
          </span>
          <div className="hp-ai-copy">
            <h2 id="ai-title">{t.aiTitle}</h2>
            <p>{t.aiText}</p>
          </div>
          <Link className="hp-btn hp-btn-ink" to={me ? "/app" : "/login"}>
            {me ? t.aiOpen : `🔒 ${t.aiAction}`}
          </Link>
        </aside>
      </Section>

      <footer className="hp-foot">
        <div className="hp-wrap hp-foot-inner">
          <div>
            <div className="hp-foot-name">{name}</div>
            {info?.university && (
              <p>
                {t.affiliated} {info.university}
              </p>
            )}
            {info?.address && <p>{info.address}</p>}
            <p>{[info?.phone, info?.email].filter(Boolean).join(" · ")}</p>
          </div>
          <div>
            <p>{t.verify}</p>
            <p className="hp-muted">{t.footer}</p>
            <p className="hp-muted">CollegeConnect</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

function CrestIcon() {
  return (
    <svg viewBox="0 0 32 32" width="30" height="30">
      <path d="M16 2 L28 7 V16 C28 23 22 28 16 30 C10 28 4 23 4 16 V7 Z" fill="var(--brass)" />
      <path d="M9 13 L16 10 L23 13 L16 16 Z" fill="var(--ink)" />
      <path d="M11.5 14.5 V19 C13 20.5 19 20.5 20.5 19 V14.5" fill="none" stroke="var(--ink)" strokeWidth="1.6" />
    </svg>
  );
}

/** A college building: drawn in line by line, with the dome, flag and windows lighting up. */
function CampusArt() {
  const cols = [70, 110, 150, 190, 230, 270];
  return (
    <svg className="hp-campus-art" viewBox="0 0 340 260" role="presentation">
      <defs>
        <linearGradient id="hp-sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="rgba(230,200,92,0.35)" />
          <stop offset="1" stopColor="rgba(230,200,92,0)" />
        </linearGradient>
      </defs>
      <circle className="hp-sun" cx="250" cy="70" r="46" fill="url(#hp-sky)" />
      <g className="hp-draw" fill="none" stroke="var(--brass-soft)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M130 92 Q170 40 210 92" />
        <path d="M170 46 V22" />
        <path d="M40 110 L170 88 L300 110 Z" />
        <path d="M44 116 H296" />
        <path d="M44 214 H296" />
        <path d="M30 228 H310" />
        {cols.map((x) => (
          <path key={x} d={`M${x} 122 V208`} />
        ))}
        <path d="M150 208 V170 Q170 152 190 170 V208" />
      </g>
      <path className="hp-flag" d="M170 22 L192 28 L170 34 Z" fill="var(--brass)" />
      {[90, 130, 210, 250].map((x, i) => (
        <rect
          key={x}
          className="hp-window"
          x={x - 6}
          y="140"
          width="12"
          height="18"
          rx="6"
          fill="var(--brass-soft)"
          style={{ animationDelay: `${2 + i * 0.3}s` }}
        />
      ))}
      <g className="hp-trees" fill="var(--teal)">
        <circle cx="22" cy="208" r="16" />
        <circle cx="318" cy="206" r="18" />
      </g>
    </svg>
  );
}

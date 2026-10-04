import { Link } from "react-router";
import type { Language } from "../../lib/types";
import "../layout.css";

interface Props {
  strings: Record<Language, { title: string; body: string; back: string }>;
  language: Language;
  children?: React.ReactNode;
}

export default function SimplePage({ strings, language, children }: Props) {
  const t = strings[language];
  return (
    <div className="simple-page" lang={language}>
      <div className="simple-card">
        <Link className="brand" to="/">
          <span className="seal">CC</span> CollegeConnect
        </Link>
        <h1>{t.title}</h1>
        <p>{t.body}</p>
        {children}
        <Link to="/">{t.back} →</Link>
      </div>
    </div>
  );
}

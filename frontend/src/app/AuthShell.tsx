import { Link } from "react-router";
import type { Language } from "../lib/types";
import "./auth.css";
import LanguageToggle from "./LanguageToggle";

/** The centred card used by the sign-in, 2-step and password pages. */
export default function AuthShell({
  language,
  onLanguage,
  children,
}: {
  language: Language;
  onLanguage: (l: Language) => void;
  children: React.ReactNode;
}) {
  return (
    <div className="auth-page" lang={language}>
      <div className="auth-card">
        <div className="auth-card-top">
          <Link className="brand" to="/">
            <span className="seal">CC</span> CollegeConnect
          </Link>
          <LanguageToggle value={language} onChange={onLanguage} />
        </div>
        {children}
      </div>
    </div>
  );
}

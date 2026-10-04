import { useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router";
import { AUTH_STRINGS, errorText } from "../../i18n/auth";
import { ApiError } from "../../lib/api";
import { pendingStep, safeNext, useLogin, useMe } from "../../lib/auth";
import { saveLanguage, savedLanguage } from "../../lib/language";
import type { Language } from "../../lib/types";
import "../auth.css";
import LanguageToggle from "../LanguageToggle";
import PasswordInput from "../PasswordInput";

export default function LoginPage() {
  const [language, setLanguage] = useState<Language>(savedLanguage);
  const [mode, setMode] = useState<"student" | "staff">("student");
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { data: me } = useMe();
  const login = useLogin();
  const t = AUTH_STRINGS[language];
  const next = safeNext(params.get("next"));

  if (me && !login.isPending) return <Navigate to={pendingStep(me) ?? next ?? "/app"} replace />;

  const error = login.error instanceof ApiError ? errorText(t, login.error.code, login.error.message) : null;

  return (
    <div className="auth-page" lang={language}>
      <form
        className="auth-card"
        onSubmit={(e) => {
          e.preventDefault();
          login.mutate(
            { identifier: identifier.trim(), password },
            { onSuccess: (signedIn) => navigate(pendingStep(signedIn) ?? next ?? "/app", { replace: true }) },
          );
        }}
      >
        <div className="auth-card-top">
          <Link className="brand" to="/">
            <span className="seal">CC</span> CollegeConnect
          </Link>
          <LanguageToggle
            value={language}
            onChange={(l) => {
              setLanguage(l);
              saveLanguage(l);
            }}
          />
        </div>
        <h1>{t.signInTitle}</h1>
        <div className="auth-tabs" role="tablist">
          {(["student", "staff"] as const).map((m) => (
            <button
              key={m}
              type="button"
              role="tab"
              aria-selected={mode === m}
              className={mode === m ? "active" : ""}
              onClick={() => {
                setMode(m);
                setIdentifier("");
                login.reset();
              }}
            >
              {m === "student" ? t.student : t.staff}
            </button>
          ))}
        </div>
        {error && (
          <div className="form-error" role="alert">
            {error}
          </div>
        )}
        <div className="field">
          <label htmlFor="identifier">{mode === "student" ? t.prn : t.email}</label>
          <input
            id="identifier"
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            type={mode === "student" ? "text" : "email"}
            autoComplete="username"
            autoCapitalize={mode === "student" ? "characters" : "none"}
            spellCheck={false}
            required
          />
          {mode === "student" && <span className="field-hint">{t.prnHint}</span>}
        </div>
        <div className="field">
          <label htmlFor="password">{t.password}</label>
          <PasswordInput id="password" value={password} onChange={setPassword} autoComplete="current-password" showLabel={t.show} hideLabel={t.hide} />
        </div>
        <button type="submit" className="btn btn-primary auth-submit" disabled={login.isPending || !identifier.trim() || !password}>
          {login.isPending ? t.signingIn : t.signIn}
        </button>
        <div className="auth-links">
          <Link to="/forgot-password">{t.forgot}</Link>
          <Link to="/">{t.backToHelpDesk}</Link>
        </div>
      </form>
    </div>
  );
}

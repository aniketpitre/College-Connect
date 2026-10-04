import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { AUTH_STRINGS, errorText } from "../../i18n/auth";
import { ApiError } from "../../lib/api";
import { useChangePassword, useMe } from "../../lib/auth";
import { saveLanguage, savedLanguage } from "../../lib/language";
import type { Language } from "../../lib/types";
import "../auth.css";
import LanguageToggle from "../LanguageToggle";
import PasswordInput from "../PasswordInput";

export default function ChangePasswordPage() {
  const [language, setLanguage] = useState<Language>(savedLanguage);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [touched, setTouched] = useState(false);
  const { data: me } = useMe();
  const change = useChangePassword();
  const navigate = useNavigate();
  const t = AUTH_STRINGS[language];
  const forced = Boolean(me?.must_change_password);
  const mismatch = touched && confirm.length > 0 && next !== confirm;

  const apiError = change.error instanceof ApiError ? change.error : null;
  const fieldError = (field: string) => (apiError?.field === field ? errorText(t, apiError.code, apiError.message) : null);
  const generalError = apiError && !apiError.field ? errorText(t, apiError.code, apiError.message) : null;

  return (
    <div className="auth-page" lang={language}>
      <form
        className="auth-card"
        onSubmit={(e) => {
          e.preventDefault();
          setTouched(true);
          if (next !== confirm) return;
          change.mutate({ current_password: current, new_password: next }, { onSuccess: () => navigate("/app", { replace: true }) });
        }}
      >
        <div className="auth-card-top">
          <span className="brand">
            <span className="seal">CC</span> CollegeConnect
          </span>
          <LanguageToggle
            value={language}
            onChange={(l) => {
              setLanguage(l);
              saveLanguage(l);
            }}
          />
        </div>
        <h1>{t.changeTitle}</h1>
        <p className="auth-intro">{forced ? t.changeIntroForced : t.changeIntro}</p>
        {generalError && (
          <div className="form-error" role="alert">
            {generalError}
          </div>
        )}
        <div className="field">
          <label htmlFor="current">{t.currentPassword}</label>
          <PasswordInput id="current" value={current} onChange={setCurrent} autoComplete="current-password" showLabel={t.show} hideLabel={t.hide} invalid={!!fieldError("current_password")} />
          {fieldError("current_password") && <span className="field-error">{fieldError("current_password")}</span>}
        </div>
        <div className="field">
          <label htmlFor="new">{t.newPassword}</label>
          <PasswordInput id="new" value={next} onChange={setNext} autoComplete="new-password" showLabel={t.show} hideLabel={t.hide} invalid={!!fieldError("new_password")} />
          <span className="field-hint">{t.passwordRules}</span>
          {fieldError("new_password") && <span className="field-error">{apiError?.message}</span>}
        </div>
        <div className="field">
          <label htmlFor="confirm">{t.confirmPassword}</label>
          <PasswordInput id="confirm" value={confirm} onChange={setConfirm} autoComplete="new-password" showLabel={t.show} hideLabel={t.hide} invalid={mismatch} />
          {mismatch && <span className="field-error">{t.mismatch}</span>}
        </div>
        <button type="submit" className="btn btn-primary auth-submit" disabled={change.isPending || !current || !next || !confirm}>
          {change.isPending ? t.saving : t.save}
        </button>
        {!forced && (
          <div className="auth-links">
            <Link to="/app">← CollegeConnect</Link>
          </div>
        )}
      </form>
    </div>
  );
}

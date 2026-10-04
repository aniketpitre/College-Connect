import { useState } from "react";
import { Link, useLocation } from "react-router";
import { ACCOUNT_STRINGS } from "../../i18n/account";
import { AUTH_STRINGS, errorText } from "../../i18n/auth";
import { useCompleteReset } from "../../lib/account";
import { ApiError } from "../../lib/api";
import { useLanguage } from "../../lib/language";
import AuthShell from "../AuthShell";
import PasswordInput from "../PasswordInput";

/** Opened from the emailed link: /reset-password#<token> (the token never reaches server logs). */
export default function ResetPasswordPage() {
  const [language, setLanguage] = useLanguage();
  const { hash } = useLocation();
  const token = hash.replace(/^#/, "");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const reset = useCompleteReset();
  const t = ACCOUNT_STRINGS[language];
  const ta = AUTH_STRINGS[language];
  const mismatch = confirm.length > 0 && next !== confirm;
  const err = reset.error instanceof ApiError ? reset.error : null;
  const badLink = !token || err?.code === "invalid_token";

  return (
    <AuthShell language={language} onLanguage={setLanguage}>
      <h1>{t.resetTitle}</h1>
      {reset.isSuccess ? (
        <div className="auth-success" role="status">
          {t.resetDone}
        </div>
      ) : badLink ? (
        <>
          <div className="form-error" role="alert">
            {ta.errors.invalid_token}
          </div>
          <Link className="btn btn-primary auth-submit" to="/forgot-password">
            {t.requestNew}
          </Link>
        </>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (next === confirm) reset.mutate({ token, new_password: next });
          }}
        >
          {err && !err.field && (
            <div className="form-error" role="alert">
              {errorText(ta, err.code, err.message)}
            </div>
          )}
          <div className="field">
            <label htmlFor="new">{ta.newPassword}</label>
            <PasswordInput id="new" value={next} onChange={setNext} autoComplete="new-password" showLabel={ta.show} hideLabel={ta.hide} invalid={err?.field === "new_password"} />
            <span className="field-hint">{ta.passwordRules}</span>
            {err?.field === "new_password" && <span className="field-error">{err.message}</span>}
          </div>
          <div className="field">
            <label htmlFor="confirm">{ta.confirmPassword}</label>
            <PasswordInput id="confirm" value={confirm} onChange={setConfirm} autoComplete="new-password" showLabel={ta.show} hideLabel={ta.hide} invalid={mismatch} />
            {mismatch && <span className="field-error">{ta.mismatch}</span>}
          </div>
          <button type="submit" className="btn btn-primary auth-submit" disabled={reset.isPending || !next || next !== confirm}>
            {reset.isPending ? ta.saving : ta.save}
          </button>
        </form>
      )}
      <div className="auth-links">
        <Link to="/login">{t.backToSignIn}</Link>
      </div>
    </AuthShell>
  );
}

import { useState } from "react";
import { Link } from "react-router";
import { ACCOUNT_STRINGS } from "../../i18n/account";
import { AUTH_STRINGS, errorText } from "../../i18n/auth";
import { useForgotPassword } from "../../lib/account";
import { ApiError } from "../../lib/api";
import { useLanguage } from "../../lib/language";
import AuthShell from "../AuthShell";

export default function ForgotPasswordPage() {
  const [language, setLanguage] = useLanguage();
  const [identifier, setIdentifier] = useState("");
  const forgot = useForgotPassword();
  const t = ACCOUNT_STRINGS[language];
  const err = forgot.error instanceof ApiError ? forgot.error : null;

  return (
    <AuthShell language={language} onLanguage={setLanguage}>
      <h1>{t.forgotTitle}</h1>
      {forgot.isSuccess ? (
        <div className="auth-success" role="status">
          {t.forgotDone}
        </div>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            forgot.mutate(identifier.trim());
          }}
        >
          <p className="auth-intro">{t.forgotIntro}</p>
          {err && (
            <div className="form-error" role="alert">
              {errorText(AUTH_STRINGS[language], err.code, err.message)}
            </div>
          )}
          <div className="field">
            <label htmlFor="identifier">{t.identifier}</label>
            <input id="identifier" value={identifier} onChange={(e) => setIdentifier(e.target.value)} autoComplete="username" required />
          </div>
          <button type="submit" className="btn btn-primary auth-submit" disabled={forgot.isPending || !identifier.trim()}>
            {forgot.isPending ? t.sending : t.sendLink}
          </button>
        </form>
      )}
      <p className="field-hint">{t.noEmailHint}</p>
      <div className="auth-links">
        <Link to="/login">{t.backToSignIn}</Link>
      </div>
    </AuthShell>
  );
}

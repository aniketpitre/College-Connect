import { useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router";
import { AUTH_STRINGS, errorText } from "../../i18n/auth";
import { ApiError } from "../../lib/api";
import { PARENT_STRINGS } from "../../i18n/parent";
import { pendingStep, safeNext, useLogin, useMe, type Me } from "../../lib/auth";
import { useRequestCode, useVerifyCode } from "../../lib/parent";
import { saveLanguage, savedLanguage } from "../../lib/language";
import type { Language } from "../../lib/types";
import "../auth.css";
import LanguageToggle from "../LanguageToggle";
import PasswordInput from "../PasswordInput";

export default function LoginPage() {
  const [language, setLanguage] = useState<Language>(savedLanguage);
  const [mode, setMode] = useState<"student" | "staff" | "parent">("student");
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  // Parents: a one-time code by default, a password if they have set one.
  const [withPassword, setWithPassword] = useState(false);
  const [code, setCode] = useState("");
  const requestCode = useRequestCode();
  const verifyCode = useVerifyCode();
  const p = PARENT_STRINGS[language];
  const codeMode = mode === "parent" && !withPassword;
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { data: me } = useMe();
  const login = useLogin();
  const t = AUTH_STRINGS[language];
  const next = safeNext(params.get("next"));

  if (me && !login.isPending && !verifyCode.isPending) return <Navigate to={pendingStep(me) ?? next ?? "/app"} replace />;

  const failure = codeMode ? (verifyCode.error ?? requestCode.error) : login.error;
  const error =
    failure instanceof ApiError
      ? failure.code === "invalid_code"
        ? p.codeWrong
        : errorText(t, failure.code, failure.message)
      : null;
  const done = (signedIn: Me) =>
    navigate(pendingStep(signedIn) ?? next ?? "/app", { replace: true });

  return (
    <div className="auth-page" lang={language}>
      <form
        className="auth-card"
        onSubmit={(e) => {
          e.preventDefault();
          if (!codeMode) login.mutate({ identifier: identifier.trim(), password }, { onSuccess: done });
          else if (!requestCode.isSuccess) requestCode.mutate(identifier.trim());
          else verifyCode.mutate({ phone: identifier.trim(), code: code.trim() }, { onSuccess: done });
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
          {(["student", "parent", "staff"] as const).map((m) => (
            <button
              key={m}
              type="button"
              role="tab"
              aria-selected={mode === m}
              className={mode === m ? "active" : ""}
              onClick={() => {
                setMode(m);
                setIdentifier("");
                setCode("");
                setWithPassword(false);
                login.reset();
                requestCode.reset();
                verifyCode.reset();
              }}
            >
              {m === "student" ? t.student : m === "parent" ? p.parent : t.staff}
            </button>
          ))}
        </div>
        {error && (
          <div className="form-error" role="alert">
            {error}
          </div>
        )}
        <div className="field">
          <label htmlFor="identifier">{mode === "student" ? t.prn : mode === "parent" ? p.mobile : t.email}</label>
          <input
            id="identifier"
            value={identifier}
            onChange={(e) => {
              setIdentifier(e.target.value);
              if (codeMode) requestCode.reset();
            }}
            type={mode === "staff" ? "email" : mode === "parent" ? "tel" : "text"}
            inputMode={mode === "parent" ? "numeric" : undefined}
            autoComplete={mode === "parent" ? "tel" : "username"}
            autoCapitalize={mode === "student" ? "characters" : "none"}
            spellCheck={false}
            required
          />
          {mode === "student" && <span className="field-hint">{t.prnHint}</span>}
          {mode === "parent" && <span className="field-hint">{p.mobileHint}</span>}
        </div>
        {codeMode ? (
          requestCode.isSuccess && (
            <>
              <p className="field-hint" role="status">
                {p.codeSent}
              </p>
              <div className="field">
                <label htmlFor="otp">{p.code}</label>
                <input
                  id="otp"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  required
                />
              </div>
            </>
          )
        ) : (
          <div className="field">
            <label htmlFor="password">{t.password}</label>
            <PasswordInput id="password" value={password} onChange={setPassword} autoComplete="current-password" showLabel={t.show} hideLabel={t.hide} />
          </div>
        )}
        {codeMode ? (
          <button
            type="submit"
            className="btn btn-primary auth-submit"
            disabled={requestCode.isPending || verifyCode.isPending || !identifier.trim() || (requestCode.isSuccess && code.length !== 6)}
          >
            {requestCode.isPending ? p.sending : requestCode.isSuccess ? (verifyCode.isPending ? t.signingIn : p.verify) : p.sendCode}
          </button>
        ) : (
          <button type="submit" className="btn btn-primary auth-submit" disabled={login.isPending || !identifier.trim() || !password}>
            {login.isPending ? t.signingIn : t.signIn}
          </button>
        )}
        {mode === "parent" && (
          <div className="auth-links">
            {codeMode && requestCode.isSuccess && (
              <button type="button" className="link-button" onClick={() => requestCode.mutate(identifier.trim())}>
                {p.resend}
              </button>
            )}
            <button
              type="button"
              className="link-button"
              onClick={() => {
                setWithPassword(!withPassword);
                login.reset();
                verifyCode.reset();
              }}
            >
              {withPassword ? p.useCode : p.usePassword}
            </button>
          </div>
        )}
        <div className="auth-links">
          <Link to="/forgot-password">{t.forgot}</Link>
          <Link to="/">{t.backToHelpDesk}</Link>
        </div>
      </form>
    </div>
  );
}

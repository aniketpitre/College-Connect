import { useState } from "react";
import { Navigate, useNavigate } from "react-router";
import { ACCOUNT_STRINGS, type AccountStrings } from "../../i18n/account";
import { AUTH_STRINGS, errorText, type AuthStrings } from "../../i18n/auth";
import { useVerifyMfa } from "../../lib/account";
import { ApiError } from "../../lib/api";
import { pendingStep, useLogout, useMe, type Me } from "../../lib/auth";
import { useLanguage } from "../../lib/language";
import AuthShell from "../AuthShell";
import { CodeInput, RecoveryCodes, TwoStepSetup } from "../TwoStepSetup";

/** After the password: enter the 2-step code, or set 2-step up when the role requires it. */
export default function TwoStepPage() {
  const [language, setLanguage] = useLanguage();
  const { data: me, isLoading } = useMe();
  const logout = useLogout();
  const navigate = useNavigate();
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);
  const t = ACCOUNT_STRINGS[language];
  const ta = AUTH_STRINGS[language];
  // Called with the updated account (after verify) or after re-render (recovery codes saved).
  const goOn = (current: Me | null | undefined = me) => navigate((current && pendingStep(current)) ?? "/app", { replace: true });

  if (isLoading) return <div className="auth-loading">…</div>;
  if (!me) return <Navigate to="/login" replace />;
  if (me.session_state === "active" && !recoveryCodes) return <Navigate to={pendingStep(me) ?? "/app"} replace />;

  return (
    <AuthShell language={language} onLanguage={setLanguage}>
      <h1>{t.twoStepTitle}</h1>
      {recoveryCodes ? (
        <RecoveryCodes t={t} codes={recoveryCodes} onDone={() => goOn()} />
      ) : me.session_state === "mfa_setup" ? (
        <TwoStepSetup t={t} ta={ta} required onEnabled={setRecoveryCodes} />
      ) : (
        <Verify t={t} ta={ta} onVerified={goOn} />
      )}
      {!recoveryCodes && (
        <div className="auth-links">
          <button
            type="button"
            className="link-button"
            onClick={() => logout.mutate(undefined, { onSettled: () => navigate("/login", { replace: true }) })}
          >
            {t.cancelSignIn}
          </button>
        </div>
      )}
    </AuthShell>
  );
}

function Verify({ t, ta, onVerified }: { t: AccountStrings; ta: AuthStrings; onVerified: (me: Me) => void }) {
  const verify = useVerifyMfa();
  const [useRecovery, setUseRecovery] = useState(false);
  const [code, setCode] = useState("");
  const err = verify.error instanceof ApiError ? verify.error : null;
  const ready = useRecovery ? code.replace(/[^a-z0-9]/gi, "").length === 10 : code.length === 6;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        verify.mutate(code, { onSuccess: onVerified, onError: () => setCode("") });
      }}
    >
      <p className="auth-intro">{useRecovery ? t.recoveryVerifyIntro : t.verifyIntro}</p>
      {err && (
        <div className="form-error" role="alert">
          {errorText(ta, err.code, err.message)}
        </div>
      )}
      <div className="field">
        <label htmlFor="code">{useRecovery ? t.recoveryLabel : t.codeLabel}</label>
        {useRecovery ? (
          <input id="code" value={code} onChange={(e) => setCode(e.target.value)} autoComplete="off" autoCapitalize="none" spellCheck={false} required />
        ) : (
          <CodeInput id="code" value={code} onChange={setCode} invalid={!!err} />
        )}
      </div>
      <button type="submit" className="btn btn-primary auth-submit" disabled={!ready || verify.isPending}>
        {verify.isPending ? t.verifying : t.verify}
      </button>
      <div className="auth-links">
        <button
          type="button"
          className="link-button"
          onClick={() => {
            setUseRecovery((v) => !v);
            setCode("");
            verify.reset();
          }}
        >
          {useRecovery ? t.useApp : t.useRecovery}
        </button>
      </div>
    </form>
  );
}

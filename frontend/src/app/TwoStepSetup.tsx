import { useEffect, useRef, useState } from "react";
import type { AccountStrings } from "../i18n/account";
import type { AuthStrings } from "../i18n/auth";
import { errorText } from "../i18n/auth";
import { useEnableMfa, useStartMfaSetup } from "../lib/account";
import { ApiError } from "../lib/api";

/** Digits only, at most 6: what an authenticator shows. */
const cleanCode = (v: string) => v.replace(/\D/g, "").slice(0, 6);

export function CodeInput({ id, value, onChange, invalid }: { id: string; value: string; onChange: (v: string) => void; invalid?: boolean }) {
  return (
    <input
      id={id}
      className="code-input"
      value={value}
      onChange={(e) => onChange(cleanCode(e.target.value))}
      inputMode="numeric"
      autoComplete="one-time-code"
      pattern="[0-9]{6}"
      maxLength={6}
      aria-invalid={invalid || undefined}
      required
    />
  );
}

/** Scan the QR code, confirm one code; hands back the recovery codes. */
export function TwoStepSetup({ t, ta, required, onEnabled }: { t: AccountStrings; ta: AuthStrings; required: boolean; onEnabled: (codes: string[]) => void }) {
  const start = useStartMfaSetup();
  const enable = useEnableMfa();
  const [code, setCode] = useState("");
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    start.mutate();
  }, [start]);

  const err = enable.error instanceof ApiError ? enable.error : start.error instanceof ApiError ? start.error : null;

  return (
    <form
      className="two-step-setup"
      onSubmit={(e) => {
        e.preventDefault();
        enable.mutate(code, { onSuccess: (r) => onEnabled(r.recovery_codes), onError: () => setCode("") });
      }}
    >
      <p className="auth-intro">{required ? t.setupIntroRequired : t.setupIntro}</p>
      {err && (
        <div className="form-error" role="alert">
          {errorText(ta, err.code, err.message)}
        </div>
      )}
      <ol className="setup-steps">
        <li>{t.setupStep1}</li>
        <li>
          {t.setupStep2}
          {start.data ? (
            <>
              <img className="qr" src={start.data.qr_svg} alt="QR code" width={180} height={180} />
              <span className="field-hint">{t.cantScan}</span>
              <code className="secret-key">{start.data.secret.replace(/(.{4})/g, "$1 ").trim()}</code>
            </>
          ) : (
            <div className="qr qr-loading" aria-busy="true" />
          )}
        </li>
        <li>
          <label htmlFor="setup-code">{t.setupStep3}</label>
          <CodeInput id="setup-code" value={code} onChange={setCode} invalid={!!enable.error} />
        </li>
      </ol>
      <button type="submit" className="btn btn-primary auth-submit" disabled={!start.data || code.length !== 6 || enable.isPending}>
        {enable.isPending ? t.turningOn : t.turnOn}
      </button>
    </form>
  );
}

export function RecoveryCodes({ t, codes, onDone }: { t: AccountStrings; codes: string[]; onDone: () => void }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="recovery">
      <h2>{t.recoveryTitle}</h2>
      <p className="auth-intro">{t.recoveryIntro}</p>
      <ul className="recovery-codes" aria-label={t.recoveryTitle}>
        {codes.map((c) => (
          <li key={c}>{c}</li>
        ))}
      </ul>
      <div className="recovery-actions">
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => {
            navigator.clipboard?.writeText(codes.join("\n"));
            setCopied(true);
          }}
        >
          {copied ? t.copied : t.copyCodes}
        </button>
        <button type="button" className="btn btn-primary" onClick={onDone}>
          {t.savedContinue}
        </button>
      </div>
    </div>
  );
}

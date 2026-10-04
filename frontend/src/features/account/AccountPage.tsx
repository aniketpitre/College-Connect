import { useState } from "react";
import { Link, useNavigate } from "react-router";
import "../../app/auth.css";
import LanguageToggle from "../../app/LanguageToggle";
import PasswordInput from "../../app/PasswordInput";
import { RecoveryCodes, TwoStepSetup } from "../../app/TwoStepSetup";
import { Modal } from "../../components/Modal";
import { StatusBadge } from "../../components/StatusBadge";
import { ACCOUNT_STRINGS, type AccountStrings } from "../../i18n/account";
import { AUTH_STRINGS, errorText } from "../../i18n/auth";
import {
  describeDevice,
  useDisableMfa,
  useEndSession,
  useLoginHistory,
  useLogoutEverywhere,
  useMfaStatus,
  useNewRecoveryCodes,
  useSessions,
} from "../../lib/account";
import { ApiError } from "../../lib/api";
import { useLanguage } from "../../lib/language";
import type { Language } from "../../lib/types";
import "./account.css";

const LOCALES: Record<Language, string> = { en: "en-IN", hi: "hi-IN", mr: "mr-IN" };

/** Password, 2-step verification, signed-in devices and recent activity, for every kind of account. */
export default function AccountPage() {
  const [language, setLanguage] = useLanguage();
  const t = ACCOUNT_STRINGS[language];
  const when = (iso: string) =>
    new Date(iso).toLocaleString(LOCALES[language], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

  return (
    <div className="account" lang={language}>
      <div className="page-head">
        <h1>{t.accountTitle}</h1>
        <LanguageToggle value={language} onChange={setLanguage} />
      </div>

      <section className="account-card">
        <h2>{t.passwordSection}</h2>
        <p className="muted">{t.passwordHelp}</p>
        <Link className="btn btn-ghost" to="/app/change-password">
          {t.changePassword}
        </Link>
      </section>

      <TwoStepSection t={t} language={language} />
      <DevicesSection t={t} when={when} />
      <ActivitySection t={t} when={when} />
    </div>
  );
}

function TwoStepSection({ t, language }: { t: AccountStrings; language: Language }) {
  const status = useMfaStatus();
  const disable = useDisableMfa();
  const newCodes = useNewRecoveryCodes();
  const [settingUp, setSettingUp] = useState(false);
  const [codes, setCodes] = useState<string[] | null>(null);
  const [confirming, setConfirming] = useState<"off" | "codes" | null>(null);
  const [password, setPassword] = useState("");
  const ta = AUTH_STRINGS[language];
  const s = status.data;
  const action = confirming === "off" ? disable : newCodes;
  const err = action.error instanceof ApiError ? action.error : null;
  const closeConfirm = () => {
    setConfirming(null);
    setPassword("");
    disable.reset();
    newCodes.reset();
  };

  return (
    <section className="account-card">
      <div className="account-card-head">
        <h2>{t.twoStepTitle}</h2>
        {s && (s.enabled ? <StatusBadge tone="success">{t.on}</StatusBadge> : <StatusBadge tone="warning">{t.off}</StatusBadge>)}
      </div>
      {s?.required && <p className="muted">{t.requiredForRole}</p>}
      {s && !s.enabled && <p className="muted">{t.twoStepOffHelp}</p>}
      {s?.enabled && <p className="muted">{t.recoveryLeft(s.recovery_codes_left)}</p>}
      <div className="account-actions">
        {s && !s.enabled && (
          <button type="button" className="btn btn-primary" onClick={() => setSettingUp(true)}>
            {t.setUp}
          </button>
        )}
        {s?.enabled && (
          <button type="button" className="btn btn-ghost" onClick={() => setConfirming("codes")}>
            {t.newCodes}
          </button>
        )}
        {s?.enabled && !s.required && (
          <button type="button" className="btn btn-ghost" onClick={() => setConfirming("off")}>
            {t.turnOff}
          </button>
        )}
      </div>

      <Modal open={settingUp || codes !== null} title={t.twoStepTitle} onClose={() => (setSettingUp(false), setCodes(null))}>
        {codes ? (
          <RecoveryCodes t={t} codes={codes} onDone={() => (setSettingUp(false), setCodes(null))} />
        ) : (
          settingUp && <TwoStepSetup t={t} ta={ta} required={false} onEnabled={setCodes} />
        )}
      </Modal>

      <Modal open={confirming !== null} title={confirming === "off" ? t.turnOff : t.newCodes} onClose={closeConfirm}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (confirming === "off") disable.mutate(password, { onSuccess: closeConfirm });
            else
              newCodes.mutate(password, {
                onSuccess: (r) => {
                  closeConfirm();
                  setCodes(r.recovery_codes);
                },
              });
          }}
        >
          {err && (
            <div className="form-error" role="alert">
              {errorText(ta, err.code, err.message)}
            </div>
          )}
          <div className="field">
            <label htmlFor="confirm-password">{t.passwordToConfirm}</label>
            <PasswordInput id="confirm-password" value={password} onChange={setPassword} autoComplete="current-password" showLabel={ta.show} hideLabel={ta.hide} />
          </div>
          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={closeConfirm}>
              {t.cancel}
            </button>
            <button type="submit" className="btn btn-primary" disabled={!password || action.isPending}>
              {t.confirm}
            </button>
          </div>
        </form>
      </Modal>
    </section>
  );
}

function DevicesSection({ t, when }: { t: AccountStrings; when: (iso: string) => string }) {
  const sessions = useSessions();
  const end = useEndSession();
  const everywhere = useLogoutEverywhere();
  const navigate = useNavigate();

  return (
    <section className="account-card">
      <h2>{t.devicesSection}</h2>
      <ul className="device-list">
        {(sessions.data ?? []).map((s) => (
          <li key={s.id}>
            <div>
              <div className="device-name">
                {describeDevice(s.user_agent) ?? t.unknownDevice}
                {s.current && <StatusBadge tone="info">{t.thisDevice}</StatusBadge>}
              </div>
              <div className="muted device-meta">
                {t.lastActive}: {when(s.last_seen_at)}
                {s.ip ? ` · ${s.ip}` : ""}
              </div>
            </div>
            {!s.current && (
              <button type="button" className="link-btn" disabled={end.isPending} onClick={() => end.mutate(s.id)}>
                {t.signOutDevice}
              </button>
            )}
          </li>
        ))}
      </ul>
      <button
        type="button"
        className="btn btn-ghost"
        disabled={everywhere.isPending}
        onClick={() => everywhere.mutate(undefined, { onSettled: () => navigate("/login", { replace: true }) })}
      >
        {t.signOutEverywhere}
      </button>
    </section>
  );
}

function ActivitySection({ t, when }: { t: AccountStrings; when: (iso: string) => string }) {
  const history = useLoginHistory();
  const rows = history.data ?? [];
  return (
    <section className="account-card">
      <h2>{t.activitySection}</h2>
      {rows.length === 0 && !history.isLoading && <p className="muted">{t.noActivity}</p>}
      <ul className="activity-list">
        {rows.map((e, i) => (
          <li key={`${e.at}-${i}`} className={e.action.endsWith("failed") || e.action.endsWith("locked") ? "warn" : ""}>
            <span>{t.actions[e.action] ?? e.action}</span>
            <span className="muted nowrap">
              {when(e.at)}
              {e.ip ? ` · ${e.ip}` : ""}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

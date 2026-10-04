import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";
import { PRIVACY_NOTICE, PRIVACY_VERSION, WELCOME_STRINGS } from "../../i18n/privacy";
import { ApiError, apiFetch } from "../../lib/api";
import { ME_KEY, useMe } from "../../lib/auth";
import { useLanguage } from "../../lib/language";
import type { Language } from "../../lib/types";
import AuthShell from "../AuthShell";

interface Status {
  privacy_version: string;
  phone: string | null;
  email: string | null;
  under_18: boolean;
  guardian_consent: boolean;
  done: boolean;
}

const LANGUAGES: { id: Language; name: string; sample: string }[] = [
  { id: "en", name: "English", sample: "Fees, notices and results" },
  { id: "hi", name: "हिंदी", sample: "फ़ीस, सूचनाएं और परिणाम" },
  { id: "mr", name: "मराठी", sample: "शुल्क, सूचना आणि निकाल" },
];

/** A student's first sign-in after setting a password: contact → privacy notice → language. */
export default function WelcomePage() {
  const [language, setLanguage] = useLanguage();
  const status = useQuery({ queryKey: ["me", "onboarding"], queryFn: () => apiFetch<Status>("/me/onboarding") });
  return (
    <AuthShell language={language} onLanguage={setLanguage}>
      {status.error && <div className="form-error">{status.error.message}</div>}
      {status.data ? <Wizard status={status.data} /> : !status.error && <p className="auth-intro">…</p>}
    </AuthShell>
  );
}

function Wizard({ status }: { status: Status }) {
  const [language, setLanguage] = useLanguage();
  const t = WELCOME_STRINGS[language];
  const notice = PRIVACY_NOTICE[language];
  const { data: me } = useMe();
  const [step, setStep] = useState(0);
  const [phone, setPhone] = useState(status.phone ?? "");
  const [email, setEmail] = useState(status.email ?? "");
  const [accepted, setAccepted] = useState(false);
  const qc = useQueryClient();
  const navigate = useNavigate();

  const finish = useMutation({
    mutationFn: () =>
      apiFetch<Status>("/me/onboarding", {
        method: "POST",
        body: JSON.stringify({ phone, email: email.trim() || null, accept_privacy: accepted, privacy_version: PRIVACY_VERSION, language }),
      }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ME_KEY });
      navigate("/app", { replace: true });
    },
    onError: (e) => {
      if (e instanceof ApiError && (e.field === "phone" || e.field === "email")) setStep(0); // back to the field to fix
    },
  });
  const err = finish.error instanceof ApiError ? finish.error : null;

  return (
    <>
      <h1>{t.title}</h1>
      <p className="auth-intro">{me?.name}</p>
      <ol className="wizard-steps" aria-label="Steps">
        {t.steps.map((label, i) => (
          <li key={label} className={i === step ? "current" : i < step ? "done" : ""} aria-current={i === step ? "step" : undefined}>
            {label}
          </li>
        ))}
      </ol>
      {err && !["phone", "email"].includes(err.field ?? "") && <div className="form-error">{err.message}</div>}

      {step === 0 && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setStep(1);
          }}
        >
          <p className="auth-intro">{t.contactIntro}</p>
          <div className="field">
            <label htmlFor="w-phone">{t.phone}</label>
            <input id="w-phone" type="tel" inputMode="tel" value={phone} onChange={(e) => setPhone(e.target.value)} autoComplete="tel" required />
            {err?.field === "phone" && <span className="field-error">{err.message}</span>}
          </div>
          <div className="field">
            <label htmlFor="w-email">{t.email}</label>
            <input id="w-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
            <span className="field-hint">{t.emailHint}</span>
            {err?.field === "email" && <span className="field-error">{err.message}</span>}
          </div>
          <button type="submit" className="btn btn-primary auth-submit" disabled={!phone.trim()}>
            {t.next}
          </button>
        </form>
      )}

      {step === 1 && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setStep(2);
          }}
        >
          <div className="privacy-notice" tabIndex={0} aria-label={notice.title}>
            <h2>{notice.title}</h2>
            <p>{notice.intro}</p>
            {notice.sections.map((s) => (
              <section key={s.title}>
                <h3>{s.title}</h3>
                <p>{s.body}</p>
              </section>
            ))}
          </div>
          {status.under_18 && !status.guardian_consent && <div className="auth-success">{t.under18}</div>}
          <label className="check-label accept-check">
            <input type="checkbox" checked={accepted} onChange={(e) => setAccepted(e.target.checked)} />
            <span>{t.accept}</span>
          </label>
          <div className="wizard-actions">
            <button type="button" className="btn btn-ghost" onClick={() => setStep(0)}>
              {t.back}
            </button>
            <button type="submit" className="btn btn-primary" disabled={!accepted}>
              {t.next}
            </button>
          </div>
        </form>
      )}

      {step === 2 && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            finish.mutate();
          }}
        >
          <p className="auth-intro">{t.languageIntro}</p>
          <div className="language-cards" role="radiogroup">
            {LANGUAGES.map((l) => (
              <label key={l.id} className={`language-card${language === l.id ? " selected" : ""}`} lang={l.id}>
                <input type="radio" name="language" value={l.id} checked={language === l.id} onChange={() => setLanguage(l.id)} />
                <b>{l.name}</b>
                <span className="muted">{l.sample}</span>
              </label>
            ))}
          </div>
          <div className="wizard-actions">
            <button type="button" className="btn btn-ghost" onClick={() => setStep(1)}>
              {t.back}
            </button>
            <button type="submit" className="btn btn-primary" disabled={finish.isPending}>
              {finish.isPending ? t.finishing : t.finish}
            </button>
          </div>
        </form>
      )}
    </>
  );
}

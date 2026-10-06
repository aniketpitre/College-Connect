import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import { ADMISSION_STRINGS } from "../../i18n/admissions";
import { ApiError } from "../../lib/api";
import { useApplyCode, useApplyVerify, useAdmissionOptions, useEnquiry, useStartApplication } from "../../lib/admissions";
import { useMe } from "../../lib/auth";
import { useLanguage } from "../../lib/language";
import { formatPaise } from "../../lib/money";
import "../auth.css";
import LanguageToggle from "../LanguageToggle";

/** Public: what is open, start or resume an application (sign-in code by email), or leave a number. */
export default function ApplyPage() {
  const [language, setLanguage] = useLanguage();
  const t = ADMISSION_STRINGS[language];
  const { data: me } = useMe();
  const options = useAdmissionOptions();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"new" | "resume">("new");
  const [form, setForm] = useState({ cycle_id: "", name: "", phone: "", email: "" });
  const [code, setCode] = useState("");
  const start = useStartApplication();
  const resume = useApplyCode();
  const verify = useApplyVerify();
  const sent = mode === "new" ? start.isSuccess : resume.isSuccess;
  const locale = language === "en" ? "en-IN" : `${language}-IN`;
  const day = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(locale, { day: "numeric", month: "long", year: "numeric" });
  const cycles = options.data?.cycles ?? [];
  const cycleId = form.cycle_id || cycles[0]?.id || "";

  if (me?.kind === "applicant" && !verify.isPending) return <Navigate to="/app/application" replace />;
  const failure = verify.error ?? (mode === "new" ? start.error : resume.error);
  const error = failure instanceof ApiError ? (failure.code === "invalid_code" ? t.codeWrong : failure.message) : null;

  return (
    <div className="auth-page apply-page" lang={language}>
      <div className="auth-card apply-card">
        <div className="auth-card-top">
          <Link className="brand" to="/">
            <span className="seal">CC</span> CollegeConnect
          </Link>
          <LanguageToggle value={language} onChange={setLanguage} />
        </div>
        <h1>{t.applyTitle}</h1>
        <p className="muted">{t.applyIntro}</p>

        <h2 className="subhead">{t.openNow}</h2>
        {cycles.length === 0 && options.data && <p className="muted">{t.noOpen}</p>}
        {cycles.map((c) => (
          <div key={c.id} className="apply-cycle">
            <b>{c.name}</b>
            <div className="muted small">
              {t.lastDate(day(c.apply_until))}
              {c.application_fee > 0 && ` · ${t.appFee(formatPaise(c.application_fee))}`}
            </div>
            <ul className="apply-programmes">
              {c.programmes.map((p) => (
                <li key={p.programme_id}>
                  {p.code} · {p.name} <span className="muted small">({t.seats(p.seats)})</span>
                </li>
              ))}
            </ul>
          </div>
        ))}

        {cycles.length > 0 && (
          <form
            className="apply-start"
            onSubmit={(e) => {
              e.preventDefault();
              if (sent) {
                verify.mutate({ phone: form.phone.trim(), code }, { onSuccess: () => navigate("/app/application", { replace: true }) });
              } else if (mode === "new") {
                start.mutate({ ...form, cycle_id: cycleId, phone: form.phone.trim(), email: form.email.trim() });
              } else {
                resume.mutate(form.phone.trim());
              }
            }}
          >
            <h2 className="subhead">{mode === "new" ? t.startTitle : t.alreadyApplied}</h2>
            {error && (
              <div className="form-error" role="alert">
                {error}
              </div>
            )}
            {mode === "new" && cycles.length > 1 && (
              <div className="field">
                <label htmlFor="ap-cycle">{t.applyTitle}</label>
                <select id="ap-cycle" value={cycleId} onChange={(e) => setForm({ ...form, cycle_id: e.target.value })}>
                  {cycles.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
            {mode === "new" && (
              <div className="field">
                <label htmlFor="ap-name">{t.name}</label>
                <input id="ap-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} disabled={sent} required />
              </div>
            )}
            <div className="field">
              <label htmlFor="ap-phone">{t.mobile}</label>
              <input id="ap-phone" type="tel" inputMode="numeric" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} disabled={sent} required />
            </div>
            {mode === "new" && (
              <div className="field">
                <label htmlFor="ap-email">{t.email}</label>
                <input id="ap-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} disabled={sent} required />
                <span className="field-hint">{t.emailHint}</span>
              </div>
            )}
            {sent && (
              <>
                <p className="field-hint" role="status">
                  {t.codeSent}
                </p>
                <div className="field">
                  <label htmlFor="ap-code">{t.code}</label>
                  <input id="ap-code" inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} required />
                </div>
              </>
            )}
            <button type="submit" className="btn btn-primary auth-submit" disabled={start.isPending || resume.isPending || verify.isPending || (sent && code.length !== 6)}>
              {start.isPending || resume.isPending ? t.sending : sent ? t.continue : t.sendCode}
            </button>
            <div className="auth-links">
              <button
                type="button"
                className="link-button"
                onClick={() => {
                  setMode(mode === "new" ? "resume" : "new");
                  setCode("");
                  start.reset();
                  resume.reset();
                  verify.reset();
                }}
              >
                {mode === "new" ? t.alreadyApplied : t.newApplication}
              </button>
            </div>
          </form>
        )}
        <EnquiryForm language={language} programmes={cycles.flatMap((c) => c.programmes)} />
      </div>
    </div>
  );
}

function EnquiryForm({ language, programmes }: { language: keyof typeof ADMISSION_STRINGS; programmes: { programme_id: string; code: string; name: string }[] }) {
  const t = ADMISSION_STRINGS[language];
  const enquiry = useEnquiry();
  const [form, setForm] = useState({ name: "", phone: "", programme_id: "", message: "" });
  if (enquiry.isSuccess)
    return (
      <p className="auth-success" role="status">
        {t.enquirySent}
      </p>
    );
  return (
    <form
      className="apply-enquiry"
      onSubmit={(e) => {
        e.preventDefault();
        enquiry.mutate({ ...form, programme_id: form.programme_id || undefined });
      }}
    >
      <h2 className="subhead">{t.enquiryTitle}</h2>
      <p className="muted small">{t.enquiryIntro}</p>
      {enquiry.error && <p className="form-error">{enquiry.error.message}</p>}
      <div className="field">
        <label htmlFor="eq-name">{t.name}</label>
        <input id="eq-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
      </div>
      <div className="field">
        <label htmlFor="eq-phone">{t.mobile}</label>
        <input id="eq-phone" type="tel" inputMode="numeric" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} required />
      </div>
      <div className="field">
        <label htmlFor="eq-prog">{t.programme}</label>
        <select id="eq-prog" value={form.programme_id} onChange={(e) => setForm({ ...form, programme_id: e.target.value })}>
          <option value="">{t.anyProgramme}</option>
          {programmes.map((p) => (
            <option key={p.programme_id} value={p.programme_id}>
              {p.code} · {p.name}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor="eq-msg">{t.message}</label>
        <textarea id="eq-msg" rows={2} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} />
      </div>
      <button type="submit" className="btn btn-ghost" disabled={enquiry.isPending}>
        {t.sendEnquiry}
      </button>
    </form>
  );
}

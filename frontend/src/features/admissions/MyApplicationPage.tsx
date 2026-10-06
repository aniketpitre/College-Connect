import { useState } from "react";
import LanguageToggle from "../../app/LanguageToggle";
import { StatusBadge } from "../../components/StatusBadge";
import { ADMISSION_STRINGS } from "../../i18n/admissions";
import { STUDENT_STRINGS } from "../../i18n/student";
import { API_V1 } from "../../lib/api";
import {
  useAdmissionOptions,
  useMyApplication,
  usePayApplicationFee,
  useSaveApplication,
  useSubmitApplication,
  useUploadApplicationDoc,
  type Application,
} from "../../lib/admissions";
import { useLanguage } from "../../lib/language";
import { formatPaise } from "../../lib/money";
import "./admissions.css";

type Flat = Record<string, string>;

const FIELDS = {
  personal: ["name", "mother_name", "gender", "dob", "category_id"],
  contact: ["phone", "email", "address.line", "address.city", "address.district", "address.pincode"],
  guardian: ["guardian.name", "guardian.relation", "guardian.phone"],
  education: ["previous_education.exam", "previous_education.board", "previous_education.year", "previous_education.percentage"],
};

function flatten(a: Application): Flat {
  const out: Flat = { programme_id: a.programme_id ?? "" };
  for (const [k, v] of Object.entries(a.personal)) {
    if (v && typeof v === "object") for (const [k2, v2] of Object.entries(v)) out[`${k}.${k2}`] = v2 == null ? "" : String(v2);
    else out[k] = v == null ? "" : String(v);
  }
  return out;
}

function toBody(f: Flat): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  const nested: Record<string, Record<string, unknown>> = {};
  for (const [k, v] of Object.entries(f)) {
    if (k === "prn") continue;
    const value = v.trim();
    if (k.includes(".")) {
      const [group, field] = k.split(".");
      if (!value) continue;
      nested[group] = { ...nested[group], [field]: field === "year" ? Number(value) : field === "percentage" ? Number(value) : value };
    } else if (value) body[k] = value;
  }
  return { ...body, ...nested };
}

/** The applicant's own application (spec R5, R15): form, documents, fee, submit, then status and offer. */
export default function MyApplicationPage() {
  const [language, setLanguage] = useLanguage();
  const t = ADMISSION_STRINGS[language];
  const S = STUDENT_STRINGS[language];
  const app = useMyApplication();
  const options = useAdmissionOptions();
  const save = useSaveApplication();
  const submit = useSubmitApplication();
  const pay = usePayApplicationFee();
  const [draft, setDraft] = useState<Flat | null>(null);
  const a = app.data;
  if (app.error) return <p className="form-error">{app.error.message}</p>;
  if (!a) return <p className="muted">…</p>;
  const values = draft ?? flatten(a);
  const cycle = options.data?.cycles.find((c) => c.id === a.cycle_id);
  const locale = language === "en" ? "en-IN" : `${language}-IN`;
  const day = (iso: string) => new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString(locale, { day: "numeric", month: "long", year: "numeric" });
  const set = (k: string, v: string) => setDraft({ ...values, [k]: v });
  const field = (k: string) => {
    const id = `app-${k.replace(".", "-")}`;
    const label = S.fields[k] ?? k;
    if (k === "gender")
      return (
        <div className="field" key={k}>
          <label htmlFor={id}>{label}</label>
          <select id={id} value={values[k] ?? ""} onChange={(e) => set(k, e.target.value)} disabled={!a.can_edit}>
            <option value="">{t.choose}</option>
            {Object.entries(S.genders).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </div>
      );
    if (k === "category_id")
      return (
        <div className="field" key={k}>
          <label htmlFor={id}>{label}</label>
          <select id={id} value={values[k] ?? ""} onChange={(e) => set(k, e.target.value)} disabled={!a.can_edit}>
            <option value="">{t.choose}</option>
            {(options.data?.categories ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.code} · {c.name}
              </option>
            ))}
          </select>
        </div>
      );
    return (
      <div className="field" key={k}>
        <label htmlFor={id}>{label}</label>
        <input
          id={id}
          type={k === "dob" ? "date" : k.endsWith("percentage") || k.endsWith("year") ? "number" : k === "email" ? "email" : "text"}
          step={k.endsWith("percentage") ? "0.01" : undefined}
          value={values[k] ?? ""}
          onChange={(e) => set(k, e.target.value)}
          disabled={!a.can_edit}
        />
      </div>
    );
  };
  const p = a.personal;
  const missing = [
    ...(["name", "dob", "gender", "phone", "email", "category_id"] as const).filter((k) => !p[k]).map((k) => t.missing[k]),
    ...(a.programme_id ? [] : [t.missing.programme_id]),
    ...(p.previous_education?.percentage == null ? [t.missing.previous_education] : []),
    ...a.required_documents.filter((d) => !a.documents.some((x) => x.type === d)).map((d) => S.docTypes[d] ?? d),
    ...(a.fee.status === "unpaid" ? [t.missing.fee] : []),
  ];
  const message =
    a.status === "returned" && a.reason
      ? t.returned(a.reason)
      : a.status === "rejected" && a.reason
        ? t.rejected(a.reason)
        : a.status === "waiting" && a.rank
          ? t.waiting(a.rank)
          : a.status === "offered" && a.offer
            ? t.offer(a.offer.seat_label, day(a.offer.accept_by))
            : a.status === "admitted" && a.prn
              ? t.admitted(a.prn)
              : a.status === "lapsed"
                ? t.lapsed
                : null;

  return (
    <div lang={language} className="my-application">
      <div className="page-head">
        <div>
          <div className="eyebrow">{a.cycle_name}</div>
          <h1>{t.appTitle}</h1>
        </div>
        <LanguageToggle value={language} onChange={setLanguage} />
      </div>
      <div className="badge-row">
        <StatusBadge tone={["admitted", "verified", "offered"].includes(a.status) ? "success" : ["returned", "rejected", "lapsed"].includes(a.status) ? "danger" : "warning"}>
          {t.statuses[a.status] ?? a.status_label}
        </StatusBadge>
        {a.number && (
          <span className="muted">
            {t.number} {a.number}
          </span>
        )}
      </div>
      {message && <div className={`attention-card ${["returned", "rejected", "lapsed"].includes(a.status) ? "danger" : "info"} app-message`}>{message}</div>}
      {!a.can_edit && ["draft", "returned"].includes(a.status) && <p className="form-error">{t.closed}</p>}

      <form
        className="card app-form"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate(toBody(values), { onSuccess: () => setDraft(null) });
        }}
      >
        <h2 className="card-title">{S.sections.academic}</h2>
        <div className="field">
          <label htmlFor="app-programme">{t.programme}</label>
          <select id="app-programme" value={values.programme_id ?? ""} onChange={(e) => set("programme_id", e.target.value)} disabled={!a.can_edit}>
            <option value="">{t.choose}</option>
            {(cycle?.programmes ?? []).map((pr) => (
              <option key={pr.programme_id} value={pr.programme_id}>
                {pr.code} · {pr.name}
              </option>
            ))}
            {!cycle && a.programme_id && <option value={a.programme_id}>{a.programme}</option>}
          </select>
        </div>
        <h2 className="card-title">{S.sections.personal}</h2>
        <div className="app-grid">{FIELDS.personal.map(field)}</div>
        <h2 className="card-title">{S.sections.contact}</h2>
        <div className="app-grid">{FIELDS.contact.map(field)}</div>
        <h2 className="card-title">{S.sections.guardian}</h2>
        <div className="app-grid">{FIELDS.guardian.map(field)}</div>
        <h2 className="card-title">{S.sections.education}</h2>
        <div className="app-grid">{FIELDS.education.map(field)}</div>
        {save.error && <p className="form-error">{save.error.message}</p>}
        {a.can_edit && (
          <div className="row-actions">
            {save.isSuccess && !draft && <span className="muted small">{t.saved}</span>}
            <button type="submit" className="btn btn-primary" disabled={!draft || save.isPending}>
              {t.save}
            </button>
          </div>
        )}
      </form>

      <section className="card">
        <h2 className="card-title">{t.documentsTitle}</h2>
        <ul className="app-docs">
          {[...new Set([...a.required_documents, ...a.documents.map((d) => d.type)])].map((type) => (
            <DocRow key={type} type={type} app={a} language={language} />
          ))}
        </ul>
      </section>

      <section className="card">
        <h2 className="card-title">{t.feeTitle}</h2>
        {a.fee.status === "paid" && <p>{t.feePaid(a.fee.receipt_number ?? "")}</p>}
        {(a.fee.status === "waived" || a.fee.status === "not_needed") && <p>{t.feeWaived}</p>}
        {a.fee.status === "unpaid" && (
          <>
            <p>{t.feeDue(formatPaise(a.fee.amount))}</p>
            {options.data?.online_payment ? (
              <button type="button" className="btn btn-primary btn-sm" disabled={pay.isPending} onClick={() => pay.mutate(undefined)}>
                {t.payOnline}
              </button>
            ) : (
              <p className="muted small">{t.payAtOffice}</p>
            )}
            {pay.error && <p className="form-error">{pay.error.message}</p>}
          </>
        )}
      </section>

      {a.can_edit && (
        <section className="card">
          <h2 className="card-title">{t.submitTitle}</h2>
          <p className="muted small">{t.submitIntro}</p>
          {missing.length > 0 && (
            <p className="small">
              {t.stillNeeded} {missing.join(", ")}
            </p>
          )}
          {submit.error && <p className="form-error">{submit.error.message}</p>}
          <button type="button" className="btn btn-primary" disabled={missing.length > 0 || Boolean(draft) || submit.isPending} onClick={() => submit.mutate(undefined)}>
            {t.submit}
          </button>
        </section>
      )}
    </div>
  );
}

function DocRow({ type, app, language }: { type: string; app: Application; language: keyof typeof ADMISSION_STRINGS }) {
  const t = ADMISSION_STRINGS[language];
  const S = STUDENT_STRINGS[language];
  const upload = useUploadApplicationDoc();
  const doc = app.documents.find((d) => d.type === type);
  const id = `doc-${type}`;
  return (
    <li>
      <div>
        <b>{S.docTypes[type] ?? type}</b>
        <div className="muted small">
          {doc ? (
            <>
              <a href={`${API_V1}${doc.url}`} target="_blank" rel="noreferrer">
                {doc.filename}
              </a>{" "}
              · {S.docStatus[doc.status]}
              {doc.reason ? ` (${doc.reason})` : ""}
            </>
          ) : (
            t.notUploaded
          )}
        </div>
        {upload.error && <div className="form-error small">{upload.error.message}</div>}
      </div>
      {app.can_edit && (
        <label className="btn btn-ghost btn-sm file-button" htmlFor={id}>
          {doc ? t.replace : t.upload}
          <input
            id={id}
            type="file"
            accept=".pdf,.jpg,.jpeg,.png"
            aria-label={`${S.docTypes[type] ?? type}: ${doc ? t.replace : t.upload}`}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) upload.mutate({ type, file });
              e.target.value = "";
            }}
          />
        </label>
      )}
    </li>
  );
}

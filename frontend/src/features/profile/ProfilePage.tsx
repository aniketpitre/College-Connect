import { useState } from "react";
import LanguageToggle from "../../app/LanguageToggle";
import { Modal } from "../../components/Modal";
import { StatusBadge } from "../../components/StatusBadge";
import { CORRECTABLE, STUDENT_STRINGS, type StudentStrings } from "../../i18n/student";
import { ApiError } from "../../lib/api";
import { API_V1 } from "../../lib/api";
import { useLanguage } from "../../lib/language";
import { fileUrl, useCorrectionOptions, useMyRequests, useMyStudent, useRequestChange, useUpload, type ChangeRequest, type Student } from "../../lib/students";
import type { Language } from "../../lib/types";
import { DocumentList, UploadDocument } from "../students/Documents";
import { RecordView } from "../students/RecordView";
import "../students/students.css";

const NUMERIC = new Set(["previous_education.year", "previous_education.percentage"]);

/** The student's own record (spec R13 "My profile"): view, request corrections, upload documents. */
export default function ProfilePage() {
  const [language, setLanguage] = useLanguage();
  const T = STUDENT_STRINGS[language];
  const student = useMyStudent();
  const [asking, setAsking] = useState(false);
  const [sent, setSent] = useState(false);
  const s = student.data;

  if (student.error) return <p className="form-error">{student.error.message}</p>;
  if (!s) return <p className="muted">…</p>;

  return (
    <div lang={language}>
      <div className="page-head">
        <h1>{T.profileTitle}</h1>
        <LanguageToggle value={language} onChange={setLanguage} />
      </div>
      <div className="student-head">
        <MyPhoto s={s} label={T.changePhoto} />
        <div className="student-head-text">
          <h2 className="profile-name">{s.name}</h2>
          <div className="muted">
            PRN {s.prn} · {[s.programme_code, s.year_label, s.division].filter(Boolean).join(" · ")}
          </div>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => (setSent(false), setAsking(true))}>
          {T.requestCorrection}
        </button>
      </div>
      {sent && (
        <div className="auth-success" role="status">
          {T.requestSent}
        </div>
      )}

      <RecordView s={s} lang={language} />

      <h2 className="subhead">{T.sections.documents}</h2>
      <DocumentList docs={s.documents} lang={language} />
      <UploadDocument base="/me/student" lang={language} />

      <h2 className="subhead">{T.myRequests}</h2>
      <MyRequests T={T} language={language} />

      <h2 className="subhead">{T.myData.title}</h2>
      <p className="muted">{T.myData.text}</p>
      <a className="btn btn-ghost" href={`${API_V1}/me/data-export`} download>
        {T.myData.button}
      </a>

      {asking && <CorrectionModal s={s} T={T} onClose={() => setAsking(false)} onSent={() => (setAsking(false), setSent(true))} />}
    </div>
  );
}

function MyPhoto({ s, label }: { s: Student; label: string }) {
  const upload = useUpload("/me/student");
  return (
    <div className="photo-box">
      {s.photo_url ? <img src={fileUrl(s.photo_url)} alt="" /> : <span className="photo-empty">{s.name.slice(0, 1)}</span>}
      <label className="photo-change">
        {upload.isPending ? "…" : label}
        <input type="file" accept="image/jpeg,image/png" hidden onChange={(e) => e.target.files?.[0] && upload.mutate({ kind: "photo", file: e.target.files[0] })} />
      </label>
      {upload.error && <span className="field-error">{upload.error.message}</span>}
    </div>
  );
}

/** What the student asked, shown in their language. */
function describe(field: string, value: unknown, T: StudentStrings, categories: { id: string; code: string }[]): string {
  if (value === null || value === undefined || value === "") return T.notSet;
  if (field === "category_id") return categories.find((c) => c.id === value)?.code ?? "";
  if (field === "gender") return T.genders[String(value)] ?? String(value);
  if (typeof value === "object")
    return Object.entries(value as Record<string, unknown>)
      .filter(([, v]) => v !== null && v !== "")
      .map(([k, v]) => `${T.fields[`${field}.${k}`] ?? k}: ${v}`)
      .join(", ");
  return String(value);
}

function MyRequests({ T, language }: { T: StudentStrings; language: Language }) {
  const requests = useMyRequests();
  const options = useCorrectionOptions();
  const tone = (r: ChangeRequest) => (r.status === "approved" ? "success" : r.status === "rejected" ? "danger" : "warning");
  if (!requests.data?.length) return <p className="muted">{T.noRequests}</p>;
  return (
    <ul className="doc-list">
      {requests.data.map((r) => (
        <li key={r.id}>
          <div>
            <div className="doc-name">
              {Object.keys(r.changes)
                .map((f) => T.fields[f] ?? T.sections[f as keyof StudentStrings["sections"]] ?? f)
                .join(", ")}
              <StatusBadge tone={tone(r)}>{T.requestStatus[r.status]}</StatusBadge>
            </div>
            <div className="muted doc-meta">
              {Object.entries(r.changes)
                .map(([f, v]) => describe(f, v, T, options.data?.categories ?? []))
                .join(" · ")}{" "}
              · {new Date(r.created_at).toLocaleDateString(language === "en" ? "en-IN" : `${language}-IN`)}
            </div>
            {r.decision_reason && (
              <div className={r.status === "rejected" ? "doc-reason" : "muted doc-meta"}>
                {T.officeNote}: {r.decision_reason}
              </div>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}

function CorrectionModal({ s, T, onClose, onSent }: { s: Student; T: StudentStrings; onClose: () => void; onSent: () => void }) {
  const [field, setField] = useState<string>(CORRECTABLE[0]);
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const send = useRequestChange();
  const options = useCorrectionOptions();
  const err = send.error instanceof ApiError ? send.error : null;

  const buildChanges = (): Record<string, unknown> => {
    const typed: unknown = NUMERIC.has(field) ? (value.trim() === "" ? null : Number(value)) : value.trim() || null;
    if (!field.includes(".")) return { [field]: typed };
    const [group, key] = field.split(".") as ["address" | "guardian" | "previous_education", string];
    const current = Object.fromEntries(Object.entries((s[group] ?? {}) as Record<string, unknown>).filter(([, v]) => v !== null && v !== ""));
    return { [group]: { ...current, [key]: typed } };
  };

  const input = () => {
    if (field === "gender")
      return (
        <select id="c-value" value={value} onChange={(e) => setValue(e.target.value)} required>
          <option value="">—</option>
          {Object.entries(T.genders).map(([v, label]) => (
            <option key={v} value={v}>
              {label}
            </option>
          ))}
        </select>
      );
    if (field === "category_id")
      return (
        <select id="c-value" value={value} onChange={(e) => setValue(e.target.value)} required>
          <option value="">—</option>
          {options.data?.categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.code} · {c.name}
            </option>
          ))}
        </select>
      );
    const type = field === "dob" ? "date" : NUMERIC.has(field) ? "number" : field.endsWith("email") ? "email" : field.endsWith("phone") ? "tel" : "text";
    return <input id="c-value" type={type} value={value} onChange={(e) => setValue(e.target.value)} required />;
  };

  return (
    <Modal open title={T.requestCorrection} onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          send.mutate({ changes: buildChanges(), reason: reason.trim() }, { onSuccess: onSent });
        }}
      >
        <p className="muted">{T.requestIntro}</p>
        {err && <div className="form-error">{err.message}</div>}
        <div className="field">
          <label htmlFor="c-field">{T.whatToCorrect}</label>
          <select
            id="c-field"
            value={field}
            onChange={(e) => {
              setField(e.target.value);
              setValue("");
            }}
          >
            {CORRECTABLE.map((f) => (
              <option key={f} value={f}>
                {T.fields[f]}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="c-value">{T.newValue}</label>
          {input()}
        </div>
        <div className="field">
          <label htmlFor="c-reason">{T.reason}</label>
          <input id="c-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder={T.reasonHint} minLength={5} required />
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            {T.cancel}
          </button>
          <button type="submit" className="btn btn-primary" disabled={send.isPending}>
            {send.isPending ? T.sending : T.send}
          </button>
        </div>
      </form>
    </Modal>
  );
}

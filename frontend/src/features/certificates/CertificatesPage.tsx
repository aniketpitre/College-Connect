import { useState } from "react";
import LanguageToggle from "../../app/LanguageToggle";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { EmptyState } from "../../components/EmptyState";
import { Modal } from "../../components/Modal";
import { StatusBadge } from "../../components/StatusBadge";
import { CERT_STRINGS, type CertStrings } from "../../i18n/certificates";
import { ApiError } from "../../lib/api";
import { hasPermission, isLearner, useMe } from "../../lib/auth";
import {
  myCertificatePdf,
  noDuesFor,
  staffCertificatePdf,
  useCertAction,
  useCertQueue,
  useCertTypes,
  useMyCertificates,
  useRequestCertificate,
  useRequestFor,
  useUpdateCertType,
  type CertRequest,
  type CertStatus,
  type CertType,
  type CertTypeInfo,
  type Due,
  type NewRequest,
} from "../../lib/certificates";
import { useLanguage } from "../../lib/language";
import { formatPaise } from "../../lib/money";
import { useStudents } from "../../lib/students";
import "../attendance/attendance.css";
import "../students/students.css";

const TONE: Record<CertStatus, "neutral" | "info" | "success" | "warning" | "danger"> = {
  requested: "info",
  verified: "info",
  signed: "warning",
  ready: "success",
  rejected: "danger",
};

export default function CertificatesPage() {
  const { data: me } = useMe();
  return isLearner(me) ? <StudentCertificates /> : <StaffCertificates />;
}

function RequestFields({ T, types, value, onChange }: { T: CertStrings; types: CertTypeInfo[]; value: NewRequest; onChange: (v: NewRequest) => void }) {
  const info = types.find((t) => t.type === value.type);
  return (
    <>
      <div className="field">
        <label htmlFor="c-type">{T.kind}</label>
        <select id="c-type" value={value.type} onChange={(e) => onChange({ ...value, type: e.target.value as CertType })}>
          {types.map((t) => (
            <option key={t.type} value={t.type}>
              {T.types[t.type] ?? t.name}
            </option>
          ))}
        </select>
        {info && <span className="field-hint">{T.readyIn(info.promised_days)}</span>}
      </div>
      <div className="field">
        <label htmlFor="c-purpose">{T.purpose}</label>
        <input id="c-purpose" placeholder={T.purposeHint} value={value.purpose} onChange={(e) => onChange({ ...value, purpose: e.target.value })} required minLength={3} />
      </div>
      {(value.type === "tc" || value.type === "migration") && (
        <div className="field">
          <label htmlFor="c-reason">{T.reasonForLeaving}</label>
          <input id="c-reason" value={value.reason_for_leaving ?? ""} onChange={(e) => onChange({ ...value, reason_for_leaving: e.target.value })} required />
        </div>
      )}
      {value.type === "noc" && (
        <div className="field-row">
          <div className="field">
            <label htmlFor="c-org">{T.organisation}</label>
            <input id="c-org" value={value.organisation ?? ""} onChange={(e) => onChange({ ...value, organisation: e.target.value })} required />
          </div>
          <div className="field">
            <label htmlFor="c-from">{T.from}</label>
            <input id="c-from" type="date" value={value.from_date ?? ""} onChange={(e) => onChange({ ...value, from_date: e.target.value })} required />
          </div>
          <div className="field">
            <label htmlFor="c-to">{T.to}</label>
            <input id="c-to" type="date" value={value.to_date ?? ""} onChange={(e) => onChange({ ...value, to_date: e.target.value })} required />
          </div>
        </div>
      )}
    </>
  );
}

function clean(v: NewRequest): NewRequest {
  return Object.fromEntries(Object.entries(v).filter(([, x]) => x !== "" && x !== undefined)) as unknown as NewRequest;
}

/** Students: ask for a certificate, follow it against the promised date, download it. */
function StudentCertificates() {
  const { data: me } = useMe();
  const [language, setLanguage] = useLanguage();
  const T = CERT_STRINGS[language];
  const data = useMyCertificates();
  const ask = useRequestCertificate();
  const [form, setForm] = useState<NewRequest>({ type: "bonafide", purpose: "" });
  const [sent, setSent] = useState(false);
  const locale = language === "en" ? "en-IN" : `${language}-IN`;
  const day = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(locale, { day: "numeric", month: "long" });
  const readOnly = Boolean(me?.read_only);
  return (
    <div lang={language}>
      <div className="page-head">
        <h1>{T.title}</h1>
        <LanguageToggle value={language} onChange={setLanguage} />
      </div>
      {readOnly && <div className="offline-banner">{T.readOnly}</div>}
      {!readOnly && data.data && (
        <form
          className="card exemption-form"
          onSubmit={(e) => {
            e.preventDefault();
            ask.mutate(clean(form), { onSuccess: () => (setSent(true), setForm({ type: form.type, purpose: "" })) });
          }}
        >
          <h2 className="subhead">{T.ask}</h2>
          {ask.error && <div className="form-error">{ask.error.message}</div>}
          {sent && (
            <div className="auth-success" role="status">
              {T.sent}
            </div>
          )}
          <RequestFields T={T} types={data.data.types} value={form} onChange={(v) => (setSent(false), setForm(v))} />
          {(form.type === "tc" || form.type === "migration") && <NoDues T={T} dues={data.data.no_dues} day={day} />}
          <button type="submit" className="btn btn-primary" disabled={ask.isPending}>
            {T.submit}
          </button>
        </form>
      )}
      {data.error && <p className="form-error">{data.error.message}</p>}
      {data.data?.requests.length === 0 && <EmptyState title={T.none} />}
      <div className="request-list">
        {data.data?.requests.map((r) => (
          <section key={r.id} className="card request-card">
            <div className="request-head">
              <b>{T.types[r.type]}</b>
              <StatusBadge tone={TONE[r.status]}>{T.status[r.status]}</StatusBadge>
            </div>
            <p className="small">
              {r.purpose}
              {r.status !== "ready" && r.status !== "rejected" && <> · {T.promised(day(r.due_date))}</>}
              {r.number && <> · {r.number}</>}
            </p>
            {r.overdue && <p className="small att-critical">{T.overdue}</p>}
            {r.reason && <p className="small att-critical">{r.reason}</p>}
            {r.status === "ready" && (
              <a className="btn btn-primary btn-sm" href={myCertificatePdf(r.id)} target="_blank" rel="noreferrer">
                {T.download}
              </a>
            )}
          </section>
        ))}
      </div>
    </div>
  );
}

function NoDues({ T, dues, day }: { T: CertStrings; dues: Due[]; day: (iso: string) => string }) {
  return (
    <div className={`no-dues ${dues.length ? "no-dues-owed" : "no-dues-clear"}`} role="status">
      <b>{T.noDues}</b>
      {dues.length === 0 ? (
        <p className="small">{T.noDuesClear}</p>
      ) : (
        <>
          <p className="small">{T.noDuesIntro}</p>
          <ul className="small">
            {dues.map((d, i) => (
              <li key={i}>
                {d.area === "fees" ? T.duesFees(d.year ?? "", formatPaise(d.amount)) : d.area === "library" ? T.duesBook(d.title ?? "", day(d.due_date ?? "")) : T.duesHostel}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

const dueText = (d: Due) => (d.amount ? `${d.what} ${formatPaise(d.amount)}` : d.what);

/** Office and Accounts: check a student's dues (fees, library, hostel) before a TC. */
function NoDuesLookup() {
  const [prn, setPrn] = useState("");
  const [result, setResult] = useState<Awaited<ReturnType<typeof noDuesFor>> | null>(null);
  const [error, setError] = useState("");
  return (
    <form
      className="row-actions no-dues-lookup"
      onSubmit={(e) => {
        e.preventDefault();
        setError("");
        noDuesFor(prn)
          .then(setResult)
          .catch((err: Error) => (setResult(null), setError(err.message)));
      }}
    >
      <label>
        No-dues check for PRN <input value={prn} onChange={(e) => setPrn(e.target.value)} required aria-label="PRN for the no-dues check" />
      </label>
      <button type="submit" className="btn btn-ghost btn-sm">
        Check
      </button>
      {error && <span className="form-error">{error}</span>}
      {result && (
        <span className={result.clear ? "small" : "small att-critical"} role="status">
          {result.student.name}: {result.clear ? "no dues" : result.dues.map(dueText).join("; ")}
        </span>
      )}
    </form>
  );
}

/** Office / Principal / HOD / Accounts: the queue, with what each person may do. */
function StaffCertificates() {
  const { data: me } = useMe();
  const [status, setStatus] = useState("open");
  const queue = useCertQueue(status);
  const action = useCertAction();
  const [rejecting, setRejecting] = useState<CertRequest | null>(null);
  const [forStudent, setForStudent] = useState(false);
  const [settings, setSettings] = useState(false);
  const isOffice = hasPermission(me, "certificates.manage");
  const T = CERT_STRINGS.en;
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Office</div>
          <h1>Certificates</h1>
        </div>
        {isOffice && (
          <div className="row-actions">
            <button type="button" className="btn btn-ghost" onClick={() => setSettings(true)}>
              Promised days
            </button>
            <button type="button" className="btn btn-primary" onClick={() => setForStudent(true)}>
              Request for a student
            </button>
          </div>
        )}
      </div>
      {(isOffice || hasPermission(me, "certificates.read")) && <NoDuesLookup />}
      <div className="day-pick" role="group" aria-label="Status">
        {[
          ["open", "In progress"],
          ["ready", "Issued"],
          ["rejected", "Rejected"],
        ].map(([v, label]) => (
          <button key={v} type="button" className={`btn btn-sm ${status === v ? "btn-primary" : "btn-ghost"}`} onClick={() => setStatus(v)}>
            {label}
          </button>
        ))}
      </div>
      {(action.error ?? queue.error) && <p className="form-error">{(action.error ?? queue.error)?.message}</p>}
      {queue.data?.length === 0 && <EmptyState title="Nothing here" />}
      <div className="request-list">
        {queue.data?.map((r) => (
          <section key={r.id} className={`card request-card${r.overdue ? " cert-overdue" : ""}`}>
            <div className="request-head">
              <b>
                {r.type_name} · {r.student} ({r.prn})
              </b>
              <StatusBadge tone={TONE[r.status]}>{r.status_label}</StatusBadge>
              {r.overdue && <StatusBadge tone="danger">Overdue{r.escalated ? " · Principal told" : ""}</StatusBadge>}
            </div>
            <p className="small">
              {r.purpose}
              {r.details.reason_for_leaving && ` · leaving: ${r.details.reason_for_leaving}`}
              {r.details.organisation && ` · ${r.details.organisation} ${r.details.from_date} to ${r.details.to_date}`}
            </p>
            <p className="muted small">
              Promised {r.due_date} · signed by the {r.signer_label}
              {r.number && ` · ${r.number}`}
            </p>
            {r.dues && r.dues.length > 0 && <p className="small att-critical">Dues: {r.dues.map(dueText).join(", ")}</p>}
            {r.reason && <p className="small att-critical">Rejected: {r.reason}</p>}
            <div className="row-actions">
              {r.can?.verify && (
                <button type="button" className="btn btn-primary btn-sm" onClick={() => action.mutate({ id: r.id, action: "verify" })}>
                  Verify{r.type === "tc" || r.type === "migration" ? " (checks dues)" : ""}
                </button>
              )}
              {r.can?.sign && (
                <button type="button" className="btn btn-primary btn-sm" onClick={() => action.mutate({ id: r.id, action: "sign" })}>
                  Sign
                </button>
              )}
              {r.can?.issue && (
                <button type="button" className="btn btn-primary btn-sm" onClick={() => action.mutate({ id: r.id, action: "issue" })}>
                  Issue{r.type === "tc" ? " (student leaves)" : ""}
                </button>
              )}
              {r.can?.reject && (
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setRejecting(r)}>
                  Reject
                </button>
              )}
              {r.status === "ready" && (
                <a className="btn btn-ghost btn-sm" href={staffCertificatePdf(r.id)} target="_blank" rel="noreferrer">
                  PDF
                </a>
              )}
            </div>
          </section>
        ))}
      </div>
      <ConfirmDialog
        open={!!rejecting}
        title="Reject this request?"
        message="Say why; the student sees it."
        confirmLabel="Reject"
        requireReason
        danger
        onCancel={() => setRejecting(null)}
        onConfirm={(reason) => {
          if (rejecting) action.mutate({ id: rejecting.id, action: "reject", reason });
          setRejecting(null);
        }}
      />
      {forStudent && <ForStudent T={T} onClose={() => setForStudent(false)} />}
      {settings && <Settings onClose={() => setSettings(false)} />}
    </>
  );
}

function ForStudent({ T, onClose }: { T: CertStrings; onClose: () => void }) {
  const types = useCertTypes();
  const ask = useRequestFor();
  const [q, setQ] = useState("");
  const students = useStudents({ q: q.trim().length >= 2 ? q.trim() : "__none__" });
  const [studentId, setStudentId] = useState("");
  const [form, setForm] = useState<NewRequest>({ type: "bonafide", purpose: "" });
  const err = ask.error instanceof ApiError ? ask.error : null;
  return (
    <Modal open title="Request for a student" onClose={onClose} wide>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask.mutate({ ...clean(form), student_id: studentId }, { onSuccess: onClose });
        }}
      >
        {err && <div className="form-error">{err.message}</div>}
        <div className="field-row">
          <div className="field">
            <label htmlFor="fs-q">Find the student</label>
            <input id="fs-q" placeholder="Name or PRN" value={q} onChange={(e) => (setQ(e.target.value), setStudentId(""))} />
          </div>
          <div className="field">
            <label htmlFor="fs-student">Student</label>
            <select id="fs-student" value={studentId} onChange={(e) => setStudentId(e.target.value)} required>
              <option value="">{q.trim().length >= 2 ? "Choose…" : "Type at least 2 letters"}</option>
              {(q.trim().length >= 2 ? (students.data?.items ?? []) : []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} · {s.prn}
                </option>
              ))}
            </select>
          </div>
        </div>
        <RequestFields T={T} types={(types.data ?? []).filter((t) => t.enabled)} value={form} onChange={setForm} />
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={ask.isPending}>
            Create request
          </button>
        </div>
      </form>
    </Modal>
  );
}

function Settings({ onClose }: { onClose: () => void }) {
  const types = useCertTypes();
  const update = useUpdateCertType();
  return (
    <Modal open title="Promised working days" onClose={onClose} wide>
      <p className="muted small">Students see the promised date when they ask. Sundays and college holidays don't count.</p>
      {update.error && <div className="form-error">{update.error.message}</div>}
      {types.data?.map((t) => (
        <div className="field-row scheme-row" key={t.type}>
          <div className="field">
            <label htmlFor={`pd-${t.type}`}>{t.name}</label>
            <input
              id={`pd-${t.type}`}
              type="number"
              min={1}
              max={60}
              defaultValue={t.promised_days}
              onBlur={(e) => Number(e.target.value) !== t.promised_days && update.mutate({ type: t.type, promised_days: Number(e.target.value), enabled: t.enabled })}
            />
          </div>
          <label className="check-label">
            <input type="checkbox" checked={t.enabled} onChange={(e) => update.mutate({ type: t.type, promised_days: t.promised_days, enabled: e.target.checked })} /> Students can ask
          </label>
          <span className="muted small">signed by the {t.signer_label}</span>
        </div>
      ))}
      <div className="modal-actions">
        <button type="button" className="btn btn-primary" onClick={onClose}>
          Done
        </button>
      </div>
    </Modal>
  );
}

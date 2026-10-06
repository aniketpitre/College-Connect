import { useState } from "react";
import { Link, useParams } from "react-router";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { StatusBadge } from "../../components/StatusBadge";
import { STUDENT_STRINGS } from "../../i18n/student";
import { API_V1 } from "../../lib/api";
import { hasPermission, useMe } from "../../lib/auth";
import { STATUS_TONE, useApplication, useApplicationAction, useRefundQuote } from "../../lib/admissions";
import { formatPaise } from "../../lib/money";
import { useSetup } from "../../lib/setup";
import "./admissions.css";

const L = STUDENT_STRINGS.en;

interface Confirmed {
  prn: string;
  temporary_password: string;
  student_id: string;
  fee_demand: number | null;
  warning: string | null;
}

/** Admission Cell: one application — documents, fee, decision, confirmation and cancellation. */
export default function ApplicationDetailPage() {
  const { id = "" } = useParams();
  const { data: me } = useMe();
  const app = useApplication(id);
  const act = useApplicationAction(id);
  const setup = useSetup();
  const canManage = hasPermission(me, "admissions.manage");
  const [reason, setReason] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [division, setDivision] = useState("");
  const [prn, setPrn] = useState("");
  const [slip, setSlip] = useState<Confirmed | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const a = app.data;
  const quote = useRefundQuote(id, a?.status === "admitted");
  if (app.error) return <p className="form-error">{app.error.message}</p>;
  if (!a) return <p className="muted">Loading…</p>;
  const p = a.personal;
  const divisions = (setup.data?.divisions ?? []).filter((d) => d.programme_id === a.programme_id && d.year_of_study === 1);
  const run = (path: string, body: unknown, done?: (r: Record<string, unknown>) => void) => act.mutate({ path, body }, { onSuccess: done });

  return (
    <>
      <Link to="/app/admissions" className="back-link">
        ← Admissions
      </Link>
      <div className="page-head">
        <div>
          <div className="eyebrow">
            {a.number ?? "Draft"} · {a.cycle_name}
          </div>
          <h1>{p.name}</h1>
          <div className="muted">
            {a.programme} · {a.category} · {a.merit_score ?? "–"}% · {p.phone} · {p.email}
          </div>
        </div>
        <StatusBadge tone={STATUS_TONE[a.status] ?? "neutral"}>{a.status_label}</StatusBadge>
      </div>
      {act.error && <p className="form-error">{act.error.message}</p>}
      {a.reason && <p className="small">Note to applicant: {a.reason}</p>}
      {a.offer && (
        <p className="small">
          Round {a.offer.round} offer: {a.offer.seat_label} seat, confirm by {a.offer.accept_by} (merit rank {a.rank}).
        </p>
      )}

      <section className="card">
        <h2 className="card-title">Details</h2>
        <dl className="record-grid">
          {(
            [
              ["Mother's name", p.mother_name],
              ["Gender", p.gender ? L.genders[p.gender as string] : null],
              ["Date of birth", p.dob],
              ["Previous exam", p.previous_education ? `${p.previous_education.exam ?? ""} ${p.previous_education.board ?? ""} ${p.previous_education.year ?? ""}: ${p.previous_education.percentage ?? "–"}%` : null],
            ] as [string, unknown][]
          ).map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>{(v as string) || "—"}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="card">
        <h2 className="card-title">Documents</h2>
        <ul className="app-docs">
          {a.documents.map((d) => (
            <li key={d.id}>
              <div>
                <b>{L.docTypes[d.type] ?? d.type}</b>
                <div className="muted small">
                  <a href={`${API_V1}${d.url}`} target="_blank" rel="noreferrer">
                    {d.filename}
                  </a>{" "}
                  · {L.docStatus[d.status]}
                  {d.reason ? ` (${d.reason})` : ""}
                </div>
              </div>
              {canManage && a.status === "submitted" && d.status === "pending" && (
                <div className="row-actions">
                  <button type="button" className="btn btn-primary btn-sm" onClick={() => run(`documents/${d.id}/decide`, { approve: true })}>
                    Verify
                  </button>
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => run(`documents/${d.id}/decide`, { approve: false, reason: reason || "Not clear" })}>
                    Not OK
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h2 className="card-title">Application fee</h2>
        <p>
          {formatPaise(a.fee.amount)} · {a.fee.status}
          {a.fee.receipt_number && ` · receipt ${a.fee.receipt_number}`}
          {a.fee.mode && ` · ${a.fee.mode}`}
        </p>
        {canManage && a.fee.status === "unpaid" && (
          <div className="row-actions" style={{ justifyContent: "flex-start" }}>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => run("fee", { mode: "cash" })}>
              Paid in cash
            </button>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => run("fee", { mode: "waived" })}>
              Waive
            </button>
          </div>
        )}
      </section>

      {canManage && a.status === "submitted" && (
        <section className="card">
          <h2 className="card-title">Decision</h2>
          <div className="field">
            <label htmlFor="ad-reason">Note to the applicant (needed to return or reject)</label>
            <input id="ad-reason" value={reason} onChange={(e) => setReason(e.target.value)} />
          </div>
          <div className="row-actions" style={{ justifyContent: "flex-start" }}>
            <button type="button" className="btn btn-primary" onClick={() => run("decide", { action: "verify" })}>
              Verify for the merit list
            </button>
            <button type="button" className="btn btn-ghost" disabled={!reason.trim()} onClick={() => run("decide", { action: "return", reason })}>
              Return for correction
            </button>
            <button type="button" className="btn btn-ghost" disabled={!reason.trim()} onClick={() => run("decide", { action: "reject", reason })}>
              Reject
            </button>
          </div>
        </section>
      )}

      {canManage && a.status === "offered" && (
        <section className="card">
          <h2 className="card-title">Confirm admission</h2>
          <p className="muted small">Check the original documents and collect the first fees, then confirm. This creates the student record, the student login and the year's fee demand.</p>
          {!confirming ? (
            <button type="button" className="btn btn-primary" onClick={() => setConfirming(true)}>
              Confirm admission…
            </button>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                run("confirm", { division_id: division || undefined, prn: prn.trim() || undefined }, (r) => setSlip(r as unknown as Confirmed));
              }}
            >
              <div className="app-grid">
                <div className="field">
                  <label htmlFor="cf-div">Division</label>
                  <select id="cf-div" value={division} onChange={(e) => setDivision(e.target.value)}>
                    <option value="">{divisions.length === 1 ? divisions[0].name : "Assign later"}</option>
                    {divisions.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="cf-prn">PRN (leave empty to number it)</label>
                  <input id="cf-prn" value={prn} onChange={(e) => setPrn(e.target.value)} />
                </div>
              </div>
              <button type="submit" className="btn btn-primary" disabled={act.isPending}>
                Confirm and create the student
              </button>
            </form>
          )}
        </section>
      )}

      {slip && (
        <section className="card slip" aria-label="Admission slip">
          <h2 className="card-title">Admission slip</h2>
          <p>
            {p.name} · {a.programme}
          </p>
          <p>
            PRN <b>{slip.prn}</b> · temporary password <b>{slip.temporary_password}</b>
          </p>
          <p className="muted small">The student signs in with the PRN and this password, and sets their own password the first time.</p>
          {slip.fee_demand != null && <p>Fee for the year: {formatPaise(slip.fee_demand)}</p>}
          {slip.warning && <p className="form-error">{slip.warning}</p>}
          <div className="row-actions" style={{ justifyContent: "flex-start" }}>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => window.print()}>
              Print
            </button>
            <Link className="btn btn-ghost btn-sm" to={`/app/fees/collect/${slip.student_id}`}>
              Collect fees
            </Link>
          </div>
        </section>
      )}

      {a.status === "admitted" && !slip && (
        <section className="card">
          <h2 className="card-title">Admitted</h2>
          <p>
            PRN {a.prn}.{" "}
            {a.student_id && <Link to={`/app/students/${a.student_id}`}>Open the student record</Link>}
          </p>
          {quote.data && quote.data.refundable != null && (
            <p className="muted small">
              If cancelled today: paid {formatPaise(quote.data.paid)}, {quote.data.percent}% refundable by the rules → {formatPaise(quote.data.refundable)} back, {formatPaise(quote.data.kept)} kept.
            </p>
          )}
          {canManage && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setCancelling(true)}>
              Cancel admission…
            </button>
          )}
        </section>
      )}
      <ConfirmDialog
        open={cancelling}
        title="Cancel this admission?"
        message="The fee demand is reversed and the refundable amount stays as a credit; Accounts then pay it back (with the Principal's approval). The student's login becomes read-only."
        confirmLabel="Cancel admission"
        requireReason
        danger
        onCancel={() => setCancelling(false)}
        onConfirm={(r) => run("cancel", { reason: r }, () => setCancelling(false))}
      />
    </>
  );
}

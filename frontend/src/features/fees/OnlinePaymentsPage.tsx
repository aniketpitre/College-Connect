import { useState } from "react";
import { Link } from "react-router";
import { EmptyState } from "../../components/EmptyState";
import { MoneyText } from "../../components/MoneyText";
import { StatusBadge } from "../../components/StatusBadge";
import { hasPermission, useMe } from "../../lib/auth";
import { formatPaise } from "../../lib/money";
import { useCheckPayment, useOnlinePayments, useReconcile, type OnlinePayment } from "../../lib/payments";
import "./fees.css";

const TONE: Record<OnlinePayment["status"], "success" | "warning" | "danger" | "neutral"> = {
  paid: "success",
  created: "warning",
  mismatch: "danger",
  failed: "neutral",
  expired: "neutral",
};

const todayIso = () => new Date(Date.now() + 5.5 * 3600_000).toISOString().slice(0, 10); // India date

/** Accounts: online payments by day, checking stuck ones, and matching the gateway's export. */
export default function OnlinePaymentsPage() {
  const { data: me } = useMe();
  const [day, setDay] = useState(todayIso);
  const list = useOnlinePayments(day);
  const check = useCheckPayment();
  const d = list.data;
  return (
    <>
      <Link to="/app/fees" className="back-link">
        ← Fees
      </Link>
      <div className="page-head">
        <h1>Online payments</h1>
        <input type="date" aria-label="Day" value={day} onChange={(e) => setDay(e.target.value)} />
      </div>
      {d && !d.enabled && (
        <p className="muted">
          Online payment is switched off. Set RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET and RAZORPAY_WEBHOOK_SECRET in the server settings to turn it on (test keys
          work without real money).
        </p>
      )}
      {d && (
        <div className="tiles fee-tiles">
          <div className="tile">
            <div className="tile-label">Paid</div>
            <div className="tile-value">
              <MoneyText paise={d.paid_amount} />
            </div>
            <div className="tile-note">{d.paid_count} payments · in the day book as “Online payment”</div>
          </div>
          <div className="tile">
            <div className="tile-label">Waiting</div>
            <div className="tile-value">{d.waiting}</div>
            <div className="tile-note">Started, not confirmed yet</div>
          </div>
          <div className={`tile${d.problems ? " tile-warn" : ""}`}>
            <div className="tile-label">To check</div>
            <div className="tile-value">{d.problems}</div>
          </div>
        </div>
      )}
      {check.error && <p className="form-error">{check.error.message}</p>}
      {d?.payments.length === 0 && <EmptyState title="No online payments on this day" />}
      {d && d.payments.length > 0 && (
        <div className="data-table data-table-scroll">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Student</th>
                <th className="num">Amount</th>
                <th>Status</th>
                <th>Gateway</th>
                <th>Receipt</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {d.payments.map((p) => (
                <tr key={p.id}>
                  <td>{new Date(p.created_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}</td>
                  <td>
                    {p.student_id ? <Link to={`/app/fees/students/${p.student_id}`}>{p.student?.name}</Link> : p.student?.name}
                    <div className="muted small">
                      {p.student?.prn}
                      {p.paid_by === "parent" ? " · paid by parent" : ""}
                      {p.purpose === "application" ? " · application fee" : ""}
                    </div>
                  </td>
                  <td className="num">
                    {formatPaise(p.amount)}
                    {p.credit > 0 && <div className="small att-critical">{formatPaise(p.credit)} more than due: refund</div>}
                  </td>
                  <td>
                    <StatusBadge tone={TONE[p.status]}>{p.status_label}</StatusBadge>
                    {p.last_error && <div className="muted small">{p.last_error}</div>}
                  </td>
                  <td className="small">
                    {p.gateway_payment_id ?? p.order_id}
                    {p.method ? ` · ${p.method}` : ""}
                  </td>
                  <td>{p.receipt_number ?? "–"}</td>
                  <td>
                    {(p.status === "created" || p.status === "expired") && hasPermission(me, "fees.collect") && (
                      <button type="button" className="btn btn-ghost btn-sm" disabled={check.isPending} onClick={() => check.mutate(p.id)}>
                        Check with gateway
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Reconcile />
    </>
  );
}

function Reconcile() {
  const reconcile = useReconcile();
  const r = reconcile.data;
  return (
    <section className="card reconcile-card">
      <h2 className="card-title">Match with the gateway</h2>
      <p className="muted small">Download the payments report (CSV) from the Razorpay dashboard for any days and upload it here.</p>
      <input
        type="file"
        accept=".csv,text/csv"
        aria-label="Gateway report (CSV)"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) reconcile.mutate(file);
          e.target.value = "";
        }}
      />
      {reconcile.error && <p className="form-error">{reconcile.error.message}</p>}
      {r && (
        <div className="reconcile-result">
          <p>
            <b>{r.matched}</b> of {r.rows} captured payments match ({formatPaise(r.matched_amount)}).
          </p>
          {r.missing_in_collegeconnect.length > 0 && (
            <p className="att-critical small">
              In the gateway but not paid here (use “Check with gateway” on that day):{" "}
              {r.missing_in_collegeconnect.map((m) => `${m.gateway_payment_id} ${formatPaise(m.amount)}`).join(", ")}
            </p>
          )}
          {r.amount_differs.length > 0 && (
            <p className="att-critical small">
              Amount differs: {r.amount_differs.map((m) => `${m.gateway_payment_id} (here ${formatPaise(m.amount)}, gateway ${formatPaise(m.gateway_amount)})`).join(", ")}
            </p>
          )}
          {r.missing_in_gateway_file.length > 0 && (
            <p className="att-critical small">
              Paid here but not in the file: {r.missing_in_gateway_file.map((m) => `${m.gateway_payment_id} ${formatPaise(m.amount)}`).join(", ")}
            </p>
          )}
          {r.missing_in_collegeconnect.length + r.amount_differs.length + r.missing_in_gateway_file.length === 0 && <p className="small">Everything matches.</p>}
        </div>
      )}
    </section>
  );
}

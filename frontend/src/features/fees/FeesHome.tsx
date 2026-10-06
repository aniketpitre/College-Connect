import { useState } from "react";
import { Link } from "react-router";
import { DataTable } from "../../components/DataTable";
import { MoneyText } from "../../components/MoneyText";
import { StatusBadge } from "../../components/StatusBadge";
import { hasPermission, useMe } from "../../lib/auth";
import { receiptPdfUrl, useReceipts, useToday, type Receipt } from "../../lib/fees";
import { useStudents, type StudentSummary } from "../../lib/students";
import "./fees.css";

/** Accounts home (English): today's collection, find a student, recent receipts. */
export default function FeesHome() {
  const { data: me } = useMe();
  const [q, setQ] = useState("");
  const students = useStudents({ q: q.trim() || undefined, status: "active" });
  const today = useToday();
  const receipts = useReceipts({ date_from: today.data?.date, date_to: today.data?.date });
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Accounts</div>
          <h1>Fees</h1>
        </div>
        <div className="row-actions">
          <Link className="btn btn-ghost" to="/app/fees/reports">
            Reports
          </Link>
          <Link className="btn btn-ghost" to="/app/fees/online">
            Online payments
          </Link>
          {hasPermission(me, "fees.manage") && (
            <>
              <Link className="btn btn-ghost" to="/app/fees/opening">
                Opening balances
              </Link>
              <Link className="btn btn-ghost" to="/app/fees/setup">
                Fee setup
              </Link>
            </>
          )}
        </div>
      </div>
      {today.data && (
        <div className="tiles fee-tiles">
          <div className="tile">
            <div className="tile-label">Collected today</div>
            <div className="tile-value">
              <MoneyText paise={today.data.total} />
            </div>
            <div className="tile-note">{today.data.count} receipts{today.data.cancelled ? ` · ${today.data.cancelled} cancelled` : ""}</div>
          </div>
          {today.data.by_mode.map((m) => (
            <div className="tile" key={m.mode}>
              <div className="tile-label">{m.label}</div>
              <div className="tile-value" style={{ fontSize: "1.4rem" }}>
                <MoneyText paise={m.amount} />
              </div>
            </div>
          ))}
          {today.data.pending_approvals > 0 && (
            <Link className="tile tile-link" to="/app/approvals">
              <div className="tile-label">Waiting for approval</div>
              <div className="tile-value">{today.data.pending_approvals}</div>
            </Link>
          )}
        </div>
      )}
      <div className="field student-search">
        <label htmlFor="fee-search">Find a student</label>
        <input id="fee-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name, PRN or mobile" autoFocus />
      </div>
      {q.trim() && (
        <DataTable
          columns={[
            {
              key: "name",
              header: "Student",
              render: (s: StudentSummary) => (
                <Link to={`/app/fees/students/${s.id}`} className="user-cell">
                  <span className="user-name">{s.name}</span>
                  <span className="user-sub">PRN {s.prn}</span>
                </Link>
              ),
            },
            { key: "class", header: "Class", render: (s) => [s.programme_code, s.year_label, s.division].filter(Boolean).join(" · ") },
            { key: "cat", header: "Category", render: (s) => s.category_code ?? "—" },
          ]}
          rows={students.data?.items ?? []}
          rowKey={(s) => s.id}
          emptyTitle={students.isLoading ? "Searching…" : "No student found"}
        />
      )}
      {!q.trim() && (
        <>
          <h2 className="subhead">Today's receipts</h2>
          <DataTable
            columns={[
              {
                key: "no",
                header: "Receipt",
                render: (r: Receipt) => (
                  <a href={receiptPdfUrl(r.id)} target="_blank" rel="noreferrer" className="mono-link">
                    {r.number}
                  </a>
                ),
                searchText: (r) => r.number,
              },
              {
                key: "student",
                header: "Student",
                render: (r) => <Link to={`/app/fees/students/${r.student_id}`}>{r.student.name}</Link>,
                searchText: (r) => `${r.student.name} ${r.student.prn}`,
              },
              { key: "mode", header: "Mode", render: (r) => r.mode_label },
              { key: "time", header: "Time", render: (r) => new Date(r.collected_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }) },
              { key: "by", header: "By", render: (r) => r.collected_by },
              {
                key: "amount",
                header: "Amount",
                align: "right",
                render: (r) => (r.status === "cancelled" ? <StatusBadge tone="danger">Cancelled</StatusBadge> : <MoneyText paise={r.amount} />),
              },
            ]}
            rows={receipts.data ?? []}
            rowKey={(r) => r.id}
            emptyTitle="No receipts yet today"
          />
        </>
      )}
    </>
  );
}

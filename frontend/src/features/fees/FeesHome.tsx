import { useState } from "react";
import { Link } from "react-router";
import { DataTable } from "../../components/DataTable";
import { hasPermission, useMe } from "../../lib/auth";
import { useStudents, type StudentSummary } from "../../lib/students";
import "./fees.css";

/** Accounts home (English): find a student's fee account. 1.9 adds today's collection. */
export default function FeesHome() {
  const { data: me } = useMe();
  const [q, setQ] = useState("");
  const students = useStudents({ q: q.trim() || undefined, status: "active" });
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Accounts</div>
          <h1>Fees</h1>
        </div>
        <div className="row-actions">
          {hasPermission(me, "fees.manage") && (
            <Link className="btn btn-ghost" to="/app/fees/setup">
              Fee setup
            </Link>
          )}
        </div>
      </div>
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
    </>
  );
}

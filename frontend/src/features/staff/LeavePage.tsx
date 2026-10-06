import { useState } from "react";
import { Link } from "react-router";
import { EmptyState } from "../../components/EmptyState";
import { StatusBadge } from "../../components/StatusBadge";
import { useApplyLeave, useCancelLeave, useDecideLeave, useLeaveRequests, useMyLeave, type LeaveRequest } from "../../lib/staff";
import "../campus/campus.css";
import "./staff.css";

const day = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
const span = (r: LeaveRequest) => (r.from_date === r.to_date ? day(r.from_date) : `${day(r.from_date)} – ${day(r.to_date)}`);
const tone = (s: LeaveRequest["status"]) => (s === "approved" ? "success" : s === "rejected" ? "danger" : s === "pending" ? "warning" : "neutral");
const APPROVER = {
  hod: "your HOD",
  principal: "the Principal",
  self: "nobody (recorded as approved)",
};

/** Staff (English): leave balances, applying, and for HODs and the Principal, approving. */
export default function LeavePage() {
  const mine = useMyLeave();
  const apply = useApplyLeave();
  const cancel = useCancelLeave();
  const [form, setForm] = useState({
    code: "CL",
    from_date: "",
    to_date: "",
    half_day: false,
    reason: "",
  });
  const m = mine.data;
  if (mine.error) return <p className="form-error">{mine.error.message}</p>;
  if (!m) return null;
  const type = m.balances.find((b) => b.code === form.code);
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Leave · {m.year}</div>
          <h1>My leave</h1>
        </div>
      </div>
      <div className="tiles fee-tiles">
        {m.balances.map((b) => (
          <div key={b.code} className="tile">
            <div className="tile-label">{b.name}</div>
            <div className="tile-value">{b.available === null ? `${b.taken} taken` : `${b.available} left`}</div>
            {b.allowance !== null && (
              <div className="small muted">
                of {b.allowance}
                {b.pending > 0 && ` · ${b.pending} waiting`}
              </div>
            )}
          </div>
        ))}
      </div>
      <h2 className="subhead">Apply for leave</h2>
      <form
        className="card campus-form"
        onSubmit={(e) => {
          e.preventDefault();
          apply.mutate(
            {
              ...form,
              to_date: form.half_day ? form.from_date : form.to_date || form.from_date,
            },
            {
              onSuccess: () =>
                setForm({
                  code: form.code,
                  from_date: "",
                  to_date: "",
                  half_day: false,
                  reason: "",
                }),
            },
          );
        }}
      >
        <div className="field">
          <label htmlFor="lv-type">Type</label>
          <select id="lv-type" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value, half_day: false })}>
            {m.balances.map((b) => (
              <option key={b.code} value={b.code}>
                {b.name}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="lv-from">From</label>
          <input id="lv-from" type="date" value={form.from_date} onChange={(e) => setForm({ ...form, from_date: e.target.value })} required />
        </div>
        <div className="field">
          <label htmlFor="lv-to">To</label>
          <input
            id="lv-to"
            type="date"
            value={form.half_day ? form.from_date : form.to_date}
            min={form.from_date}
            disabled={form.half_day}
            onChange={(e) => setForm({ ...form, to_date: e.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor="lv-why">Reason</label>
          <input id="lv-why" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} required minLength={3} />
        </div>
        {type?.half_day && (
          <label className="check-label">
            <input type="checkbox" checked={form.half_day} onChange={(e) => setForm({ ...form, half_day: e.target.checked })} /> Half day
          </label>
        )}
        <p className="small muted staff-wide">Sundays and college holidays don't count. Your leave goes to {APPROVER[m.approver]}.</p>
        {apply.error && <p className="form-error staff-wide">{apply.error.message}</p>}
        <div>
          <button type="submit" className="btn btn-primary" disabled={apply.isPending}>
            Apply
          </button>
        </div>
      </form>
      <h2 className="subhead">My requests</h2>
      {m.requests.length === 0 ? (
        <p className="muted">No leave this year.</p>
      ) : (
        <ul className="campus-list">
          {m.requests.map((r) => (
            <li key={r.id}>
              <div>
                <b>{r.type_name}</b> · {span(r)} · {r.days} day
                {r.days === 1 ? "" : "s"}
                <div className="small muted">
                  {r.reason}
                  {r.decided_by && ` · ${r.status} by ${r.decided_by}`}
                  {r.note && ` · ${r.note}`}
                </div>
              </div>
              <span className="row-actions">
                {(r.status === "pending" || (r.status === "approved" && r.from_date > m.today)) && (
                  <button type="button" className="btn btn-ghost btn-sm" disabled={cancel.isPending} onClick={() => cancel.mutate(r.id)}>
                    Cancel
                  </button>
                )}
                <StatusBadge tone={tone(r.status)}>{r.status}</StatusBadge>
              </span>
            </li>
          ))}
        </ul>
      )}
      {m.can_approve && <Approvals />}
    </>
  );
}

function Approvals() {
  const [status, setStatus] = useState("pending");
  const list = useLeaveRequests(status, true);
  const decide = useDecideLeave();
  const [notes, setNotes] = useState<Record<string, string>>({});
  return (
    <>
      <h2 className="subhead">Leave to approve</h2>
      <div className="day-pick" role="group" aria-label="Status">
        {(
          [
            ["pending", "Waiting"],
            ["approved", "Approved"],
            ["rejected", "Rejected"],
          ] as const
        ).map(([k, label]) => (
          <button key={k} type="button" className={status === k ? "active" : ""} aria-pressed={status === k} onClick={() => setStatus(k)}>
            {label}
          </button>
        ))}
      </div>
      {decide.error && <p className="form-error">{decide.error.message}</p>}
      {list.data?.length === 0 && <EmptyState title="Nothing here" />}
      {list.data?.map((r) => (
        <section key={r.id} className="card leave-card">
          <div className="staff-head">
            <div>
              <b>{r.name}</b> · {r.type_name} · {span(r)} · {r.days} day
              {r.days === 1 ? "" : "s"}
              <div className="small muted">
                {r.reason}
                {r.balance && r.balance.available !== null && ` · ${r.balance.available} ${r.balance.name.toLowerCase()} left after this`}
                {r.decided_by && ` · ${r.status} by ${r.decided_by}`}
                {r.note && ` · ${r.note}`}
              </div>
            </div>
            <StatusBadge tone={tone(r.status)}>{r.status}</StatusBadge>
          </div>
          {r.lectures && r.lectures.length > 0 && (
            <div className="small">
              Lectures to cover ({r.lectures.length}):{" "}
              {r.lectures.map((l) => `${day(l.date)} ${l.start} ${l.subject ?? ""}${l.division ? ` (${l.division})` : ""}`).join(" · ")}{" "}
              <Link to="/app/timetable">Arrange substitutes in the timetable →</Link>
            </div>
          )}
          {r.lectures && r.lectures.length === 0 && <div className="small muted">No lectures in this period.</div>}
          {r.status === "pending" && (
            <div className="row-actions" style={{ justifyContent: "flex-start", marginTop: 8 }}>
              <input
                aria-label={`Note for ${r.name}`}
                placeholder="Note (needed to reject)"
                value={notes[r.id] ?? ""}
                onChange={(e) => setNotes({ ...notes, [r.id]: e.target.value })}
              />
              <button
                type="button"
                className="btn btn-primary btn-sm"
                disabled={decide.isPending}
                onClick={() =>
                  decide.mutate({
                    id: r.id,
                    approve: true,
                    note: notes[r.id] ?? "",
                  })
                }
              >
                Approve
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                disabled={decide.isPending || !(notes[r.id] ?? "").trim()}
                onClick={() =>
                  decide.mutate({
                    id: r.id,
                    approve: false,
                    note: notes[r.id] ?? "",
                  })
                }
              >
                Reject
              </button>
            </div>
          )}
        </section>
      ))}
    </>
  );
}

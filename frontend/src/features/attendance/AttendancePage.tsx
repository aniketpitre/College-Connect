import { useState } from "react";
import { Link, useLocation } from "react-router";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { EmptyState } from "../../components/EmptyState";
import { StatusBadge } from "../../components/StatusBadge";
import { hasPermission, useMe } from "../../lib/auth";
import {
  useAddExemption,
  useCancelExemption,
  useDecideEdit,
  useEditRequests,
  useExemptions,
  useToday,
  type EditRequest,
  type Exemption,
} from "../../lib/attendance";
import { useStudents } from "../../lib/students";
import { isoDay, shiftDays } from "../../lib/timetable";
import "./attendance.css";

type Tab = "today" | "requests" | "exemptions";

export default function AttendancePage() {
  const { data: me } = useMe();
  const location = useLocation();
  const saved = (location.state as { saved?: string } | null)?.saved;
  const teaches = hasPermission(me, "attendance.take");
  const tabs: [Tab, string][] = [
    ...(teaches ? ([["today", "My lectures"]] as [Tab, string][]) : []),
    ...(teaches || hasPermission(me, "attendance.approve") ? ([["requests", "Change requests"]] as [Tab, string][]) : []),
    ...(hasPermission(me, "attendance.exempt") ? ([["exemptions", "Exemptions"]] as [Tab, string][]) : []),
  ];
  const [tab, setTab] = useState<Tab | undefined>(tabs[0]?.[0]);

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Academics</div>
          <h1>Attendance</h1>
        </div>
      </div>
      {saved && (
        <div className="auth-success" role="status">
          {saved}
        </div>
      )}
      {tabs.length > 1 && (
        <div className="tabs" role="tablist">
          {tabs.map(([id, label]) => (
            <button key={id} type="button" role="tab" aria-selected={tab === id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>
              {label}
            </button>
          ))}
        </div>
      )}
      {tab === "today" && <MyLectures />}
      {tab === "requests" && <Requests canDecide={hasPermission(me, "attendance.approve")} myId={me?.id} />}
      {tab === "exemptions" && <Exemptions />}
      {!tab && <EmptyState title="Attendance reports arrive with the next update" />}
    </>
  );
}

function MyLectures() {
  const [todayIso] = useState(() => isoDay(new Date()));
  const [day, setDay] = useState(todayIso);
  const today = useToday(day);
  const days = [0, 1, 2].map((n) => shiftDays(todayIso, -n));
  return (
    <>
      <div className="day-pick" role="group" aria-label="Day">
        {days.map((d, i) => (
          <button key={d} type="button" className={`btn btn-sm ${d === day ? "btn-primary" : "btn-ghost"}`} onClick={() => setDay(d)}>
            {i === 0 ? "Today" : i === 1 ? "Yesterday" : d}
          </button>
        ))}
      </div>
      {today.error && <p className="form-error">{today.error.message}</p>}
      {today.data?.holiday && <EmptyState title={`Holiday: ${today.data.holiday}`} />}
      {today.data && !today.data.holiday && today.data.lectures.length === 0 && <EmptyState title="No lectures on this day" />}
      <div className="lecture-cards">
        {today.data?.lectures.map((x) => (
          <div key={x.slot_id} className={`card lecture-card lecture-${x.status}`}>
            <div>
              <div className="lecture-time">
                {x.start}–{x.end}
              </div>
              <b>
                {x.subject_code} {x.subject_name}
              </b>
              <div className="muted small">
                {x.division}
                {x.batch && ` · Batch ${x.batch}`}
                {x.room && ` · Room ${x.room}`}
              </div>
              {x.status === "cancelled" && <StatusBadge tone="danger">Cancelled</StatusBadge>}
              {x.status === "substitute" && <StatusBadge tone="warning">You're substituting</StatusBadge>}
              {x.status === "handed_over" && <StatusBadge tone="neutral">Taken by {x.substitute.join(", ")}</StatusBadge>}
            </div>
            <div className="lecture-card-action">
              {x.session && (
                <div className="small">
                  <b>{x.session.present}</b>/{x.session.total} present
                </div>
              )}
              {x.takeable && (
                <Link className={`btn ${x.session ? "btn-ghost" : "btn-primary"}`} to={`/app/attendance/take/${x.slot_id}/${x.date}`}>
                  {x.session ? (x.window_open ? "Change" : "View") : "Take attendance"}
                </Link>
              )}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

function Requests({ canDecide, myId }: { canDecide: boolean; myId?: string }) {
  const [status, setStatus] = useState("pending");
  const list = useEditRequests(status);
  const decide = useDecideEdit();
  const [deciding, setDeciding] = useState<{ r: EditRequest; approve: boolean } | null>(null);
  return (
    <>
      <div className="day-pick">
        {["pending", "approved", "rejected"].map((s) => (
          <button key={s} type="button" className={`btn btn-sm ${s === status ? "btn-primary" : "btn-ghost"}`} onClick={() => setStatus(s)}>
            {s === "pending" ? "Waiting" : s === "approved" ? "Approved" : "Rejected"}
          </button>
        ))}
      </div>
      {decide.error && <p className="form-error">{decide.error.message}</p>}
      {list.data?.length === 0 && <EmptyState title="Nothing here" />}
      <div className="request-list">
        {list.data?.map((r) => (
          <div key={r.id} className="card request-card">
            <div className="request-head">
              <b>
                {r.class} · {r.subject}
              </b>
              <span className="muted">
                {r.date} {r.start}
              </span>
            </div>
            <p className="request-reason">
              Absent {r.absent_now ?? "not marked"} → {r.absent_new}. <span className="muted">Reason:</span> {r.reason}
            </p>
            <p className="muted small">
              Asked by {r.requested_by}
              {r.decided_by && ` · ${r.status} by ${r.decided_by}${r.decision_reason ? `: ${r.decision_reason}` : ""}`}
            </p>
            {canDecide && r.status === "pending" && r.requested_by_id !== myId && (
              <div className="row-actions">
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setDeciding({ r, approve: false })}>
                  Reject
                </button>
                <button type="button" className="btn btn-primary btn-sm" onClick={() => setDeciding({ r, approve: true })}>
                  Approve
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
      <ConfirmDialog
        open={!!deciding}
        title={deciding?.approve ? "Approve this change?" : "Reject this change?"}
        message={deciding?.approve ? "The attendance is changed now and the change is recorded in the audit log." : "Say why, so the teacher knows."}
        confirmLabel={deciding?.approve ? "Approve" : "Reject"}
        requireReason={deciding ? !deciding.approve : false}
        onCancel={() => setDeciding(null)}
        onConfirm={(why) => {
          if (deciding) decide.mutate({ id: deciding.r.id, approve: deciding.approve, reason: why || undefined });
          setDeciding(null);
        }}
      />
    </>
  );
}

function Exemptions() {
  const list = useExemptions(true);
  const add = useAddExemption();
  const cancel = useCancelExemption();
  const [q, setQ] = useState("");
  const students = useStudents({ q: q.trim().length >= 2 ? q.trim() : "__none__" });
  const [studentId, setStudentId] = useState("");
  const [kind, setKind] = useState("medical");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [reason, setReason] = useState("");
  const [cancelling, setCancelling] = useState<Exemption | null>(null);
  return (
    <>
      <form
        className="card exemption-form"
        onSubmit={(e) => {
          e.preventDefault();
          add.mutate(
            { student_id: studentId, kind, from_date: from, to_date: to, reason },
            { onSuccess: () => (setStudentId(""), setQ(""), setReason("")) },
          );
        }}
      >
        <h2 className="subhead">Add an exemption</h2>
        <p className="muted small">Absences on these days count as attended (medical leave with a doctor's note, or official duty such as sports or NSS).</p>
        {add.error && <div className="form-error">{add.error.message}</div>}
        <div className="field-row">
          <div className="field">
            <label htmlFor="ex-q">Find the student</label>
            <input id="ex-q" placeholder="Name or PRN" value={q} onChange={(e) => (setQ(e.target.value), setStudentId(""))} />
          </div>
          <div className="field">
            <label htmlFor="ex-student">Student</label>
            <select id="ex-student" value={studentId} onChange={(e) => setStudentId(e.target.value)} required>
              <option value="">{q.trim().length >= 2 ? "Choose…" : "Type at least 2 letters"}</option>
              {(q.trim().length >= 2 ? students.data?.items ?? [] : []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} · {s.prn}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="field-row">
          <div className="field">
            <label htmlFor="ex-kind">Kind</label>
            <select id="ex-kind" value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="medical">Medical</option>
              <option value="official_duty">Official duty</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="ex-from">From</label>
            <input id="ex-from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} required />
          </div>
          <div className="field">
            <label htmlFor="ex-to">To</label>
            <input id="ex-to" type="date" value={to} min={from} onChange={(e) => setTo(e.target.value)} required />
          </div>
        </div>
        <div className="field">
          <label htmlFor="ex-reason">Reason / document</label>
          <input id="ex-reason" value={reason} onChange={(e) => setReason(e.target.value)} required minLength={3} />
        </div>
        <button type="submit" className="btn btn-primary" disabled={add.isPending}>
          Add exemption
        </button>
      </form>
      {cancel.error && <p className="form-error">{cancel.error.message}</p>}
      {list.data?.length === 0 && <EmptyState title="No exemptions yet" />}
      <div className="request-list">
        {list.data?.map((e) => (
          <div key={e.id} className="card request-card">
            <div className="request-head">
              <StatusBadge tone={e.status === "active" ? "info" : "neutral"}>{e.status === "active" ? e.kind_label : "Cancelled"}</StatusBadge>
              <b>
                {e.student} · {e.prn}
              </b>
              <span className="muted">
                {e.from_date} to {e.to_date}
              </span>
            </div>
            <p className="request-reason">{e.reason}</p>
            {e.status === "active" && (
              <div className="row-actions">
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setCancelling(e)}>
                  Cancel
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
      <ConfirmDialog
        open={!!cancelling}
        title="Cancel this exemption?"
        message="The absences on these days count again."
        confirmLabel="Cancel exemption"
        requireReason
        danger
        onCancel={() => setCancelling(null)}
        onConfirm={(why) => {
          if (cancelling) cancel.mutate({ id: cancelling.id, reason: why });
          setCancelling(null);
        }}
      />
    </>
  );
}

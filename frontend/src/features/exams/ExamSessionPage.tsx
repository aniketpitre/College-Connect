import { useState } from "react";
import { Link, useParams } from "react-router";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { EmptyState } from "../../components/EmptyState";
import { Modal } from "../../components/Modal";
import { StatusBadge } from "../../components/StatusBadge";
import { hasPermission, useMe } from "../../lib/auth";
import { examExportUrl, hallTicketUrl, useAssignSeats, useExamForms, useExamSessions, useUpdateSession, useVerifyEligible, useVerifyForm, type ExamSession, type FormRow } from "../../lib/exams";
import { formatPaise } from "../../lib/money";
import { useSetup, useSubjects } from "../../lib/setup";
import ResultsPanel from "./ResultsPanel";
import "./exams.css";

const TONE = { not_submitted: "neutral", submitted: "info", verified: "success", rejected: "danger" } as const;

/** One exam: papers, every student's form and eligibility, seat numbers, hall tickets. */
export default function ExamSessionPage() {
  const { id = "" } = useParams();
  const { data: me } = useMe();
  const canManage = hasPermission(me, "exams.manage");
  const sessions = useExamSessions();
  const forms = useExamForms(id);
  const verifyAll = useVerifyEligible();
  const seats = useAssignSeats();
  const update = useUpdateSession();
  const verify = useVerifyForm();
  const [filter, setFilter] = useState("");
  const [deciding, setDeciding] = useState<{ row: FormRow; approve: boolean } | null>(null);
  const [papers, setPapers] = useState(false);
  const s = sessions.data?.find((x) => x.id === id);
  const rows = (forms.data ?? []).filter((r) => !filter || (filter === "ineligible" ? !r.eligible : r.status === filter));
  const err = verifyAll.error ?? seats.error ?? update.error ?? verify.error;
  if (!s) return <p className="muted">{sessions.error ? sessions.error.message : "…"}</p>;
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">
            <Link to="/app/exams">Exams & results</Link> · {s.kind === "university" ? "University exam" : "Internal exam"}
          </div>
          <h1>{s.name}</h1>
          <p className="muted">
            {s.classes.map((c) => c.label).join(", ")} · term {s.term} · form by {s.form_deadline}
            {s.fee_head_code && ` · ${s.fee_head_code} fee must be paid`}
          </p>
        </div>
      </div>
      {err && <p className="form-error">{err.message}</p>}
      {verifyAll.data && <p className="auth-success">Verified {verifyAll.data.verified} eligible forms; {verifyAll.data.left} need a decision.</p>}
      {seats.data && <p className="auth-success">{seats.data.assigned} seat numbers given ({seats.data.total} in all).</p>}
      <section className="card">
        <div className="request-head">
          <h2 className="card-title">Paper timetable</h2>
          {canManage && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setPapers(true)}>
              Edit papers
            </button>
          )}
        </div>
        {s.papers.length === 0 ? (
          <p className="muted">Not set yet. Hall tickets show it once it is.</p>
        ) : (
          <ul className="marks-parts">
            {s.papers.map((p) => (
              <li key={p.subject_id}>
                <span>
                  {p.code} {p.name}
                </span>
                <b>
                  {p.date} {p.start}–{p.end}
                </b>
              </li>
            ))}
          </ul>
        )}
      </section>
      {canManage && (
        <div className="row-actions exam-actions">
          <button type="button" className="btn btn-primary btn-sm" onClick={() => verifyAll.mutate(id)}>
            Verify all eligible forms
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => seats.mutate(id)}>
            Give seat numbers
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => update.mutate({ id, hall_tickets_released: !s.hall_tickets_released })}>
            {s.hall_tickets_released ? "Withdraw hall tickets" : "Release hall tickets"}
          </button>
          <a className="btn btn-ghost btn-sm" href={examExportUrl(id)} download>
            Download list (CSV)
          </a>
        </div>
      )}
      <ResultsPanel sessionId={id} canManage={canManage} />
      <h2 className="subhead">Exam forms</h2>
      <div className="day-pick" role="group" aria-label="Filter">
        {[
          ["", "All"],
          ["not_submitted", "Not submitted"],
          ["submitted", "To verify"],
          ["verified", "Verified"],
          ["rejected", "Rejected"],
          ["ineligible", "Not eligible"],
        ].map(([v, label]) => (
          <button key={v || "all"} type="button" className={`btn btn-sm ${filter === v ? "btn-primary" : "btn-ghost"}`} onClick={() => setFilter(v)}>
            {label}
          </button>
        ))}
      </div>
      {forms.data && rows.length === 0 && <EmptyState title="Nobody here" />}
      {rows.length > 0 && (
        <div className="data-table-scroll">
          <table className="audit-table guard-table">
            <thead>
              <tr>
                <th>Student</th>
                <th>Form</th>
                <th>Attendance</th>
                <th>Fee</th>
                <th>Seat</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.student_id}>
                  <td>
                    {r.name}
                    <div className="muted small">
                      {r.prn} · {r.class}
                      {r.backlogs.length > 0 && ` · backlogs ${r.backlogs.join(", ")}`}
                    </div>
                  </td>
                  <td>
                    <StatusBadge tone={TONE[r.status]}>{r.status_label}</StatusBadge>
                    {r.reason && <div className="muted small">{r.reason}</div>}
                  </td>
                  <td className={r.attendance_ok ? "" : "att-critical"}>{r.attendance_ok ? "OK" : r.low_subjects.join(", ")}</td>
                  <td className={r.fee_ok ? "" : "att-critical"}>{r.fee_ok ? "Paid" : `${formatPaise(r.fee_due)} due`}</td>
                  <td>{r.seat_no ?? "–"}</td>
                  <td>
                    <div className="row-actions">
                      {canManage && (r.status === "submitted" || r.status === "rejected") && (
                        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setDeciding({ row: r, approve: true })}>
                          Verify
                        </button>
                      )}
                      {canManage && (r.status === "submitted" || r.status === "verified") && (
                        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setDeciding({ row: r, approve: false })}>
                          Reject
                        </button>
                      )}
                      {canManage && r.seat_no && r.status === "verified" && (
                        <a className="btn btn-ghost btn-sm" href={hallTicketUrl(id, r.student_id)} target="_blank" rel="noreferrer">
                          Hall ticket
                        </a>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <ConfirmDialog
        open={!!deciding}
        title={deciding?.approve ? `Verify ${deciding.row.name}'s form?` : `Reject ${deciding?.row.name}'s form?`}
        message={
          deciding?.approve
            ? deciding.row.eligible
              ? "The student is eligible."
              : "The student is NOT eligible (attendance or fee). Give the reason for verifying anyway, e.g. condonation by the Principal."
            : "Say why; the student sees it."
        }
        confirmLabel={deciding?.approve ? "Verify" : "Reject"}
        requireReason={deciding ? !(deciding.approve && deciding.row.eligible) : false}
        danger={deciding ? !deciding.approve : false}
        onCancel={() => setDeciding(null)}
        onConfirm={(reason) => {
          if (deciding) verify.mutate({ id, studentId: deciding.row.student_id, approve: deciding.approve, reason: reason || undefined });
          setDeciding(null);
        }}
      />
      {papers && <PapersModal session={s} onClose={() => setPapers(false)} />}
    </>
  );
}

function PapersModal({ session, onClose }: { session: ExamSession; onClose: () => void }) {
  const setup = useSetup();
  const update = useUpdateSession();
  const programmeIds = [...new Set(session.classes.map((c) => c.programme_id))];
  const subjects = useSubjects(programmeIds[0]);
  const semesters = new Set(
    session.classes.map((c) => {
      const p = setup.data?.programmes.find((x) => x.id === c.programme_id);
      return (c.year_of_study - 1) * (p?.semesters_per_year ?? 2) + session.term;
    }),
  );
  const options = (subjects.data ?? []).filter((x) => semesters.has(x.semester));
  const merged = session.papers.map((p) => ({ subject_id: p.subject_id, date: p.date, start: p.start, end: p.end }));
  for (const o of options) if (!merged.some((r) => r.subject_id === o.id)) merged.push({ subject_id: o.id, date: "", start: "10:00", end: "13:00" });
  const [draft, setDraft] = useState<typeof merged | null>(null);
  const list = draft ?? merged;
  const set = (i: number, k: string, v: string) => setDraft(list.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  return (
    <Modal open title="Paper timetable" onClose={onClose} wide>
      {update.error && <div className="form-error">{update.error.message}</div>}
      <p className="muted small">Leave the date empty for papers not in this exam.</p>
      {list.map((r, i) => {
        const sub = options.find((o) => o.id === r.subject_id) ?? session.papers.find((p) => p.subject_id === r.subject_id);
        return (
          <div className="field-row scheme-row" key={r.subject_id}>
            <div className="field">
              <label>{sub ? `${sub.code} ${sub.name}` : r.subject_id}</label>
            </div>
            <div className="field">
              <label htmlFor={`pp-date-${i}`}>Date</label>
              <input id={`pp-date-${i}`} type="date" value={r.date} onChange={(e) => set(i, "date", e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor={`pp-start-${i}`}>From</label>
              <input id={`pp-start-${i}`} type="time" value={r.start} onChange={(e) => set(i, "start", e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor={`pp-end-${i}`}>To</label>
              <input id={`pp-end-${i}`} type="time" value={r.end} onChange={(e) => set(i, "end", e.target.value)} />
            </div>
          </div>
        );
      })}
      <div className="modal-actions">
        <button type="button" className="btn btn-ghost" onClick={onClose}>
          Cancel
        </button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={update.isPending}
          onClick={() => update.mutate({ id: session.id, papers: list.filter((r) => r.date) }, { onSuccess: onClose })}
        >
          Save timetable
        </button>
      </div>
      {programmeIds.length > 1 && <p className="muted small">Subjects of the first programme are listed; add others from a separate exam.</p>}
    </Modal>
  );
}

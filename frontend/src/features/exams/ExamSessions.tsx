import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { EmptyState } from "../../components/EmptyState";
import { Modal } from "../../components/Modal";
import { ApiError } from "../../lib/api";
import { useCreateSession, useExamSessions } from "../../lib/exams";
import { useSetup } from "../../lib/setup";

/** Exam Cell: exam sessions (university or internal) with their form deadlines and counts. */
export default function ExamSessions({ canManage }: { canManage: boolean }) {
  const list = useExamSessions();
  const [creating, setCreating] = useState(false);
  return (
    <>
      <div className="tt-toolbar">
        <p className="muted" style={{ margin: 0, flex: 1 }}>
          Open an exam for some classes; students fill the form in their portal. Verify eligible forms, give seat numbers and release hall tickets.
        </p>
        {canManage && (
          <button type="button" className="btn btn-primary" onClick={() => setCreating(true)}>
            New exam
          </button>
        )}
      </div>
      {list.error && <p className="form-error">{list.error.message}</p>}
      {list.data?.length === 0 && <EmptyState title="No exams yet" />}
      <div className="request-list">
        {list.data?.map((s) => (
          <Link key={s.id} to={`/app/exams/sessions/${s.id}`} className="card request-card marks-card">
            <div className="request-head">
              <b>{s.name}</b>
              <span className="muted">{s.classes.map((c) => c.label).join(", ")} · term {s.term}</span>
            </div>
            <p className="muted small">
              Form by {s.form_deadline}
              {s.counts && ` · ${s.counts.submitted + s.counts.verified + s.counts.rejected} of ${s.counts.students} submitted, ${s.counts.verified} verified`}
              {s.hall_tickets_released && " · hall tickets released"}
            </p>
          </Link>
        ))}
      </div>
      {creating && <CreateExam onClose={() => setCreating(false)} />}
    </>
  );
}

function CreateExam({ onClose }: { onClose: () => void }) {
  const setup = useSetup();
  const create = useCreateSession();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [kind, setKind] = useState("university");
  const [term, setTerm] = useState(1);
  const [classes, setClasses] = useState<string[]>([]);
  const [deadline, setDeadline] = useState("");
  const [fee, setFee] = useState("EXAM");
  const [prefix, setPrefix] = useState("");
  const err = create.error instanceof ApiError ? create.error : null;
  const options = (setup.data?.programmes ?? [])
    .filter((p) => p.status === "active")
    .flatMap((p) => p.year_labels.map((label, i) => ({ key: `${p.id}:${i + 1}`, label: `${p.code} ${label}` })));
  return (
    <Modal open title="New exam" onClose={onClose} wide>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate(
            {
              name,
              kind,
              term,
              classes: classes.map((k) => ({ programme_id: k.split(":")[0], year_of_study: Number(k.split(":")[1]) })),
              form_deadline: deadline,
              fee_head_code: fee.trim() || null,
              seat_prefix: prefix.trim().toUpperCase(),
            },
            { onSuccess: (s) => navigate(`/app/exams/sessions/${s.id}`) },
          );
        }}
      >
        {err && <div className="form-error">{err.message}</div>}
        <div className="field">
          <label htmlFor="ex-name">Name</label>
          <input id="ex-name" placeholder="e.g. Oct–Nov 2026 university exams" value={name} onChange={(e) => setName(e.target.value)} required minLength={3} />
        </div>
        <div className="field-row">
          <div className="field">
            <label htmlFor="ex-kind">Kind</label>
            <select id="ex-kind" value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="university">University exam</option>
              <option value="internal">Internal exam</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="ex-term">Term</label>
            <select id="ex-term" value={term} onChange={(e) => setTerm(Number(e.target.value))}>
              <option value={1}>Term 1 (odd semester)</option>
              <option value={2}>Term 2 (even semester)</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="ex-deadline">Form deadline</label>
            <input id="ex-deadline" type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} required />
          </div>
        </div>
        <fieldset className="field">
          <legend>Classes</legend>
          <div className="teacher-picks">
            {options.map((o) => (
              <label key={o.key} className="check-label">
                <input type="checkbox" checked={classes.includes(o.key)} onChange={(e) => setClasses(e.target.checked ? [...classes, o.key] : classes.filter((x) => x !== o.key))} />{" "}
                {o.label}
              </label>
            ))}
          </div>
        </fieldset>
        <div className="field-row">
          <div className="field">
            <label htmlFor="ex-fee">Fee head that must be paid (empty: none)</label>
            <input id="ex-fee" value={fee} onChange={(e) => setFee(e.target.value.toUpperCase())} />
          </div>
          <div className="field">
            <label htmlFor="ex-prefix">Seat number prefix (optional)</label>
            <input id="ex-prefix" value={prefix} onChange={(e) => setPrefix(e.target.value.toUpperCase())} maxLength={8} />
          </div>
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={create.isPending || classes.length === 0}>
            Create
          </button>
        </div>
      </form>
    </Modal>
  );
}

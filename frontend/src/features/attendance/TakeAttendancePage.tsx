import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../../lib/api";
import { ATTENDANCE_KEY, saveAttendance, useRequestEdit, useSheet, type Sheet } from "../../lib/attendance";
import "./attendance.css";

/** The 10-second flow: everyone starts present; tap the absentees; save. */
export default function TakeAttendancePage() {
  const { slotId = "", date = "" } = useParams();
  const sheet = useSheet(slotId, date);
  if (sheet.error) return <p className="form-error">{sheet.error.message}</p>;
  if (!sheet.data) return <p className="muted">Loading the class list…</p>;
  // Remount when the server copy changes (e.g. after loading someone else's newer save).
  return <SheetForm key={`${sheet.data.session?.version ?? 0}`} data={sheet.data} slotId={slotId} date={date} />;
}

function SheetForm({ data, slotId, date }: { data: Sheet; slotId: string; date: string }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [absent, setAbsent] = useState<Set<string>>(() => new Set(data.session?.absent ?? []));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [asking, setAsking] = useState(false);
  const lec = data.lecture;
  const total = data.students.length;
  const readOnly = !data.can_save;

  const toggle = (id: string) => {
    if (readOnly && !data.can_request_edit) return;
    setAbsent((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await saveAttendance({ slot_id: slotId, date, absent: [...absent], base_version: data.session?.version ?? null, client_id: crypto.randomUUID() });
      await qc.invalidateQueries({ queryKey: ATTENDANCE_KEY });
      navigate("/app/attendance", { state: { saved: `${lec.subject_code}: ${total - absent.size} of ${total} present` } });
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, "error", "Could not save."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="take">
      <div className="page-head">
        <div>
          <div className="eyebrow">
            <Link to="/app/attendance">Attendance</Link> · {date}
          </div>
          <h1>
            {lec.subject_code} {lec.subject_name}
          </h1>
          <p className="muted">
            {lec.division} · {lec.start}–{lec.end}
            {lec.batch && ` · Batch ${lec.batch}`}
            {lec.room && ` · Room ${lec.room}`}
          </p>
        </div>
      </div>
      {data.session && (
        <p className="muted small">
          Saved by {data.session.saved_by} at {new Date(data.session.saved_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}.
          {data.can_save && " You can still change it."}
        </p>
      )}
      {readOnly && data.can_request_edit && (
        <div className="auth-success">The 48 hours for changes are over. Tap the students to correct, then ask your HOD to approve.</div>
      )}
      {readOnly && !data.can_request_edit && <div className="auth-success">View only.</div>}
      {error && (
        <div className="form-error" role="alert">
          {error.message}
          {error.code === "attendance_conflict" && (
            <>
              {" "}
              <button type="button" className="link-btn" onClick={() => qc.invalidateQueries({ queryKey: [...ATTENDANCE_KEY, "sheet", slotId, date] })}>
                Load their version
              </button>
            </>
          )}
        </div>
      )}
      {total === 0 && <p className="muted">No active students in this class.</p>}
      <ul className="roster" aria-label="Class list">
        {data.students.map((s) => {
          const isAbsent = absent.has(s.id);
          return (
            <li key={s.id}>
              <button
                type="button"
                className={`roster-row${isAbsent ? " absent" : ""}`}
                aria-pressed={isAbsent}
                onClick={() => toggle(s.id)}
                disabled={readOnly && !data.can_request_edit}
              >
                <span className="roster-roll">{s.roll_no ?? "–"}</span>
                <span className="roster-name">
                  {s.name}
                  <span className="muted small"> {s.prn}</span>
                  {s.exempt && <span className="roster-exempt">{s.exempt === "medical" ? "Medical" : "On duty"}</span>}
                </span>
                <span className="roster-mark">{isAbsent ? "Absent" : "Present"}</span>
              </button>
            </li>
          );
        })}
      </ul>
      <div className="take-bar">
        <span>
          <b>{total - absent.size}</b> present · <b className={absent.size ? "absent-count" : ""}>{absent.size}</b> absent
        </span>
        {data.can_save && (
          <button type="button" className="btn btn-primary" onClick={save} disabled={saving || total === 0}>
            {saving ? "Saving…" : "Save attendance"}
          </button>
        )}
        {!data.can_save && data.can_request_edit && (
          <button type="button" className="btn btn-primary" onClick={() => setAsking(true)}>
            Ask HOD to change
          </button>
        )}
      </div>
      {asking && <AskHod slotId={slotId} date={date} absent={[...absent]} onClose={() => setAsking(false)} />}
    </div>
  );
}

function AskHod({ slotId, date, absent, onClose }: { slotId: string; date: string; absent: string[]; onClose: () => void }) {
  const ask = useRequestEdit();
  const navigate = useNavigate();
  const [reason, setReason] = useState("");
  return (
    <div className="card ask-hod">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask.mutate(
            { slot_id: slotId, date, absent, reason },
            { onSuccess: () => navigate("/app/attendance", { state: { saved: "Sent to your HOD for approval." } }) },
          );
        }}
      >
        {ask.error && <div className="form-error">{ask.error.message}</div>}
        <div className="field">
          <label htmlFor="ask-reason">Why does it need changing?</label>
          <input id="ask-reason" value={reason} onChange={(e) => setReason(e.target.value)} required minLength={5} />
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={ask.isPending}>
            Send to HOD
          </button>
        </div>
      </form>
    </div>
  );
}

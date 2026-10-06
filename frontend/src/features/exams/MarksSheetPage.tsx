import { useState } from "react";
import { Link, useParams } from "react-router";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { StatusBadge } from "../../components/StatusBadge";
import { ApiError } from "../../lib/api";
import { STATUS_TONE, useSaveMarks, useSheet, useSheetAction, type MarkValue, type Sheet } from "../../lib/marks";
import "./exams.css";

/** Marks grid for one class and subject. Type a mark or AB (absent); Enter moves down the column. */
export default function MarksSheetPage() {
  const { divisionId = "", subjectId = "" } = useParams();
  const sheet = useSheet(divisionId, subjectId);
  if (sheet.error)
    return (
      <>
        <p className="form-error">{sheet.error.message}</p>
        <Link to="/app/exams">← Exams & results</Link>
      </>
    );
  if (!sheet.data) return <p className="muted">…</p>;
  return <Grid key={sheet.data.version + sheet.data.status} data={sheet.data} />;
}

type Cells = Record<string, Record<string, string>>;

const show = (v: MarkValue | undefined) => (v === undefined ? "" : String(v));

function Grid({ data }: { data: Sheet }) {
  const save = useSaveMarks();
  const action = useSheetAction();
  const initial: Cells = Object.fromEntries(data.students.map((s) => [s.id, Object.fromEntries(data.scheme.components.map((c) => [c.key, show(s.marks[c.key])]))]));
  const [cells, setCells] = useState<Cells>(initial);
  const [confirm, setConfirm] = useState<"publish" | "approve" | "return" | "lock" | "unlock" | null>(null);
  const comps = data.scheme.components;
  const changed = data.students.filter((s) => comps.some((c) => cells[s.id][c.key] !== initial[s.id][c.key]));
  const err = (save.error ?? action.error) as ApiError | null;

  const parse = (raw: string): MarkValue | null => {
    const v = raw.trim().toUpperCase();
    if (v === "") return null;
    if (v === "AB" || v === "A") return "AB";
    return Number(v);
  };
  const invalid = (raw: string, max: number) => {
    const v = parse(raw);
    return v !== null && v !== "AB" && (Number.isNaN(v) || v < 0 || v > max || Math.round(v * 2) !== v * 2);
  };
  const anyInvalid = data.students.some((s) => comps.some((c) => invalid(cells[s.id][c.key], c.max)));
  const total = (sid: string) => {
    let t = 0;
    for (const c of comps) {
      const v = parse(cells[sid][c.key]);
      if (v === null || (v !== "AB" && Number.isNaN(v))) return null;
      t += v === "AB" ? 0 : v;
    }
    return Math.round(t * 100) / 100;
  };
  const submit = () =>
    save.mutate({
      division_id: data.division_id,
      subject_id: data.subject.id,
      base_version: data.version,
      marks: Object.fromEntries(changed.map((s) => [s.id, Object.fromEntries(comps.map((c) => [c.key, parse(cells[s.id][c.key])]))])),
    });
  const run = (a: NonNullable<typeof confirm>, reason?: string) => action.mutate({ division_id: data.division_id, subject_id: data.subject.id, action: a, reason });

  return (
    <div className="marks-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">
            <Link to="/app/exams">Exams & results</Link> · {data.class}
          </div>
          <h1>
            {data.subject.code} {data.subject.name}
          </h1>
          <p className="muted">
            Internal marks out of {data.subject.max_internal}
            {data.scheme.deadline && ` · deadline ${data.scheme.deadline}`}
            {data.deadline_passed && " (passed)"}
          </p>
        </div>
        <StatusBadge tone={STATUS_TONE[data.status]}>{data.status_label}</StatusBadge>
      </div>
      {data.returned_reason && data.status === "draft" && <div className="form-error">Returned by the HOD: {data.returned_reason}</div>}
      {err && <div className="form-error">{err.message}</div>}
      {!data.can_edit && <p className="muted small">View only{data.approved_by ? ` · approved by ${data.approved_by}` : ""}{data.locked_by ? ` · locked by ${data.locked_by}` : ""}.</p>}
      {data.can_edit && <p className="muted small">Type a mark, or AB for absent. Enter moves down. Students see the marks once you publish them.</p>}
      <div className="data-table-scroll">
        <table className="marks-grid audit-table">
          <thead>
            <tr>
              <th>Roll</th>
              <th>Student</th>
              {comps.map((c) => (
                <th key={c.key}>
                  {c.name}
                  <div className="muted small">/ {c.max}</div>
                </th>
              ))}
              <th>Total</th>
            </tr>
          </thead>
          <tbody>
            {data.students.map((s, row) => (
              <tr key={s.id}>
                <td>{s.roll_no ?? "–"}</td>
                <td>
                  {s.name}
                  <div className="muted small">{s.prn}</div>
                </td>
                {comps.map((c, col) => (
                  <td key={c.key}>
                    <input
                      className={`mark-input${invalid(cells[s.id][c.key], c.max) ? " bad" : ""}`}
                      aria-label={`${s.name} ${c.name}`}
                      inputMode="decimal"
                      value={cells[s.id][c.key]}
                      disabled={!data.can_edit}
                      data-cell={`${row}:${col}`}
                      onChange={(e) => setCells({ ...cells, [s.id]: { ...cells[s.id], [c.key]: e.target.value } })}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          (document.querySelector(`[data-cell="${row + 1}:${col}"]`) as HTMLInputElement | null)?.focus();
                        }
                      }}
                    />
                  </td>
                ))}
                <td className="mark-total">{total(s.id) ?? "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="take-bar">
        <span className="small">{changed.length ? `${changed.length} student${changed.length > 1 ? "s" : ""} changed` : data.saved_by ? `Saved by ${data.saved_by}` : "Not saved yet"}</span>
        <div className="row-actions">
          {data.can_edit && (
            <button type="button" className="btn btn-primary" onClick={submit} disabled={save.isPending || anyInvalid || changed.length === 0}>
              Save marks
            </button>
          )}
          {data.can_publish && changed.length === 0 && (
            <button type="button" className="btn btn-ghost" onClick={() => setConfirm("publish")}>
              Publish to students
            </button>
          )}
          {data.can_return && (
            <button type="button" className="btn btn-ghost" onClick={() => setConfirm("return")}>
              Return to teacher
            </button>
          )}
          {data.can_approve && (
            <button type="button" className="btn btn-primary" onClick={() => setConfirm("approve")}>
              Approve
            </button>
          )}
          {data.can_lock && (
            <button type="button" className="btn btn-primary" onClick={() => setConfirm("lock")}>
              Lock
            </button>
          )}
          {data.can_unlock && (
            <button type="button" className="btn btn-ghost" onClick={() => setConfirm("unlock")}>
              Unlock
            </button>
          )}
        </div>
      </div>
      <ConfirmDialog
        open={!!confirm}
        title={
          confirm === "publish"
            ? "Publish these marks to students?"
            : confirm === "approve"
              ? "Approve these marks?"
              : confirm === "return"
                ? "Return to the teacher?"
                : confirm === "lock"
                  ? "Lock these marks?"
                  : "Unlock these marks?"
        }
        message={
          confirm === "publish"
            ? "Students see their marks. You can still correct them until the HOD approves."
            : confirm === "approve"
              ? "The teacher can no longer change them. The Exam Cell locks them for the university."
              : confirm === "lock"
                ? "Nobody can change them until the Exam Cell unlocks them."
                : "Say why; it is recorded in the audit log."
        }
        confirmLabel={confirm ? confirm[0].toUpperCase() + confirm.slice(1) : ""}
        requireReason={confirm === "return" || confirm === "unlock"}
        onCancel={() => setConfirm(null)}
        onConfirm={(reason) => {
          if (confirm) run(confirm, reason || undefined);
          setConfirm(null);
        }}
      />
    </div>
  );
}

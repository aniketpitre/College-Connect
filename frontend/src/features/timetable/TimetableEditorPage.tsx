import { useState } from "react";
import { Link, useParams } from "react-router";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { EmptyState } from "../../components/EmptyState";
import { Modal } from "../../components/Modal";
import { TIMETABLE_STRINGS } from "../../i18n/timetable";
import { ApiError } from "../../lib/api";
import { useRemoveSlot, useSaveSlot, useTimetable, useTimetableOptions, useUpdateTimetable, type Slot, type SlotInput } from "../../lib/timetable";
import "./timetable.css";

const DAYS = TIMETABLE_STRINGS.en.days;

/** Office / HOD: the weekly lectures of one class for one term. */
export default function TimetableEditorPage() {
  const { id } = useParams();
  const tt = useTimetable(id);
  const [editing, setEditing] = useState<Slot | "new" | null>(null);
  const [removing, setRemoving] = useState<Slot | null>(null);
  const remove = useRemoveSlot();
  const t = tt.data;

  if (tt.error) return <p className="form-error">{tt.error.message}</p>;
  if (!t) return <p className="muted">…</p>;
  const byDay = [1, 2, 3, 4, 5, 6].map((d) => ({ day: d, slots: t.slots.filter((s) => s.day === d) }));

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">
            <Link to="/app/timetable">Timetable</Link> · {t.academic_year}
          </div>
          <h1>
            {t.division} · Term {t.term}
          </h1>
          <p className="muted">Semester {t.semester}</p>
        </div>
        {t.can_manage && (
          <button type="button" className="btn btn-primary" onClick={() => setEditing("new")}>
            Add lecture
          </button>
        )}
      </div>
      <Dates id={t.id} from={t.valid_from} to={t.valid_to} canManage={t.can_manage} />
      {remove.error && <p className="form-error">{remove.error.message}</p>}
      {t.slots.length === 0 && <EmptyState title="No lectures yet" />}
      {byDay
        .filter((d) => d.slots.length)
        .map((d) => (
          <section key={d.day} className="card slot-day">
            <h2 className="card-title">{DAYS[d.day]}</h2>
            {d.slots.map((s) => (
              <div key={s.id} className="slot-row">
                <div>
                  <b>
                    {s.start}–{s.end}
                  </b>{" "}
                  {s.subject_code} {s.subject_name}
                  <div className="muted small">
                    {s.faculty.join(", ")}
                    {s.room && ` · Room ${s.room}`}
                    {s.batch && ` · Batch ${s.batch}`}
                  </div>
                </div>
                {t.can_manage && (
                  <div className="row-actions">
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditing(s)}>
                      Edit
                    </button>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => setRemoving(s)}>
                      Remove
                    </button>
                  </div>
                )}
              </div>
            ))}
          </section>
        ))}
      {editing && <SlotModal timetableId={t.id} slot={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
      <ConfirmDialog
        open={!!removing}
        title="Remove this lecture?"
        message={removing ? `${DAYS[removing.day]} ${removing.start} ${removing.subject_code}. Attendance already taken in it is kept.` : ""}
        confirmLabel="Remove"
        danger
        onCancel={() => setRemoving(null)}
        onConfirm={() => {
          if (removing) remove.mutate(removing.id);
          setRemoving(null);
        }}
      />
    </>
  );
}

function Dates({ id, from, to, canManage }: { id: string; from: string; to: string; canManage: boolean }) {
  const update = useUpdateTimetable();
  const [a, setA] = useState(from);
  const [b, setB] = useState(to);
  if (!canManage)
    return (
      <p className="muted">
        Lectures from {from} to {to}
      </p>
    );
  return (
    <form
      className="tt-toolbar"
      onSubmit={(e) => {
        e.preventDefault();
        update.mutate({ id, valid_from: a, valid_to: b });
      }}
    >
      <div className="field">
        <label htmlFor="tt-from">Lectures from</label>
        <input id="tt-from" type="date" value={a} onChange={(e) => setA(e.target.value)} required />
      </div>
      <div className="field">
        <label htmlFor="tt-to">Until</label>
        <input id="tt-to" type="date" value={b} onChange={(e) => setB(e.target.value)} required />
      </div>
      <button type="submit" className="btn btn-ghost" disabled={update.isPending || (a === from && b === to)}>
        Save dates
      </button>
      {update.error && <span className="form-error">{update.error.message}</span>}
    </form>
  );
}

function SlotModal({ timetableId, slot, onClose }: { timetableId: string; slot: Slot | null; onClose: () => void }) {
  const options = useTimetableOptions(timetableId, true);
  const save = useSaveSlot();
  const [form, setForm] = useState<SlotInput>({
    day: slot?.day ?? 1,
    start: slot?.start ?? "09:00",
    end: slot?.end ?? "10:00",
    subject_id: slot?.subject_id ?? "",
    faculty_ids: slot?.faculty_ids ?? [],
    room: slot?.room ?? "",
    batch: slot?.batch ?? null,
  });
  const [filter, setFilter] = useState("");
  const err = save.error instanceof ApiError ? save.error : null;
  const teachers = (options.data?.faculty ?? []).filter((f) => form.faculty_ids.includes(f.id) || f.name.toLowerCase().includes(filter.toLowerCase()));

  return (
    <Modal open title={slot ? "Edit lecture" : "Add lecture"} onClose={onClose} wide>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate({ timetableId, slotId: slot?.id, body: { ...form, batch: form.batch?.trim() || null } }, { onSuccess: onClose });
        }}
      >
        {err && <div className="form-error">{err.message}</div>}
        <div className="field-row">
          <div className="field">
            <label htmlFor="sl-day">Day</label>
            <select id="sl-day" value={form.day} onChange={(e) => setForm({ ...form, day: Number(e.target.value) })}>
              {[1, 2, 3, 4, 5, 6].map((d) => (
                <option key={d} value={d}>
                  {DAYS[d]}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="sl-start">Starts</label>
            <input id="sl-start" type="time" value={form.start} onChange={(e) => setForm({ ...form, start: e.target.value })} required />
          </div>
          <div className="field">
            <label htmlFor="sl-end">Ends</label>
            <input id="sl-end" type="time" value={form.end} onChange={(e) => setForm({ ...form, end: e.target.value })} required />
          </div>
        </div>
        <div className="field">
          <label htmlFor="sl-subject">Subject</label>
          <select id="sl-subject" value={form.subject_id} onChange={(e) => setForm({ ...form, subject_id: e.target.value })} required>
            <option value="">Choose…</option>
            {options.data?.subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {s.code} · {s.name}
                {s.type !== "theory" ? ` (${s.type})` : ""}
              </option>
            ))}
          </select>
          {options.data?.subjects.length === 0 && <span className="field-hint">Add this semester's subjects in College setup → Subjects first.</span>}
        </div>
        <fieldset className="field">
          <legend>Teacher(s)</legend>
          <input aria-label="Find a teacher" placeholder="Find a teacher" value={filter} onChange={(e) => setFilter(e.target.value)} />
          <div className="teacher-picks">
            {teachers.map((f) => (
              <label key={f.id} className="check-label">
                <input
                  type="checkbox"
                  checked={form.faculty_ids.includes(f.id)}
                  onChange={(e) =>
                    setForm({ ...form, faculty_ids: e.target.checked ? [...form.faculty_ids, f.id] : form.faculty_ids.filter((x) => x !== f.id) })
                  }
                />{" "}
                {f.name}
              </label>
            ))}
          </div>
          {err?.field === "faculty_ids" && <span className="field-error">{err.message}</span>}
        </fieldset>
        <div className="field-row">
          <div className="field">
            <label htmlFor="sl-room">Room</label>
            <input id="sl-room" list="sl-rooms" value={form.room} onChange={(e) => setForm({ ...form, room: e.target.value })} />
            <datalist id="sl-rooms">
              {options.data?.rooms.map((r) => (
                <option key={r} value={r} />
              ))}
            </datalist>
          </div>
          <div className="field">
            <label htmlFor="sl-batch">Practical batch (optional)</label>
            <input id="sl-batch" placeholder="e.g. B1" value={form.batch ?? ""} onChange={(e) => setForm({ ...form, batch: e.target.value })} />
          </div>
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={save.isPending || form.faculty_ids.length === 0}>
            Save
          </button>
        </div>
      </form>
    </Modal>
  );
}

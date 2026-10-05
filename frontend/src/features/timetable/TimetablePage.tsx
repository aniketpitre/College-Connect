import { useState } from "react";
import { Link, useNavigate } from "react-router";
import LanguageToggle from "../../app/LanguageToggle";
import { EmptyState } from "../../components/EmptyState";
import { Modal } from "../../components/Modal";
import { TIMETABLE_STRINGS, type TimetableStrings } from "../../i18n/timetable";
import { ApiError } from "../../lib/api";
import { hasPermission, useMe } from "../../lib/auth";
import { useLanguage } from "../../lib/language";
import { classLabel, useSetup } from "../../lib/setup";
import {
  isoDay,
  shiftDays,
  useCreateTimetable,
  useSetChange,
  useTimetableOptions,
  useTimetables,
  useUndoChange,
  useWeek,
  type Lecture,
} from "../../lib/timetable";
import { WeekView } from "./WeekView";
import "./timetable.css";

const EN = TIMETABLE_STRINGS.en;

function WeekNav({ day, setDay, T, today }: { day: string; setDay: (d: string) => void; T: TimetableStrings; today: string }) {
  return (
    <div className="week-nav">
      <button type="button" className="btn btn-ghost btn-sm" onClick={() => setDay(shiftDays(day, -7))}>
        {T.prev}
      </button>
      <button type="button" className="btn btn-ghost btn-sm" onClick={() => setDay(today)} disabled={day === today}>
        {T.thisWeek}
      </button>
      <button type="button" className="btn btn-ghost btn-sm" onClick={() => setDay(shiftDays(day, 7))}>
        {T.next}
      </button>
    </div>
  );
}

/** Students: their own division's week, in their language. */
function StudentTimetable() {
  const [language, setLanguage] = useLanguage();
  const T = TIMETABLE_STRINGS[language];
  const [today] = useState(() => isoDay(new Date()));
  const [day, setDay] = useState(today);
  const week = useWeek({ student: true, day });
  const noDivision = week.error instanceof ApiError && week.error.code === "no_division";
  return (
    <div lang={language}>
      <div className="page-head">
        <h1>{T.title}</h1>
        <LanguageToggle value={language} onChange={setLanguage} />
      </div>
      <WeekNav day={day} setDay={setDay} T={T} today={today} />
      {noDivision && <EmptyState title={T.noDivision} />}
      {week.error && !noDivision && <p className="form-error">{week.error.message}</p>}
      {week.data && <WeekView week={week.data} T={T} today={today} />}
    </div>
  );
}

type Tab = "mine" | "class" | "manage";

export default function TimetablePage() {
  const { data: me } = useMe();
  if (me?.kind === "student") return <StudentTimetable />;
  return <StaffTimetable />;
}

function StaffTimetable() {
  const { data: me } = useMe();
  const setup = useSetup();
  const teaches = hasPermission(me, "attendance.take");
  const manager = hasPermission(me, "timetable.manage") || hasPermission(me, "timetable.manage.dept");
  const [tab, setTab] = useState<Tab>(teaches ? "mine" : "class");
  const [today] = useState(() => isoDay(new Date()));
  const [day, setDay] = useState(today);
  const [divisionId, setDivisionId] = useState("");
  const [changing, setChanging] = useState<Lecture | null>(null);
  const week = useWeek({ mine: tab === "mine", divisionId: tab === "class" ? divisionId : undefined, day });
  const divisions = (setup.data?.divisions ?? []).filter((d) => d.status === "active");
  const tabs: [Tab, string][] = [
    ...(teaches ? ([["mine", "My week"]] as [Tab, string][]) : []),
    ["class", "Class timetable"],
    ...(manager ? ([["manage", "Set up timetables"]] as [Tab, string][]) : []),
  ];

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Academics</div>
          <h1>Timetable</h1>
        </div>
      </div>
      <div className="tabs" role="tablist">
        {tabs.map(([id, label]) => (
          <button key={id} type="button" role="tab" aria-selected={tab === id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>
            {label}
          </button>
        ))}
      </div>
      {tab === "manage" ? (
        <ManageTimetables />
      ) : (
        <>
          {tab === "class" && (
            <div className="tt-toolbar">
              <div className="field">
                <label htmlFor="tt-division">Class</label>
                <select id="tt-division" value={divisionId} onChange={(e) => setDivisionId(e.target.value)}>
                  <option value="">Choose a class…</option>
                  {divisions.map((d) => (
                    <option key={d.id} value={d.id}>
                      {classLabel(setup.data, d.programme_id, d.year_of_study, d.id)}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          )}
          <WeekNav day={day} setDay={setDay} T={EN} today={today} />
          {tab === "class" && manager && divisionId && <p className="muted small">Click a lecture to cancel it for that day or give it to a substitute.</p>}
          {week.error && <p className="form-error">{week.error.message}</p>}
          {week.data && (
            <WeekView
              week={week.data}
              T={EN}
              today={today}
              showDivision={tab === "mine"}
              onLecture={tab === "class" && manager ? setChanging : undefined}
            />
          )}
        </>
      )}
      {changing && <ChangeModal lecture={changing} onClose={() => setChanging(null)} />}
    </>
  );
}

function ManageTimetables() {
  const setup = useSetup();
  const year = setup.data?.current_year;
  const list = useTimetables(year?.id);
  const [creating, setCreating] = useState(false);
  return (
    <>
      <div className="tt-toolbar">
        <p className="muted" style={{ margin: 0, flex: 1 }}>
          One timetable per class and term{year ? ` (${year.name})` : ""}. Lectures repeat every week between its dates; clashes of teachers, rooms and classes are refused.
        </p>
        <button type="button" className="btn btn-primary" onClick={() => setCreating(true)} disabled={!year}>
          New timetable
        </button>
      </div>
      {!year && <EmptyState title="Set the current academic year in College setup first" />}
      {list.data?.length === 0 && <EmptyState title="No timetables yet" />}
      <div className="request-list">
        {list.data?.map((t) => (
          <Link key={t.id} to={`/app/timetable/${t.id}`} className="card request-card" style={{ color: "inherit", textDecoration: "none" }}>
            <div className="request-head">
              <b>{t.division}</b>
              <span className="muted">
                Term {t.term} · Semester {t.semester}
              </span>
            </div>
            <p className="muted small">
              {t.valid_from} to {t.valid_to} · {t.slots} lectures a week{t.can_manage ? "" : " · read only"}
            </p>
          </Link>
        ))}
      </div>
      {creating && year && <CreateTimetableModal onClose={() => setCreating(false)} />}
    </>
  );
}

function CreateTimetableModal({ onClose }: { onClose: () => void }) {
  const setup = useSetup();
  const year = setup.data?.current_year;
  const create = useCreateTimetable();
  const navigate = useNavigate();
  const [divisionId, setDivisionId] = useState("");
  const [term, setTerm] = useState(1);
  const [from, setFrom] = useState(year?.start_date ?? "");
  const [to, setTo] = useState(year?.end_date ?? "");
  const division = setup.data?.divisions.find((d) => d.id === divisionId);
  const programme = setup.data?.programmes.find((p) => p.id === division?.programme_id);
  const err = create.error instanceof ApiError ? create.error : null;
  return (
    <Modal open title="New timetable" onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!year) return;
          create.mutate(
            { academic_year_id: year.id, division_id: divisionId, term, valid_from: from, valid_to: to },
            { onSuccess: (t) => navigate(`/app/timetable/${t.id}`) },
          );
        }}
      >
        {err && <div className="form-error">{err.message}</div>}
        <div className="field">
          <label htmlFor="nt-division">Class</label>
          <select id="nt-division" value={divisionId} onChange={(e) => setDivisionId(e.target.value)} required>
            <option value="">Choose…</option>
            {(setup.data?.divisions ?? [])
              .filter((d) => d.status === "active")
              .map((d) => (
                <option key={d.id} value={d.id}>
                  {classLabel(setup.data, d.programme_id, d.year_of_study, d.id)}
                </option>
              ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="nt-term">Term</label>
          <select id="nt-term" value={term} onChange={(e) => setTerm(Number(e.target.value))}>
            {Array.from({ length: programme?.semesters_per_year ?? 2 }, (_, i) => i + 1).map((n) => (
              <option key={n} value={n}>
                Term {n}
                {division && programme ? ` (semester ${(division.year_of_study - 1) * programme.semesters_per_year + n})` : ""}
              </option>
            ))}
          </select>
        </div>
        <div className="field-row">
          <div className="field">
            <label htmlFor="nt-from">Lectures from</label>
            <input id="nt-from" type="date" value={from} min={year?.start_date} max={year?.end_date} onChange={(e) => setFrom(e.target.value)} required />
          </div>
          <div className="field">
            <label htmlFor="nt-to">Until</label>
            <input id="nt-to" type="date" value={to} min={from} max={year?.end_date} onChange={(e) => setTo(e.target.value)} required />
          </div>
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={create.isPending}>
            Create
          </button>
        </div>
      </form>
    </Modal>
  );
}

/** Cancel one day's lecture, hand it to a substitute, or undo that. */
function ChangeModal({ lecture, onClose }: { lecture: Lecture; onClose: () => void }) {
  const options = useTimetableOptions(lecture.timetable_id, true);
  const setChange = useSetChange();
  const undo = useUndoChange();
  const [kind, setKind] = useState<"cancelled" | "substitute">("cancelled");
  const [teacher, setTeacher] = useState("");
  const [room, setRoom] = useState("");
  const [reason, setReason] = useState("");
  const changed = lecture.status !== "scheduled";
  const err = (setChange.error ?? undo.error) as ApiError | null;
  return (
    <Modal open title={`${lecture.subject_code} · ${lecture.date} ${lecture.start}`} onClose={onClose}>
      {err && <div className="form-error">{err.message}</div>}
      {changed ? (
        <>
          <p>
            {lecture.status === "cancelled" ? "Cancelled" : `Taken by ${lecture.substitute.join(", ")}`} on this day. Reason: {lecture.change_reason}
          </p>
          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>
              Close
            </button>
            <button type="button" className="btn btn-primary" onClick={() => undo.mutate({ slotId: lecture.slot_id, date: lecture.date }, { onSuccess: onClose })}>
              Undo the change
            </button>
          </div>
        </>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setChange.mutate(
              { slotId: lecture.slot_id, date: lecture.date, kind, faculty_ids: kind === "substitute" ? [teacher] : [], room, reason },
              { onSuccess: onClose },
            );
          }}
        >
          <div className="field">
            <label htmlFor="ch-kind">Change</label>
            <select id="ch-kind" value={kind} onChange={(e) => setKind(e.target.value as "cancelled" | "substitute")}>
              <option value="cancelled">Cancel this lecture</option>
              <option value="substitute">A substitute takes it</option>
            </select>
          </div>
          {kind === "substitute" && (
            <>
              <div className="field">
                <label htmlFor="ch-teacher">Substitute</label>
                <select id="ch-teacher" value={teacher} onChange={(e) => setTeacher(e.target.value)} required>
                  <option value="">Choose…</option>
                  {options.data?.faculty
                    .filter((f) => !lecture.faculty_ids.includes(f.id))
                    .map((f) => (
                      <option key={f.id} value={f.id}>
                        {f.name}
                      </option>
                    ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="ch-room">Room (if different)</label>
                <input id="ch-room" value={room} onChange={(e) => setRoom(e.target.value)} />
              </div>
            </>
          )}
          <div className="field">
            <label htmlFor="ch-reason">Reason (students see it)</label>
            <input id="ch-reason" value={reason} onChange={(e) => setReason(e.target.value)} required minLength={3} />
          </div>
          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={setChange.isPending}>
              Save
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}

import { useState } from "react";
import { Link } from "react-router";
import LanguageToggle from "../../app/LanguageToggle";
import { EmptyState } from "../../components/EmptyState";
import { Modal } from "../../components/Modal";
import { StatusBadge } from "../../components/StatusBadge";
import { MARKS_STRINGS } from "../../i18n/marks";
import { ApiError } from "../../lib/api";
import { hasPermission, useMe } from "../../lib/auth";
import { useLanguage } from "../../lib/language";
import { STATUS_TONE, useMarksOverview, useMyClasses, useMyMarks, useSaveScheme, useSchemes, type ClassRow, type SchemeRow, type SheetStatus } from "../../lib/marks";
import { useSetup } from "../../lib/setup";
import ExamSessions from "./ExamSessions";
import Revaluations from "./Revaluations";
import StudentExamForms from "./StudentExamForms";
import StudentResults from "./StudentResults";
import UploadGuard from "./UploadGuard";
import "./exams.css";

/** Exams & results: students see their marks; staff enter, approve and lock marks and set schemes. */
export default function ExamsPage() {
  const { data: me } = useMe();
  if (me?.kind === "student") return <StudentMarks />;
  return <StaffExams />;
}

function StaffExams() {
  const { data: me } = useMe();
  const teaches = hasPermission(me, "marks.enter");
  const oversees = ["marks.approve", "marks.read", "exams.manage"].some((p) => hasPermission(me, p));
  const schemes = hasPermission(me, "exams.manage") || hasPermission(me, "marks.scheme.dept");
  const tabs: [string, string][] = [
    ...(teaches ? ([["mine", "My classes"]] as [string, string][]) : []),
    ...(oversees ? ([["department", hasPermission(me, "marks.approve") && !hasPermission(me, "exams.manage") ? "Department marks" : "All marks"]] as [string, string][]) : []),
    ...(schemes ? ([["schemes", "Assessment schemes"]] as [string, string][]) : []),
    ...(hasPermission(me, "exams.manage") || hasPermission(me, "marks.approve") ? ([["guard", "Upload Guard"]] as [string, string][]) : []),
    ...(hasPermission(me, "exams.manage") || hasPermission(me, "results.read") ? ([["forms", "Exams"], ["revals", "Revaluation"]] as [string, string][]) : []),
  ];
  const [tab, setTab] = useState(tabs[0]?.[0]);
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Academics</div>
          <h1>Exams & results</h1>
        </div>
      </div>
      <div className="tabs" role="tablist">
        {tabs.map(([id, label]) => (
          <button key={id} type="button" role="tab" aria-selected={tab === id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>
            {label}
          </button>
        ))}
      </div>
      {tab === "mine" && <ClassList mine />}
      {tab === "department" && <ClassList />}
      {tab === "schemes" && <Schemes />}
      {tab === "guard" && <UploadGuard canExport={hasPermission(me, "exams.manage")} />}
      {tab === "forms" && <ExamSessions canManage={hasPermission(me, "exams.manage")} />}
      {tab === "revals" && <Revaluations canManage={hasPermission(me, "exams.manage")} />}
    </>
  );
}

function ClassList({ mine }: { mine?: boolean }) {
  const own = useMyClasses(Boolean(mine));
  const all = useMarksOverview(!mine);
  const list = mine ? own : all;
  const [filter, setFilter] = useState<SheetStatus | "">("");
  const rows = (list.data ?? []).filter((r) => !filter || r.status === filter);
  return (
    <>
      {!mine && (
        <div className="day-pick" role="group" aria-label="Status">
          {(["", "draft", "published", "approved", "locked"] as const).map((s) => (
            <button key={s || "all"} type="button" className={`btn btn-sm ${filter === s ? "btn-primary" : "btn-ghost"}`} onClick={() => setFilter(s)}>
              {s === "" ? "All" : s === "published" ? "Waiting for HOD" : s[0].toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      )}
      {list.error && <p className="form-error">{list.error.message}</p>}
      {list.data && rows.length === 0 && <EmptyState title={mine ? "No subjects in your timetable this year" : "Nothing here"} />}
      <div className="request-list">
        {rows.map((r) => (
          <ClassCard key={`${r.division_id}:${r.subject_id}`} r={r} />
        ))}
      </div>
    </>
  );
}

function ClassCard({ r }: { r: ClassRow }) {
  return (
    <Link to={`/app/exams/marks/${r.division_id}/${r.subject_id}`} className="card request-card marks-card">
      <div className="request-head">
        <b>
          {r.class} · {r.code}
        </b>
        <span className="muted">{r.name}</span>
        <StatusBadge tone={STATUS_TONE[r.status]}>{r.status_label}</StatusBadge>
      </div>
      <p className="muted small">
        {r.has_scheme ? `${r.complete} of ${r.students} students complete` : "No assessment scheme yet"}
        {r.deadline && ` · deadline ${r.deadline}`}
      </p>
    </Link>
  );
}

function Schemes() {
  const setup = useSetup();
  const [programmeId, setProgrammeId] = useState("");
  const [semester, setSemester] = useState("");
  const list = useSchemes(programmeId, semester);
  const [editing, setEditing] = useState<SchemeRow | null>(null);
  const programme = setup.data?.programmes.find((p) => p.id === programmeId);
  const { data: me } = useMe();
  return (
    <>
      <div className="tt-toolbar">
        <div className="field">
          <label htmlFor="sc-programme">Programme</label>
          <select id="sc-programme" value={programmeId} onChange={(e) => (setProgrammeId(e.target.value), setSemester(""))}>
            <option value="">Choose…</option>
            {setup.data?.programmes
              .filter((p) => p.status === "active")
              .map((p) => (
                <option key={p.id} value={p.id}>
                  {p.code} · {p.name}
                </option>
              ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="sc-sem">Semester</label>
          <select id="sc-sem" value={semester} onChange={(e) => setSemester(e.target.value)} disabled={!programme}>
            <option value="">All</option>
            {Array.from({ length: (programme?.duration_years ?? 0) * (programme?.semesters_per_year ?? 0) }, (_, i) => i + 1).map((n) => (
              <option key={n} value={n}>
                Semester {n}
              </option>
            ))}
          </select>
        </div>
      </div>
      {list.error && <p className="form-error">{list.error.message}</p>}
      {list.data?.length === 0 && <EmptyState title="No subjects. Add them in College setup → Subjects." />}
      <div className="request-list">
        {list.data?.map((s) => (
          <div key={s.subject_id} className="card request-card">
            <div className="request-head">
              <b>{s.code}</b> <span className="muted">{s.name}</span>
              <span className="muted small">Sem {s.semester} · {s.max_internal} internal marks</span>
            </div>
            <p className="request-reason">
              {s.scheme ? s.scheme.components.map((c) => `${c.name} ${c.max}`).join(" + ") : <span className="muted">No scheme yet</span>}
              {s.scheme?.deadline && <span className="muted"> · deadline {s.scheme.deadline}</span>}
            </p>
            {s.can_manage && (
              <div className="row-actions">
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditing(s)}>
                  {s.scheme ? "Edit scheme" : "Set scheme"}
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
      {editing && <SchemeModal row={editing} canSetDeadline={hasPermission(me, "exams.manage")} onClose={() => setEditing(null)} />}
    </>
  );
}

function SchemeModal({ row, canSetDeadline, onClose }: { row: SchemeRow; canSetDeadline: boolean; onClose: () => void }) {
  const save = useSaveScheme();
  const [parts, setParts] = useState(
    row.scheme?.components.map((c) => ({ key: c.key as string | undefined, name: c.name, max: String(c.max), held_on: c.held_on ?? "" })) ?? [
      { key: undefined, name: "Unit test 1", max: "", held_on: "" },
    ],
  );
  const [deadline, setDeadline] = useState(row.scheme?.deadline ?? "");
  const sum = parts.reduce((a, p) => a + (Number(p.max) || 0), 0);
  const err = save.error instanceof ApiError ? save.error : null;
  return (
    <Modal open title={`${row.code} · assessment scheme`} onClose={onClose} wide>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate(
            {
              subject_id: row.subject_id,
              components: parts.map((p) => ({ key: p.key, name: p.name, max: Number(p.max), held_on: p.held_on || null })),
              ...(canSetDeadline ? { deadline: deadline || null } : {}),
            },
            { onSuccess: onClose },
          );
        }}
      >
        {err && <div className="form-error">{err.message}</div>}
        <p className="muted small">The parts must add up to {row.max_internal} internal marks. The test date is used to flag students marked who were absent that day.</p>
        {parts.map((p, i) => (
          <div className="field-row scheme-row" key={i}>
            <div className="field">
              <label htmlFor={`sp-name-${i}`}>Part {i + 1}</label>
              <input id={`sp-name-${i}`} value={p.name} onChange={(e) => setParts(parts.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} required minLength={2} />
            </div>
            <div className="field">
              <label htmlFor={`sp-max-${i}`}>Out of</label>
              <input id={`sp-max-${i}`} type="number" min={0.5} step={0.5} value={p.max} onChange={(e) => setParts(parts.map((x, j) => (j === i ? { ...x, max: e.target.value } : x)))} required />
            </div>
            <div className="field">
              <label htmlFor={`sp-date-${i}`}>Test date (optional)</label>
              <input id={`sp-date-${i}`} type="date" value={p.held_on} onChange={(e) => setParts(parts.map((x, j) => (j === i ? { ...x, held_on: e.target.value } : x)))} />
            </div>
            <button type="button" className="link-btn" onClick={() => setParts(parts.filter((_, j) => j !== i))} disabled={parts.length === 1} aria-label={`Remove part ${i + 1}`}>
              Remove
            </button>
          </div>
        ))}
        <button type="button" className="link-btn" onClick={() => setParts([...parts, { key: undefined, name: "", max: "", held_on: "" }])}>
          + Add a part
        </button>
        <p className={sum === row.max_internal ? "muted" : "field-error"}>
          Total {sum} of {row.max_internal}
        </p>
        {canSetDeadline && (
          <div className="field">
            <label htmlFor="sp-deadline">Last day for marks entry</label>
            <input id="sp-deadline" type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
          </div>
        )}
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={save.isPending || sum !== row.max_internal}>
            Save scheme
          </button>
        </div>
      </form>
    </Modal>
  );
}

/** A student's own internal marks, in their language. */
function StudentMarks() {
  const [language, setLanguage] = useLanguage();
  const T = MARKS_STRINGS[language];
  const marks = useMyMarks();
  return (
    <div lang={language}>
      <div className="page-head">
        <h1>{T.title}</h1>
        <LanguageToggle value={language} onChange={setLanguage} />
      </div>
      <StudentResults />
      <StudentExamForms />
      <h2 className="subhead">{T.internalMarks}</h2>
      {marks.error && <p className="form-error">{marks.error.message}</p>}
      {marks.data?.length === 0 && <EmptyState title={T.none} />}
      <div className="att-subjects">
        {marks.data?.map((m) => (
          <section key={m.subject_id} className="card att-subject">
            <div className="att-head">
              <div>
                <b>{m.code}</b> <span className="muted">{m.name}</span>
              </div>
              <div className="att-percent">
                {m.total ?? "–"}
                <span className="muted small"> {T.outOf(m.out_of)}</span>
              </div>
            </div>
            <ul className="marks-parts">
              {m.components.map((c) => (
                <li key={c.name}>
                  <span>{c.name}</span>
                  <b>{c.mark === null ? <span className="muted">{T.notEntered}</span> : c.mark === "AB" ? T.absent : `${c.mark} / ${c.max}`}</b>
                </li>
              ))}
            </ul>
            <div className="muted small">{T.status[m.status]}</div>
          </section>
        ))}
      </div>
    </div>
  );
}

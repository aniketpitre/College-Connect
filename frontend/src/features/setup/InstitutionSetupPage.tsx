import { useState } from "react";
import { StatusBadge } from "../../components/StatusBadge";
import { ApiError } from "../../lib/api";
import { hasPermission, useMe } from "../../lib/auth";
import { useHolidays, useSetup, useSetupAction, useSubjects, type Institution, type SetupOverview } from "../../lib/setup";
import { RecordSection } from "./RecordSection";
import "./setup.css";

const TABS = ["College", "Academic years", "Programmes", "Subjects", "Categories", "Holidays"] as const;
type Tab = (typeof TABS)[number];

/** Staff screen (English). Everyone on staff can read it; System Admin can change it. */
export default function InstitutionSetupPage() {
  const { data: me } = useMe();
  const setup = useSetup();
  const [tab, setTab] = useState<Tab>("College");
  const canManage = hasPermission(me, "setup.manage");
  const starter = useSetupAction<Record<string, number>>();
  const data = setup.data;
  const empty = data && data.programmes.length === 0 && data.academic_years.length === 0;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Administration</div>
          <h1>College setup</h1>
        </div>
        {data?.current_year && <StatusBadge tone="info">Current year {data.current_year.name}</StatusBadge>}
      </div>

      {empty && canManage && (
        <div className="card starter-card">
          <div>
            <b>Starting fresh?</b> Load the standard categories, a Computer Science department with BCA (FY/SY/TY, division A) and the
            current academic year. You can edit everything afterwards.
          </div>
          <button type="button" className="btn btn-primary" disabled={starter.isPending} onClick={() => starter.mutate({ path: "starter-data" })}>
            Load starter data
          </button>
        </div>
      )}

      <div className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t} type="button" role="tab" aria-selected={tab === t} className={tab === t ? "active" : ""} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </div>

      {setup.error && <p className="form-error">{setup.error.message}</p>}
      {!data ? (
        <p className="muted">Loading…</p>
      ) : (
        <>
          {tab === "College" && <CollegeForm key={JSON.stringify(data.institution)} institution={data.institution} canManage={canManage} />}
          {tab === "Academic years" && <YearsTab data={data} canManage={canManage} />}
          {tab === "Programmes" && <ProgrammesTab data={data} canManage={canManage} />}
          {tab === "Subjects" && <SubjectsTab data={data} canManage={canManage} />}
          {tab === "Categories" && (
            <RecordSection
              title="Categories"
              path="categories"
              rows={data.categories}
              canManage={canManage}
              columns={[
                { key: "code", header: "Code", render: (c) => <b>{c.code}</b>, searchText: (c) => c.code },
                { key: "name", header: "Name", render: (c) => c.name, searchText: (c) => c.name },
                { key: "reserved", header: "Reserved %", render: (c) => (c.reserved_percent ?? "—").toString() },
              ]}
              fields={[
                { name: "code", label: "Code", required: true, hint: "e.g. OBC" },
                { name: "name", label: "Name", required: true, editable: true },
                { name: "reserved_percent", label: "Reserved seats (%)", type: "number", editable: true },
              ]}
            />
          )}
          {tab === "Holidays" && <HolidaysTab data={data} canManage={canManage} />}
        </>
      )}
    </>
  );
}

const fmtDate = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });

function CollegeForm({ institution, canManage }: { institution: Institution; canManage: boolean }) {
  const [form, setForm] = useState<Institution>(institution);
  const save = useSetupAction();
  const err = save.error instanceof ApiError ? save.error : null;
  const fields: [keyof Institution, string, string?][] = [
    ["name", "College name"],
    ["short_name", "Short name"],
    ["university", "Affiliated university"],
    ["college_code", "College code (university / AISHE)"],
    ["address", "Address"],
    ["phone", "Phone"],
    ["email", "Email"],
    ["website", "Website"],
    ["receipt_prefix", "Receipt prefix", `Receipts are numbered ${form.receipt_prefix || "R"}/2026-27/000123`],
    ["certificate_prefix", "Certificate prefix"],
  ];
  return (
    <form
      className="card"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate({ path: "institution", method: "PUT", body: { ...form, email: form.email || null } });
      }}
    >
      {err && !err.field && <div className="form-error">{err.message}</div>}
      <div className="field-row">
        {fields.map(([key, label, hint]) => (
          <div className="field" key={key}>
            <label htmlFor={`i-${key}`}>{label}</label>
            <input id={`i-${key}`} value={form[key] ?? ""} disabled={!canManage} onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
            {hint && <span className="field-hint">{hint}</span>}
            {err?.field === key && <span className="field-error">{err.message}</span>}
          </div>
        ))}
      </div>
      {canManage && (
        <div className="modal-actions">
          {save.isSuccess && <span className="muted">Saved.</span>}
          <button type="submit" className="btn btn-primary" disabled={save.isPending}>
            Save
          </button>
        </div>
      )}
    </form>
  );
}

function YearsTab({ data, canManage }: { data: SetupOverview; canManage: boolean }) {
  const action = useSetupAction();
  return (
    <RecordSection
      title="Academic years"
      path="academic-years"
      rows={data.academic_years}
      canManage={canManage}
      columns={[
        { key: "name", header: "Year", render: (y) => <b>{y.name}</b>, searchText: (y) => y.name },
        { key: "dates", header: "Dates", render: (y) => `${fmtDate(y.start_date)} – ${fmtDate(y.end_date)}` },
        { key: "current", header: "", render: (y) => (y.is_current ? <StatusBadge tone="success">Current</StatusBadge> : null) },
      ]}
      fields={[
        { name: "name", label: "Name", required: true, hint: "e.g. 2026-27" },
        { name: "start_date", label: "Starts", type: "date", required: true, editable: true },
        { name: "end_date", label: "Ends", type: "date", required: true, editable: true },
      ]}
      extraActions={(y) =>
        canManage && !y.is_current && y.status === "active" ? (
          <button type="button" className="link-btn" disabled={action.isPending} onClick={() => action.mutate({ path: `academic-years/${y.id}/make-current` })}>
            Make current
          </button>
        ) : null
      }
    />
  );
}

function ProgrammesTab({ data, canManage }: { data: SetupOverview; canManage: boolean }) {
  const deptOptions = data.departments.filter((d) => d.status === "active").map((d) => ({ value: d.id, label: `${d.code} · ${d.name}` }));
  const progOptions = data.programmes.filter((p) => p.status === "active").map((p) => ({ value: p.id, label: p.code }));
  const deptName = (id: string) => data.departments.find((d) => d.id === id)?.code ?? "";
  const prog = (id: string) => data.programmes.find((p) => p.id === id);
  return (
    <>
      <RecordSection
        title="Departments"
        path="departments"
        rows={data.departments}
        canManage={canManage}
        columns={[
          { key: "code", header: "Code", render: (d) => <b>{d.code}</b>, searchText: (d) => d.code },
          { key: "name", header: "Name", render: (d) => d.name, searchText: (d) => d.name },
        ]}
        fields={[
          { name: "code", label: "Code", required: true, hint: "e.g. CS" },
          { name: "name", label: "Name", required: true, editable: true },
        ]}
      />
      <RecordSection
        title="Programmes"
        path="programmes"
        rows={data.programmes}
        canManage={canManage}
        columns={[
          { key: "code", header: "Code", render: (p) => <b>{p.code}</b>, searchText: (p) => p.code },
          { key: "name", header: "Name", render: (p) => p.name, searchText: (p) => p.name },
          { key: "dept", header: "Department", render: (p) => deptName(p.department_id) },
          { key: "years", header: "Years", render: (p) => p.year_labels.join(" / ") },
        ]}
        fields={[
          { name: "code", label: "Code", required: true, hint: "e.g. BCA" },
          { name: "name", label: "Name", required: true, editable: true },
          { name: "department_id", label: "Department", type: "select", options: deptOptions, required: true, editable: true },
          { name: "level", label: "Level", type: "select", options: ["UG", "PG", "Diploma"].map((v) => ({ value: v, label: v })), required: true },
          { name: "duration_years", label: "Years", type: "number", required: true },
          { name: "semesters_per_year", label: "Semesters per year", type: "number", required: true },
          { name: "year_labels", label: "Year labels", type: "list", editable: true, hint: "Comma-separated, e.g. FY, SY, TY" },
        ]}
        defaults={{ level: "UG", duration_years: 3, semesters_per_year: 2 }}
      />
      <RecordSection
        title="Divisions"
        path="divisions"
        rows={data.divisions}
        canManage={canManage}
        columns={[
          { key: "class", header: "Class", render: (d) => <b>{`${prog(d.programme_id)?.code ?? ""} · ${prog(d.programme_id)?.year_labels[d.year_of_study - 1] ?? d.year_of_study}`}</b>, searchText: (d) => prog(d.programme_id)?.code ?? "" },
          { key: "name", header: "Division", render: (d) => d.name },
          { key: "capacity", header: "Capacity", render: (d) => (d.capacity ?? "—").toString() },
        ]}
        fields={[
          { name: "programme_id", label: "Programme", type: "select", options: progOptions, required: true },
          { name: "year_of_study", label: "Year of study", type: "number", required: true, hint: "1 = first year" },
          { name: "name", label: "Division", required: true, hint: "e.g. A" },
          { name: "capacity", label: "Capacity", type: "number", editable: true },
        ]}
      />
    </>
  );
}

function SubjectsTab({ data, canManage }: { data: SetupOverview; canManage: boolean }) {
  const programmes = data.programmes.filter((p) => p.status === "active");
  const [programmeId, setProgrammeId] = useState(programmes[0]?.id ?? "");
  const subjects = useSubjects(programmeId || undefined);
  const programme = programmes.find((p) => p.id === programmeId);
  const semesters = programme ? programme.duration_years * programme.semesters_per_year : 0;
  return (
    <>
      <div className="field inline-field">
        <label htmlFor="subj-prog">Programme</label>
        <select id="subj-prog" value={programmeId} onChange={(e) => setProgrammeId(e.target.value)}>
          {programmes.map((p) => (
            <option key={p.id} value={p.id}>
              {p.code} · {p.name}
            </option>
          ))}
        </select>
      </div>
      {programme && (
        <RecordSection
          key={programme.id}
          title="Subjects"
          path="subjects"
          rows={subjects.data ?? []}
          canManage={canManage}
          defaults={{ programme_id: programme.id, type: "theory" }}
          columns={[
            { key: "sem", header: "Sem", render: (s) => s.semester },
            { key: "code", header: "Code", render: (s) => <b>{s.code}</b>, searchText: (s) => s.code },
            { key: "name", header: "Name", render: (s) => s.name, searchText: (s) => s.name },
            { key: "type", header: "Type", render: (s) => s.type },
            { key: "credits", header: "Credits", render: (s) => s.credits, align: "right" },
            { key: "marks", header: "Internal / External", render: (s) => `${s.max_internal} / ${s.max_external}`, align: "right" },
          ]}
          fields={[
            { name: "semester", label: `Semester (1–${semesters})`, type: "number", required: true },
            { name: "code", label: "Code", required: true },
            { name: "name", label: "Name", required: true, editable: true },
            { name: "type", label: "Type", type: "select", options: ["theory", "practical", "project"].map((v) => ({ value: v, label: v })), required: true, editable: true },
            { name: "credits", label: "Credits", type: "number", required: true, editable: true },
            { name: "max_internal", label: "Max internal marks", type: "number", required: true, editable: true },
            { name: "max_external", label: "Max external marks", type: "number", required: true, editable: true },
          ]}
        />
      )}
      {programmes.length === 0 && <p className="muted">Add a programme first.</p>}
    </>
  );
}

function HolidaysTab({ data, canManage }: { data: SetupOverview; canManage: boolean }) {
  const years = data.academic_years.filter((y) => y.status === "active");
  const [yearId, setYearId] = useState(data.current_year?.id ?? years[0]?.id ?? "");
  const holidays = useHolidays(yearId || undefined);
  return (
    <>
      <div className="field inline-field">
        <label htmlFor="hol-year">Academic year</label>
        <select id="hol-year" value={yearId} onChange={(e) => setYearId(e.target.value)}>
          {years.map((y) => (
            <option key={y.id} value={y.id}>
              {y.name}
            </option>
          ))}
        </select>
      </div>
      {yearId ? (
        <RecordSection
          key={yearId}
          title="Holidays"
          path="holidays"
          rows={holidays.data ?? []}
          canManage={canManage}
          defaults={{ academic_year_id: yearId }}
          columns={[
            { key: "date", header: "Date", render: (h) => <span className="nowrap">{fmtDate(h.date)}</span> },
            { key: "name", header: "Holiday", render: (h) => h.name, searchText: (h) => h.name },
          ]}
          fields={[
            { name: "date", label: "Date", type: "date", required: true },
            { name: "name", label: "Name", required: true, editable: true },
          ]}
        />
      ) : (
        <p className="muted">Add an academic year first.</p>
      )}
    </>
  );
}

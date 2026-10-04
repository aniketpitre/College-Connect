import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { DataTable, type Column } from "../../components/DataTable";
import { Modal } from "../../components/Modal";
import { StatusBadge } from "../../components/StatusBadge";
import { STUDENT_STRINGS } from "../../i18n/student";
import { hasPermission, useMe } from "../../lib/auth";
import { useSetup } from "../../lib/setup";
import { useChangeQueue, useCreateStudent, useStudents, type StudentFilters, type StudentSummary } from "../../lib/students";
import { ChangeRequestList } from "./ChangeRequestList";
import { StudentFields } from "./StudentForm";
import { toBody, toValues } from "./studentValues";
import "./students.css";

const L = STUDENT_STRINGS.en;
const STATUS_TONE = { active: "success", tc: "neutral", graduated: "info", dropped: "neutral", detained: "warning" } as const;

/** Office screen (English): find students, add one, and handle correction requests. */
export default function StudentsPage() {
  const { data: me } = useMe();
  const setup = useSetup();
  const [tab, setTab] = useState<"list" | "requests">("list");
  const [filters, setFilters] = useState<StudentFilters>({ status: "active" });
  const students = useStudents(filters);
  const pending = useChangeQueue("pending");
  const [adding, setAdding] = useState(false);
  const [created, setCreated] = useState<{ id: string; name: string; prn: string; password: string } | null>(null);
  const canManage = hasPermission(me, "students.manage");
  const navigate = useNavigate();
  const programme = setup.data?.programmes.find((p) => p.id === filters.programme_id);

  const columns: Column<StudentSummary>[] = [
    {
      key: "name",
      header: "Student",
      render: (s) => (
        <Link to={`/app/students/${s.id}`} className="user-cell">
          <span className="user-name">{s.name}</span>
          <span className="user-sub">PRN {s.prn}</span>
        </Link>
      ),
      searchText: (s) => `${s.name} ${s.prn}`,
    },
    {
      key: "class",
      header: "Class",
      render: (s) => <span className="nowrap">{[s.programme_code, s.year_label, s.division].filter(Boolean).join(" · ")}</span>,
    },
    { key: "roll", header: "Roll", render: (s) => s.roll_no ?? "—" },
    { key: "cat", header: "Category", render: (s) => s.category_code ?? "—" },
    { key: "phone", header: "Mobile", render: (s) => s.phone ?? "—", searchText: (s) => s.phone ?? "" },
    { key: "status", header: "Status", render: (s) => <StatusBadge tone={STATUS_TONE[s.status]}>{L.studentStatus[s.status]}</StatusBadge> },
  ];

  const filter = (k: keyof StudentFilters) => (e: React.ChangeEvent<HTMLSelectElement>) => {
    const next = { ...filters, [k]: e.target.value || undefined };
    if (k === "programme_id") next.year_of_study = next.division_id = undefined;
    if (k === "year_of_study") next.division_id = undefined;
    setFilters(next);
  };

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Office</div>
          <h1>Students</h1>
        </div>
        <div className="row-actions">
          {canManage && (
            <Link className="btn btn-ghost" to="/app/students/promote">
              Promote a class
            </Link>
          )}
          {hasPermission(me, "students.import") && (
            <Link className="btn btn-ghost" to="/app/students/import">
              Import from Excel
            </Link>
          )}
          {canManage && (
            <button type="button" className="btn btn-primary" onClick={() => setAdding(true)} disabled={!setup.data}>
              Add student
            </button>
          )}
        </div>
      </div>

      <div className="tabs" role="tablist">
        <button type="button" role="tab" aria-selected={tab === "list"} className={tab === "list" ? "active" : ""} onClick={() => setTab("list")}>
          All students
        </button>
        <button type="button" role="tab" aria-selected={tab === "requests"} className={tab === "requests" ? "active" : ""} onClick={() => setTab("requests")}>
          Correction requests {pending.data?.length ? <span className="count-pill">{pending.data.length}</span> : null}
        </button>
      </div>

      {tab === "requests" ? (
        <ChangeRequestList status="pending" canDecide={canManage} />
      ) : (
        <>
          <div className="filters">
            <select aria-label="Programme" value={filters.programme_id ?? ""} onChange={filter("programme_id")}>
              <option value="">All programmes</option>
              {setup.data?.programmes.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.code}
                </option>
              ))}
            </select>
            <select aria-label="Year" value={filters.year_of_study ?? ""} onChange={filter("year_of_study")} disabled={!programme}>
              <option value="">All years</option>
              {programme?.year_labels.map((label, i) => (
                <option key={label} value={i + 1}>
                  {label}
                </option>
              ))}
            </select>
            <select aria-label="Division" value={filters.division_id ?? ""} onChange={filter("division_id")} disabled={!filters.year_of_study}>
              <option value="">All divisions</option>
              {setup.data?.divisions
                .filter((d) => d.programme_id === filters.programme_id && String(d.year_of_study) === filters.year_of_study)
                .map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
            </select>
            <select aria-label="Status" value={filters.status ?? ""} onChange={filter("status")}>
              <option value="">Any status</option>
              {Object.entries(L.studentStatus).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            <span className="muted">{students.data ? `${students.data.total} students` : ""}</span>
          </div>
          {students.error && <p className="form-error">{students.error.message}</p>}
          <DataTable
            columns={columns}
            rows={students.data?.items ?? []}
            rowKey={(s) => s.id}
            searchPlaceholder="Search by name, PRN or mobile"
            emptyTitle={students.isLoading ? "Loading…" : "No students match"}
          />
        </>
      )}

      {adding && setup.data && (
        <AddStudentModal
          onClose={() => setAdding(false)}
          onCreated={(c) => {
            setAdding(false);
            setCreated(c);
          }}
        />
      )}

      <Modal open={created !== null} title="Student added" onClose={() => setCreated(null)}>
        {created && (
          <>
            <p className="muted">
              Give <b>{created.name}</b> (PRN {created.prn}) this temporary password. It is shown only once; they choose their own at first sign-in.
            </p>
            <div className="temp-password">{created.password}</div>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => navigate(`/app/students/${created.id}`)}>
                Open record
              </button>
              <button type="button" className="btn btn-primary" onClick={() => setCreated(null)}>
                Done
              </button>
            </div>
          </>
        )}
      </Modal>
    </>
  );
}

function AddStudentModal({ onClose, onCreated }: { onClose: () => void; onCreated: (c: { id: string; name: string; prn: string; password: string }) => void }) {
  const setup = useSetup();
  const [values, setValues] = useState(() => toValues());
  const create = useCreateStudent();
  return (
    <Modal open title="Add student" onClose={onClose} wide>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate(toBody(values), {
            onSuccess: (r) => onCreated({ id: r.student.id, name: r.student.name, prn: r.student.prn, password: r.temporary_password }),
          });
        }}
      >
        <StudentFields setup={setup.data!} values={values} onChange={setValues} error={create.error} isNew />
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={create.isPending}>
            {create.isPending ? "Adding…" : "Add student and create login"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

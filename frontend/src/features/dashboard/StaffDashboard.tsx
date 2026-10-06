import type { ReactNode } from "react";
import { Link } from "react-router";
import { useDashboard, type Dashboard } from "../../lib/dashboard";
import "./dashboard.css";

const day = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short" });

function Count({ to, label, n, warn }: { to: string; label: string; n: number; warn?: boolean }) {
  return (
    <Link to={to} className={`tile dash-count${warn && n > 0 ? " tile-warn" : ""}`}>
      <div className="tile-label">{label}</div>
      <div className="tile-value">{n}</div>
    </Link>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="dash-section">
      <h2 className="subhead">{title}</h2>
      {children}
    </section>
  );
}

function Teaching({ d }: { d: NonNullable<Dashboard["teaching"]> }) {
  return (
    <Section title="Today's lectures">
      {d.holiday ? (
        <p className="muted">Holiday: {d.holiday}</p>
      ) : d.lectures.length === 0 ? (
        <p className="muted">No lectures today.</p>
      ) : (
        <ul className="dash-list">
          {d.lectures.map((l) => (
            <li key={l.slot_id}>
              <span>
                <strong>
                  {l.start}–{l.end}
                </strong>{" "}
                {l.code} · {l.class}
                {l.status === "cancelled" && <span className="muted"> (cancelled)</span>}
              </span>
              {l.taken ? (
                <span className="muted">Taken ✓</span>
              ) : l.takeable ? (
                <Link className="btn btn-primary btn-sm" to={`/app/attendance/take/${l.slot_id}/${l.date}`}>
                  Take attendance
                </Link>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {d.marks_tasks.length > 0 && (
        <>
          <h3 className="dash-h3">Marks to enter</h3>
          <ul className="dash-list">
            {d.marks_tasks.map((m) => (
              <li key={`${m.division_id}-${m.subject_id}`}>
                <span>
                  {m.label} · {m.complete}/{m.students} done
                  {m.deadline && <span className="muted"> · by {day(m.deadline)}</span>}
                </span>
                <Link to={`/app/exams/marks/${m.division_id}/${m.subject_id}`}>Open →</Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </Section>
  );
}

function Hod({ d }: { d: NonNullable<Dashboard["hod"]> }) {
  return (
    <Section title="My department">
      <div className="tiles dash-tiles">
        <Count to="/app/attendance" label="Attendance edits to approve" n={d.attendance_requests} warn />
        <Count to="/app/exams" label="Marks to approve" n={d.marks_to_approve} warn />
      </div>
      {d.classes.length > 0 && (
        <div className="data-table data-table-scroll">
          <table>
            <thead>
              <tr>
                <th>Class</th>
                <th className="num">Students</th>
                <th className="num">Attendance</th>
                <th className="num">Below minimum</th>
              </tr>
            </thead>
            <tbody>
              {d.classes.map((c) => (
                <tr key={c.division_id}>
                  <td>{c.class}</td>
                  <td className="num">{c.students}</td>
                  <td className="num">{c.attendance == null ? "–" : `${c.attendance}%`}</td>
                  <td className="num">{c.defaulters}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {d.workload.length > 0 && (
        <>
          <h3 className="dash-h3">Teaching hours per week</h3>
          <ul className="dash-list">
            {d.workload.map((w) => (
              <li key={w.name}>
                <span>{w.name}</span>
                <span>{w.hours} h</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </Section>
  );
}

function ExamCell({ d }: { d: NonNullable<Dashboard["exam_cell"]> }) {
  return (
    <Section title="Exams">
      <div className="tiles dash-tiles">
        <Count to="/app/exams" label="Marks sheets awaiting HOD" n={d.marks.published ?? 0} />
        <Count to="/app/exams" label="Approved, not locked" n={d.marks.approved ?? 0} warn />
        <Count to="/app/exams" label="Revaluation requests" n={d.revaluations} warn />
        <Count to="/app/exams" label="Subjects without a scheme" n={d.subjects_without_scheme} warn />
      </div>
      {d.sessions.length > 0 && (
        <ul className="dash-list">
          {d.sessions.map((s) => (
            <li key={s.id}>
              <span>
                {s.name} <span className="muted">· forms by {day(s.form_deadline)}</span>
              </span>
              <Link to={`/app/exams/sessions/${s.id}`}>
                {s.to_verify} to verify · {s.verified} verified{s.results_published ? " · results out" : ""} →
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

function Office({ d }: { d: NonNullable<Dashboard["office"]> }) {
  return (
    <Section title="Office">
      <div className="tiles dash-tiles">
        <Count to="/app/certificates" label="Certificate requests open" n={d.certificates_open} />
        <Count to="/app/certificates" label="Certificates late" n={d.certificates_overdue} warn />
        <Count to="/app/certificates" label="Signed, ready to issue" n={d.certificates_to_issue} warn />
        <Count to="/app/students" label="Corrections to review" n={d.corrections} warn />
        <Count to="/app/students" label="Students with documents to check" n={d.documents} warn />
      </div>
    </Section>
  );
}

function Principal({ d }: { d: NonNullable<Dashboard["principal"]> }) {
  return (
    <Section title="Waiting for you">
      <div className="tiles dash-tiles">
        <Count to="/app/approvals" label="Approvals" n={d.approvals} warn />
        <Count to="/app/exports" label="Export requests" n={d.exports} warn />
        <Count to="/app/certificates" label="Certificates to sign" n={d.certificates_to_sign} warn />
        <Count to="/app/certificates" label="Certificates late (all)" n={d.certificates_overdue} warn />
      </div>
    </Section>
  );
}

function People({ leave, grievances }: { leave?: Dashboard["leave"]; grievances?: Dashboard["grievances"] }) {
  return (
    <Section title="People">
      <div className="tiles dash-tiles">
        {leave && <Count to="/app/leave" label="Leave to approve" n={leave.to_approve} warn />}
        {grievances && <Count to="/app/grievances" label="Open grievances" n={grievances.open} />}
        {grievances && <Count to="/app/grievances" label="Grievances past the time limit" n={grievances.overdue} warn />}
      </div>
      {leave && leave.on_leave_today.length > 0 && <p className="muted small">On leave today: {leave.on_leave_today.join(", ")}</p>}
    </Section>
  );
}

/** Staff home widgets (plan 2.11): only the sections the person's roles allow come back from the API. */
export default function StaffDashboard() {
  const { data } = useDashboard(true);
  if (!data) return null;
  return (
    <div className="dashboard">
      {data.principal && <Principal d={data.principal} />}
      {data.teaching && <Teaching d={data.teaching} />}
      {data.hod && <Hod d={data.hod} />}
      {data.exam_cell && <ExamCell d={data.exam_cell} />}
      {data.office && <Office d={data.office} />}
      {(data.leave || data.grievances) && <People leave={data.leave} grievances={data.grievances} />}
    </div>
  );
}

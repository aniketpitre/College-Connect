import type { ReactNode } from "react";
import { Link } from "react-router";
import { MoneyText } from "../../components/MoneyText";
import { hasPermission, useMe } from "../../lib/auth";
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

function Tile({ label, children, warn }: { label: string; children: ReactNode; warn?: boolean }) {
  return (
    <div className={`tile dash-count${warn ? " tile-warn" : ""}`}>
      <div className="tile-label">{label}</div>
      <div className="tile-value">{children}</div>
    </div>
  );
}

const pct = (n: number | null | undefined) => (n === null || n === undefined ? "—" : `${n}%`);
const MODES: Record<string, string> = { cash: "Cash", upi: "UPI", card: "Card", cheque: "Cheque", dd: "DD", neft: "NEFT", online: "Online" };

function Overview({ d }: { d: NonNullable<Dashboard["overview"]> }) {
  return (
    <Section title={`College at a glance${d.year ? ` · ${d.year}` : ""}`}>
      <div className="tiles dash-tiles">
        {d.admissions && (
          <Tile label="Admitted / seats">
            {d.admissions.admitted}/{d.admissions.seats}
            <div className="small muted">{d.admissions.applied} applied</div>
          </Tile>
        )}
        {d.fees && (
          <Tile label="Fees collected">
            {pct(d.fees.percent)}
            <div className="small muted">
              <MoneyText paise={d.fees.collected} /> · <MoneyText paise={d.fees.outstanding} /> due
            </div>
          </Tile>
        )}
        <Tile label="Attendance (average)" warn={d.attendance.below_minimum > 0}>
          {pct(d.attendance.average)}
          <div className="small muted">
            {d.attendance.below_minimum} below {d.attendance.minimum}%
          </div>
        </Tile>
        {d.marks && (
          <Tile label="Internal marks approved">
            {pct(d.marks.percent)}
            <div className="small muted">
              {d.marks.done} of {d.marks.sheets} sheets
            </div>
          </Tile>
        )}
        <Tile label="Certificate turnaround" warn={d.certificates.overdue > 0}>
          {d.certificates.average_days === null ? "—" : `${d.certificates.average_days} days`}
          <div className="small muted">{d.certificates.overdue} late</div>
        </Tile>
      </div>
      <div className="tiles dash-tiles">
        <Count to="/app/mentoring" label="Students at high risk" n={d.risk.high} warn />
        <Count to="/app/mentoring" label="Students to watch" n={d.risk.medium} />
        <Count to="/app/leave" label="Leave to approve" n={d.pending.leave} warn />
        <Count to="/app/grievances" label="Grievances past the time limit" n={d.pending.grievances_overdue} warn />
      </div>
    </Section>
  );
}

function Accounts({ d }: { d: NonNullable<Dashboard["accounts"]> }) {
  return (
    <Section title="Collections and receivables">
      <div className="tiles dash-tiles">
        <Tile label="Collected today">
          <MoneyText paise={d.today.total} />
        </Tile>
        <Tile label="This month">
          <MoneyText paise={d.month.total} />
          <div className="small muted">
            {Object.entries(d.month.by_mode)
              .map(([m, a]) => `${MODES[m] ?? m} ${Math.round(a / 100).toLocaleString("en-IN")}`)
              .join(" · ")}
          </div>
        </Tile>
        {d.year && (
          <Tile label="This year">
            <MoneyText paise={d.year.total} />
          </Tile>
        )}
        {d.receivables && (
          <>
            <Tile label="Receivable">
              <MoneyText paise={d.receivables.total} />
            </Tile>
            <Tile label="Overdue" warn={d.receivables.overdue > 0}>
              <MoneyText paise={d.receivables.overdue} />
              <div className="small muted">{d.receivables.overdue_students} students</div>
            </Tile>
          </>
        )}
      </div>
      {d.receivables && d.receivables.by_year.length > 0 && (
        <p className="muted small">
          Receivable by year:{" "}
          {d.receivables.by_year.map((y) => (
            <span key={y.year_of_study}>
              Year {y.year_of_study} <MoneyText paise={y.amount} />{" "}
            </span>
          ))}
        </p>
      )}
    </Section>
  );
}

function Risk({ d }: { d: NonNullable<Dashboard["risk"]> }) {
  return (
    <Section title="Students who may need help">
      <div className="tiles dash-tiles">
        <Count to="/app/mentoring" label="High risk" n={d.high} warn />
        <Count to="/app/mentoring" label="To watch" n={d.medium} />
      </div>
    </Section>
  );
}

/** The knowledge-gap loop (plan 5.7): what the help desk couldn't answer this week. */
function HelpDesk({ d }: { d: NonNullable<Dashboard["help_desk"]> }) {
  const { data: me } = useMe();
  // Office and System Admin answer them; others (the Principal) see the analytics.
  const to = hasPermission(me, "kb.manage") ? "/app/knowledge#gaps" : "/app/analytics";
  return (
    <Section title="Help desk">
      <div className="tiles dash-tiles">
        <Count to={to} label="Questions it couldn't answer (7 days)" n={d.unanswered} warn />
        <Count to={to} label="Times asked" n={d.asked} />
      </div>
      {d.top.length > 0 && (
        <ul className="small">
          {d.top.map((g) => (
            <li key={g.key}>
              {g.question} <span className="muted">({g.count})</span>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

/** Staff home widgets (plan 2.11): only the sections the person's roles allow come back from the API. */
export default function StaffDashboard() {
  const { data } = useDashboard(true);
  if (!data) return null;
  return (
    <div className="dashboard">
      {data.overview && <Overview d={data.overview} />}
      {data.principal && <Principal d={data.principal} />}
      {data.accounts && <Accounts d={data.accounts} />}
      {data.risk && !data.overview && <Risk d={data.risk} />}
      {data.teaching && <Teaching d={data.teaching} />}
      {data.hod && <Hod d={data.hod} />}
      {data.exam_cell && <ExamCell d={data.exam_cell} />}
      {data.office && <Office d={data.office} />}
      {(data.leave || data.grievances) && <People leave={data.leave} grievances={data.grievances} />}
      {data.help_desk && <HelpDesk d={data.help_desk} />}
    </div>
  );
}

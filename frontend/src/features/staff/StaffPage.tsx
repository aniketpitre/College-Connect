import { useState } from "react";
import { EmptyState } from "../../components/EmptyState";
import { Modal } from "../../components/Modal";
import { StatusBadge } from "../../components/StatusBadge";
import { hasPermission, useMe } from "../../lib/auth";
import {
  useAdjustLeave,
  useLeaveTypes,
  useSaveLeaveTypes,
  useSaveStaff,
  useStaffBalances,
  useStaffList,
  useStaffSummary,
  useWorkload,
  type LeaveType,
  type Qualification,
  type StaffMember,
} from "../../lib/staff";
import "../campus/campus.css";
import "./staff.css";

const EMPLOYMENT: Record<string, string> = {
  permanent: "Permanent",
  contract: "Contract",
  visiting: "Visiting",
  ad_hoc: "Ad hoc",
};
const LEVELS: Record<Qualification["level"], string> = {
  ug: "UG",
  pg: "PG",
  mphil: "M.Phil.",
  phd: "Ph.D.",
  net: "NET",
  set: "SET",
  other: "Other",
};

/** Staff records, workload and leave settings (English; Office, Principal, HOD for their department). */
export default function StaffPage() {
  const { data: me } = useMe();
  const canManage = hasPermission(me, "staff.manage");
  const [tab, setTab] = useState<"staff" | "workload" | "summary" | "leave">("staff");
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Staff</div>
          <h1>Staff and workload</h1>
        </div>
      </div>
      <div className="tabs" role="tablist">
        {(
          [
            ["staff", "Staff records"],
            ["workload", "Workload"],
            ["summary", "NAAC summary"],
            ...(canManage ? ([["leave", "Leave types"]] as const) : []),
          ] as const
        ).map(([k, label]) => (
          <button key={k} type="button" role="tab" aria-selected={tab === k} className={tab === k ? "active" : ""} onClick={() => setTab(k)}>
            {label}
          </button>
        ))}
      </div>
      {tab === "staff" && <Records canManage={canManage} />}
      {tab === "workload" && <WorkloadView />}
      {tab === "summary" && <Summary />}
      {tab === "leave" && canManage && <LeaveTypes />}
    </>
  );
}

function Records({ canManage }: { canManage: boolean }) {
  const list = useStaffList();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<StaffMember | null>(null);
  const rows = (list.data ?? []).filter((s) => !q || `${s.name} ${s.department ?? ""} ${s.employee_code ?? ""}`.toLowerCase().includes(q.toLowerCase()));
  return (
    <>
      <input
        className="campus-search"
        placeholder="Search by name, department or code"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        aria-label="Search staff"
      />
      {list.data?.length === 0 && <EmptyState title="No staff accounts yet" />}
      <div className="data-table data-table-scroll">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Department</th>
              <th>Designation</th>
              <th>Employment</th>
              <th>Qualifications</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr key={s.user_id}>
                <td>
                  <b>{s.name}</b>
                  {s.employee_code && <div className="small muted">{s.employee_code}</div>}
                </td>
                <td>{s.department ?? "—"}</td>
                <td>{s.designation ?? <span className="muted">no record</span>}</td>
                <td>{s.employment ? EMPLOYMENT[s.employment] : "—"}</td>
                <td>
                  <span className="staff-tags">
                    {s.phd && <StatusBadge tone="info">Ph.D.</StatusBadge>}
                    {s.net_set && <StatusBadge tone="info">NET/SET</StatusBadge>}
                    {!s.teaching && <StatusBadge>Non-teaching</StatusBadge>}
                  </span>
                </td>
                <td>
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => setOpen(s)}>
                    {canManage ? "Edit" : "View"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {open && <StaffForm key={open.user_id} staff={open} canManage={canManage} onClose={() => setOpen(null)} />}
    </>
  );
}

function StaffForm({ staff, canManage, onClose }: { staff: StaffMember; canManage: boolean; onClose: () => void }) {
  const save = useSaveStaff();
  const balances = useStaffBalances(staff.user_id);
  const adjust = useAdjustLeave();
  const [f, setF] = useState({
    employee_code: staff.employee_code ?? "",
    designation: staff.designation ?? "",
    employment: staff.employment ?? "permanent",
    teaching: staff.teaching,
    gender: staff.gender ?? "",
    social_category: staff.social_category ?? "",
    joined_on: staff.joined_on ?? "",
    experience_years: staff.experience_years,
    phone: staff.phone ?? "",
    appointment_order: staff.appointment_order ?? "",
    appointment_date: staff.appointment_date ?? "",
    university_approved: staff.university_approved,
    left_on: staff.left_on ?? "",
  });
  const [quals, setQuals] = useState<Qualification[]>(staff.qualifications);
  const [adj, setAdj] = useState({ code: "EL", days: 0, reason: "" });
  const opt = (v: string) => v.trim() || null;
  return (
    <Modal open title={staff.name} onClose={onClose} wide>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate(
            {
              id: staff.user_id,
              body: {
                ...f,
                employee_code: opt(f.employee_code),
                joined_on: opt(f.joined_on),
                gender: opt(f.gender),
                social_category: opt(f.social_category),
                phone: opt(f.phone),
                appointment_order: opt(f.appointment_order),
                appointment_date: opt(f.appointment_date),
                left_on: opt(f.left_on),
                qualifications: quals.filter((q) => q.degree.trim()),
              },
            },
            { onSuccess: onClose },
          );
        }}
      >
        <fieldset disabled={!canManage} className="campus-form">
          <div className="field">
            <label htmlFor="st-code">Employee code</label>
            <input id="st-code" value={f.employee_code} onChange={(e) => setF({ ...f, employee_code: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="st-desig">Designation</label>
            <input id="st-desig" value={f.designation} onChange={(e) => setF({ ...f, designation: e.target.value })} required minLength={2} />
          </div>
          <div className="field">
            <label htmlFor="st-emp">Employment</label>
            <select id="st-emp" value={f.employment} onChange={(e) => setF({ ...f, employment: e.target.value })}>
              {Object.entries(EMPLOYMENT).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="st-gender">Gender</label>
            <select id="st-gender" value={f.gender} onChange={(e) => setF({ ...f, gender: e.target.value })}>
              <option value="">—</option>
              <option value="female">Female</option>
              <option value="male">Male</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="st-cat">Social category (AISHE)</label>
            <select id="st-cat" value={f.social_category} onChange={(e) => setF({ ...f, social_category: e.target.value })}>
              <option value="">—</option>
              <option value="general">General</option>
              <option value="ews">EWS</option>
              <option value="sc">SC</option>
              <option value="st">ST</option>
              <option value="obc">OBC</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="st-joined">Joined on</label>
            <input id="st-joined" type="date" value={f.joined_on} onChange={(e) => setF({ ...f, joined_on: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="st-exp">Experience before joining (years)</label>
            <input
              id="st-exp"
              type="number"
              min={0}
              max={60}
              step={0.5}
              value={f.experience_years}
              onChange={(e) => setF({ ...f, experience_years: Number(e.target.value) })}
            />
          </div>
          <div className="field">
            <label htmlFor="st-phone">Phone</label>
            <input id="st-phone" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="st-order">Appointment order no.</label>
            <input id="st-order" value={f.appointment_order} onChange={(e) => setF({ ...f, appointment_order: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="st-odate">Appointment date</label>
            <input id="st-odate" type="date" value={f.appointment_date} onChange={(e) => setF({ ...f, appointment_date: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="st-left">Left on</label>
            <input id="st-left" type="date" value={f.left_on} onChange={(e) => setF({ ...f, left_on: e.target.value })} />
          </div>
          <label className="check-label">
            <input type="checkbox" checked={f.teaching} onChange={(e) => setF({ ...f, teaching: e.target.checked })} /> Teaching staff
          </label>
          <label className="check-label">
            <input type="checkbox" checked={f.university_approved} onChange={(e) => setF({ ...f, university_approved: e.target.checked })} /> Approved by the
            university
          </label>
          <div className="staff-wide">
            <h3 className="subhead">Qualifications</h3>
            {quals.map((q, i) => (
              <div key={i} className="qual-row">
                <select
                  aria-label="Level"
                  value={q.level}
                  onChange={(e) =>
                    setQuals(
                      quals.map((x, j) =>
                        j === i
                          ? {
                              ...x,
                              level: e.target.value as Qualification["level"],
                            }
                          : x,
                      ),
                    )
                  }
                >
                  {Object.entries(LEVELS).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
                <input
                  aria-label="Degree"
                  placeholder="Degree / exam"
                  value={q.degree}
                  onChange={(e) => setQuals(quals.map((x, j) => (j === i ? { ...x, degree: e.target.value } : x)))}
                />
                <input
                  aria-label="University"
                  placeholder="University"
                  value={q.university ?? ""}
                  onChange={(e) => setQuals(quals.map((x, j) => (j === i ? { ...x, university: e.target.value || null } : x)))}
                />
                <input
                  aria-label="Year"
                  type="number"
                  placeholder="Year"
                  value={q.year ?? ""}
                  onChange={(e) =>
                    setQuals(
                      quals.map((x, j) =>
                        j === i
                          ? {
                              ...x,
                              year: e.target.value ? Number(e.target.value) : null,
                            }
                          : x,
                      ),
                    )
                  }
                />
                <button type="button" className="link-button" onClick={() => setQuals(quals.filter((_, j) => j !== i))}>
                  remove
                </button>
              </div>
            ))}
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => setQuals([...quals, { level: "pg", degree: "", university: null, year: null }])}
            >
              Add qualification
            </button>
          </div>
        </fieldset>
        {save.error && <p className="form-error">{save.error.message}</p>}
        {canManage && (
          <div className="row-actions" style={{ marginTop: 12 }}>
            <button type="button" className="btn btn-ghost" onClick={onClose}>
              Close
            </button>
            <button type="submit" className="btn btn-primary" disabled={save.isPending}>
              Save
            </button>
          </div>
        )}
      </form>
      <h3 className="subhead">Leave this year</h3>
      <ul className="campus-list">
        {balances.data?.map((b) => (
          <li key={b.code}>
            <span>{b.name}</span>
            <span className="small">
              {b.taken} taken{b.pending > 0 && `, ${b.pending} waiting`}
              {b.available !== null && ` · ${b.available} of ${b.allowance} left`}
            </span>
          </li>
        ))}
      </ul>
      {canManage && (
        <form
          className="row-actions"
          style={{ justifyContent: "flex-start" }}
          onSubmit={(e) => {
            e.preventDefault();
            adjust.mutate({ user_id: staff.user_id, ...adj }, { onSuccess: () => setAdj({ ...adj, days: 0, reason: "" }) });
          }}
        >
          <select aria-label="Leave type to adjust" value={adj.code} onChange={(e) => setAdj({ ...adj, code: e.target.value })}>
            {balances.data
              ?.filter((b) => b.allowance !== null)
              .map((b) => (
                <option key={b.code} value={b.code}>
                  {b.code}
                </option>
              ))}
          </select>
          <input
            aria-label="Days to add (minus to remove)"
            type="number"
            step={0.5}
            value={adj.days}
            onChange={(e) => setAdj({ ...adj, days: Number(e.target.value) })}
            style={{ width: 80 }}
          />
          <input
            aria-label="Reason for the adjustment"
            placeholder="Reason, e.g. carried forward"
            value={adj.reason}
            onChange={(e) => setAdj({ ...adj, reason: e.target.value })}
          />
          <button type="submit" className="btn btn-ghost btn-sm" disabled={adjust.isPending || !adj.days || adj.reason.trim().length < 3}>
            Adjust balance
          </button>
          {adjust.error && <span className="form-error">{adjust.error.message}</span>}
        </form>
      )}
    </Modal>
  );
}

function WorkloadView() {
  const load = useWorkload(true);
  const w = load.data;
  if (load.error) return <p className="form-error">{load.error.message}</p>;
  if (!w) return null;
  return (
    <>
      <p className="small">
        <b>On leave today:</b> {w.on_leave_today.length ? w.on_leave_today.join(", ") : "nobody"}
      </p>
      <div className="data-table data-table-scroll">
        <table>
          <thead>
            <tr>
              <th>Teacher</th>
              <th>Department</th>
              <th className="num">Lectures a week</th>
              <th className="num">Hours a week</th>
              <th className="num">Subjects</th>
              <th className="num">Classes</th>
              <th className="num">Leave taken</th>
            </tr>
          </thead>
          <tbody>
            {w.staff.map((s) => (
              <tr key={s.user_id}>
                <td>
                  {s.name} {s.on_leave_today && <StatusBadge tone="warning">On leave</StatusBadge>}
                  {s.designation && <div className="small muted">{s.designation}</div>}
                </td>
                <td>{s.department ?? "—"}</td>
                <td className="num">{s.lectures}</td>
                <td className="num">{s.hours}</td>
                <td className="num">{s.subjects}</td>
                <td className="num">{s.divisions}</td>
                <td className="num">{s.leave_taken}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function Summary() {
  const summary = useStaffSummary();
  const s = summary.data;
  if (!s) return null;
  return (
    <>
      <div className="tiles fee-tiles">
        <div className="tile">
          <div className="tile-label">Teaching staff</div>
          <div className="tile-value">{s.teaching}</div>
        </div>
        <div className="tile">
          <div className="tile-label">Non-teaching staff</div>
          <div className="tile-value">{s.non_teaching}</div>
        </div>
        <div className="tile">
          <div className="tile-label">Teachers with Ph.D.</div>
          <div className="tile-value">{s.phd}</div>
        </div>
        <div className="tile">
          <div className="tile-label">Teachers with NET/SET</div>
          <div className="tile-value">{s.net_set}</div>
        </div>
        <div className={`tile${s.missing_records ? " tile-warn" : ""}`}>
          <div className="tile-label">Without a staff record</div>
          <div className="tile-value">{s.missing_records}</div>
        </div>
      </div>
      <p className="small muted">
        Teachers by employment:{" "}
        {Object.entries(s.by_employment)
          .map(([k, n]) => `${EMPLOYMENT[k]} ${n}`)
          .join(" · ")}
      </p>
      <ul className="campus-list">
        {s.by_department.map((d) => (
          <li key={d.department}>
            <b>{d.department}</b>
            <span className="small">
              {d.teachers} teacher{d.teachers === 1 ? "" : "s"} · {d.phd} with Ph.D.
            </span>
          </li>
        ))}
      </ul>
    </>
  );
}

function LeaveTypes() {
  const types = useLeaveTypes();
  const save = useSaveLeaveTypes();
  const [draft, setDraft] = useState<LeaveType[] | null>(null);
  if (!types.data) return null;
  const rows = draft ?? types.data;
  const set = (i: number, patch: Partial<LeaveType>) => setDraft(rows.map((t, j) => (j === i ? { ...t, ...patch } : t)));
  return (
    <form
      className="card"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate(rows, { onSuccess: () => setDraft(null) });
      }}
    >
      <h2 className="card-title">Leave types and yearly allowance</h2>
      <p className="small muted">Leave without a number of days has no limit (on duty, without pay).</p>
      {rows.map((t, i) => (
        <div key={i} className="row-actions" style={{ justifyContent: "flex-start", marginBottom: 6 }}>
          <input aria-label="Code" value={t.code} onChange={(e) => set(i, { code: e.target.value.toUpperCase() })} style={{ width: 70 }} />
          <input aria-label="Name" value={t.name} onChange={(e) => set(i, { name: e.target.value })} />
          <input
            aria-label={`Days a year for ${t.code}`}
            type="number"
            min={0}
            step={0.5}
            placeholder="no limit"
            value={t.days ?? ""}
            onChange={(e) =>
              set(i, {
                days: e.target.value === "" ? null : Number(e.target.value),
              })
            }
            style={{ width: 100 }}
          />
          <label className="check-label">
            <input type="checkbox" checked={t.half_day} onChange={(e) => set(i, { half_day: e.target.checked })} /> half days
          </label>
          <button type="button" className="link-button" onClick={() => setDraft(rows.filter((_, j) => j !== i))}>
            remove
          </button>
        </div>
      ))}
      <div className="row-actions" style={{ justifyContent: "flex-start" }}>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setDraft([...rows, { code: "", name: "", days: null, half_day: true }])}>
          Add a type
        </button>
        <button type="submit" className="btn btn-primary" disabled={save.isPending}>
          Save
        </button>
      </div>
      {save.error && <p className="form-error">{save.error.message}</p>}
    </form>
  );
}

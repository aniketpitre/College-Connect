import { useState } from "react";
import { Link } from "react-router";
import { EmptyState } from "../../components/EmptyState";
import { Modal } from "../../components/Modal";
import { StatusBadge } from "../../components/StatusBadge";
import { API_V1, ApiError } from "../../lib/api";
import { STATUS_TONE, checkUploadFile, useGuard, useGuardDetail, type GuardRow } from "../../lib/marks";

/** University Upload Guard: what still blocks each subject's internal-marks upload. */
export default function UploadGuard({ canExport }: { canExport: boolean }) {
  const guard = useGuard(true);
  const [open, setOpen] = useState<GuardRow | null>(null);
  const [onlyProblems, setOnlyProblems] = useState(false);
  const rows = (guard.data?.rows ?? []).filter((r) => !onlyProblems || !r.ready || Object.values(r.counts).some(Boolean));
  return (
    <>
      <p className="muted">
        Before the university's deadline, fix every subject until it is ready: no missing marks, nothing above the maximum. Students marked on a test day they were absent, and
        students not eligible for the exam, are listed so you can check them.
      </p>
      {guard.data && guard.data.departments.length > 0 && (
        <div className="tiles fee-tiles">
          {guard.data.departments.map((d) => (
            <div className="tile" key={d.name}>
              <div className="tile-label">{d.name}</div>
              <div className="tile-value" style={{ fontSize: "1.4rem" }}>
                {d.ready}/{d.subjects} ready
              </div>
              <div className="tile-note">{d.locked} locked</div>
            </div>
          ))}
        </div>
      )}
      <label className="check-label">
        <input type="checkbox" checked={onlyProblems} onChange={(e) => setOnlyProblems(e.target.checked)} /> Only subjects with problems
      </label>
      {guard.error && <p className="form-error">{guard.error.message}</p>}
      {guard.data && rows.length === 0 && <EmptyState title="Nothing to show" />}
      {rows.length > 0 && (
        <div className="data-table-scroll">
          <table className="audit-table guard-table">
            <thead>
              <tr>
                <th>Class · subject</th>
                <th>Status</th>
                <th>Missing</th>
                <th>Above max</th>
                <th>Absent but marked</th>
                <th>Not eligible</th>
                <th>Deadline</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={`${r.division_id}:${r.subject_id}`}>
                  <td>
                    <b>
                      {r.class} · {r.code}
                    </b>
                    <div className="muted small">{r.name}</div>
                  </td>
                  <td>
                    {r.has_scheme ? <StatusBadge tone={STATUS_TONE[r.status]}>{r.status_label}</StatusBadge> : <span className="muted">No scheme</span>}
                  </td>
                  <td className={r.counts.missing ? "att-critical" : ""}>{r.counts.missing}</td>
                  <td className={r.counts.above_max ? "att-critical" : ""}>{r.counts.above_max}</td>
                  <td className={r.counts.absent_marked ? "att-warning" : ""}>{r.counts.absent_marked}</td>
                  <td className={r.counts.ineligible ? "att-warning" : ""}>{r.counts.ineligible}</td>
                  <td>
                    {r.deadline ?? "–"}
                    {r.days_left !== null && <div className={`small ${r.days_left <= 2 ? "att-critical" : "muted"}`}>{r.days_left < 0 ? "passed" : `${r.days_left} days left`}</div>}
                  </td>
                  <td>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => setOpen(r)}>
                      {r.ready ? "Ready ✓" : "Check"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {open && <GuardModal row={open} canExport={canExport} onClose={() => setOpen(null)} />}
    </>
  );
}

function GuardModal({ row, canExport, onClose }: { row: GuardRow; canExport: boolean; onClose: () => void }) {
  const detail = useGuardDetail(row.division_id, row.subject_id);
  const [result, setResult] = useState<{ ok: boolean; problems: string[] } | null>(null);
  const [checkError, setCheckError] = useState("");
  const d = detail.data;
  return (
    <Modal open title={`${row.class} · ${row.code}`} onClose={onClose} wide>
      {detail.error && <p className="form-error">{detail.error.message}</p>}
      {d && (
        <>
          {d.issues.length === 0 ? (
            <p className="auth-success">No problems found.</p>
          ) : (
            <ul className="guard-issues">
              {d.issues.map((i, n) => (
                <li key={n} className={`guard-${i.kind}`}>
                  <b>{i.label}</b>: {i.name} ({i.prn}). {i.detail}
                </li>
              ))}
            </ul>
          )}
          <div className="row-actions">
            <Link className="btn btn-ghost btn-sm" to={`/app/exams/marks/${row.division_id}/${row.subject_id}`}>
              Open the marks
            </Link>
            {canExport && d.ready && (
              <a className="btn btn-primary btn-sm" href={`${API_V1}/marks/guard/export?division_id=${row.division_id}&subject_id=${row.subject_id}`} download>
                Download university file
              </a>
            )}
          </div>
          {canExport && (
            <div className="field" style={{ marginTop: 14 }}>
              <label htmlFor="guard-file">Check a file before uploading it to the university portal</label>
              <input
                id="guard-file"
                type="file"
                accept=".csv,text/csv"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  setCheckError("");
                  try {
                    setResult(await checkUploadFile(row.division_id, row.subject_id, file));
                  } catch (err) {
                    setCheckError(err instanceof ApiError ? err.message : "Could not check the file.");
                  }
                }}
              />
              {checkError && <span className="field-error">{checkError}</span>}
              {result &&
                (result.ok ? (
                  <p className="auth-success">The file passes the format check.</p>
                ) : (
                  <ul className="guard-issues">
                    {result.problems.map((p) => (
                      <li key={p} className="guard-missing">
                        {p}
                      </li>
                    ))}
                  </ul>
                ))}
            </div>
          )}
        </>
      )}
    </Modal>
  );
}

import { useState } from "react";
import { EmptyState } from "../../components/EmptyState";
import { StatusBadge } from "../../components/StatusBadge";
import { ApiError } from "../../lib/api";
import { useQueryClient } from "@tanstack/react-query";
import { importResults, usePublishResults, useSessionResults, type ImportReport } from "../../lib/results";

/** Exam Cell: import the university's results for this exam, check, publish. */
export default function ResultsPanel({ sessionId, canManage }: { sessionId: string; canManage: boolean }) {
  const results = useSessionResults(sessionId, true);
  const publish = usePublishResults();
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [days, setDays] = useState(10);
  const r = results.data;
  const run = async (dry: boolean) => {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      setReport(await importResults(sessionId, file, dry));
      if (!dry) await qc.invalidateQueries({ queryKey: ["results"] });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not read the file.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="card">
      <h2 className="card-title">Results</h2>
      {canManage && !r?.published && (
        <>
          <p className="muted small">
            Upload the university's result file (CSV or Excel), one row per student and paper. Columns: PRN, Subject code, Grade, and optionally Internal, External,
            Total, Grade points, Credits, Result. Check it first; nothing is saved until you import.
          </p>
          <div className="tt-toolbar">
            <input aria-label="Result file" type="file" accept=".csv,.xlsx" onChange={(e) => (setFile(e.target.files?.[0] ?? null), setReport(null))} />
            <button type="button" className="btn btn-ghost btn-sm" disabled={!file || busy} onClick={() => run(true)}>
              Check
            </button>
            <button type="button" className="btn btn-primary btn-sm" disabled={!file || busy || !report || report.problems.length > 0 || report.imported} onClick={() => run(false)}>
              Import
            </button>
          </div>
        </>
      )}
      {error && <p className="form-error">{error}</p>}
      {report && (
        <div className={report.problems.length ? "form-error" : "auth-success"}>
          {report.imported ? "Imported: " : "Checked: "}
          {report.rows} rows, {report.students} students ({report.pass} pass, {report.atkt} ATKT).
          {report.problems.length > 0 && (
            <ul className="guard-issues">
              {report.problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      {publish.error && <p className="form-error">{publish.error.message}</p>}
      {r && r.students.length === 0 && <EmptyState title="No results imported yet" />}
      {r && r.students.length > 0 && (
        <>
          <p>
            <StatusBadge tone={r.published ? "success" : "neutral"}>{r.published ? "Published" : "Not published"}</StatusBadge> {r.counts.pass} pass · {r.counts.atkt} ATKT ·{" "}
            {r.counts.absent} absent{r.revaluation_until && ` · revaluation until ${r.revaluation_until}`}
          </p>
          {canManage && (
            <div className="tt-toolbar">
              {!r.published && (
                <div className="field">
                  <label htmlFor="rv-days">Days for revaluation requests</label>
                  <input id="rv-days" type="number" min={0} max={60} value={days} onChange={(e) => setDays(Number(e.target.value))} />
                </div>
              )}
              <button type="button" className={`btn btn-sm ${r.published ? "btn-ghost" : "btn-primary"}`} onClick={() => publish.mutate({ id: sessionId, publish: !r.published, revaluation_days: days })}>
                {r.published ? "Withdraw results" : "Publish to students"}
              </button>
            </div>
          )}
          <div className="data-table-scroll">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Student</th>
                  <th>SGPA</th>
                  <th>Result</th>
                  <th>Backlogs</th>
                </tr>
              </thead>
              <tbody>
                {r.students.map((s) => (
                  <tr key={s.result_id}>
                    <td>
                      {s.name}
                      <div className="muted small">{s.prn}</div>
                    </td>
                    <td>{s.sgpa?.toFixed(2) ?? "–"}</td>
                    <td className={s.outcome === "pass" ? "" : "att-critical"}>{s.outcome === "atkt" ? "ATKT" : s.outcome[0].toUpperCase() + s.outcome.slice(1)}</td>
                    <td>{s.failed.join(", ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

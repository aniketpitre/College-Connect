import { useState } from "react";
import { Link } from "react-router";
import { StatusBadge } from "../../components/StatusBadge";
import { IMPORT_TEMPLATE_URL, useCommitImport, useValidateImport, type Credential, type ImportReport } from "../../lib/students";
import "./students.css";

/** Office screen (English): check a spreadsheet, then create the students and print their logins. */
export default function ImportPage() {
  const [file, setFile] = useState<File | null>(null);
  const validate = useValidateImport();
  const commit = useCommitImport();
  const [report, setReport] = useState<ImportReport | null>(null);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [progress, setProgress] = useState<{ committed: number; total: number; done: boolean } | null>(null);

  const run = async (r: ImportReport) => {
    setProgress({ committed: r.committed, total: r.valid, done: false });
    for (;;) {
      const chunk = await commit.mutateAsync(r.id).catch(() => null);
      if (!chunk) return; // error shown below; "Continue" resumes where it stopped
      setCredentials((c) => [...c, ...chunk.credentials]);
      setProgress({ committed: chunk.committed, total: chunk.valid, done: chunk.done });
      if (chunk.done) return;
    }
  };

  if (progress?.done) return <Credentials credentials={credentials} />;

  return (
    <>
      <Link to="/app/students" className="back-link no-print">
        ← Students
      </Link>
      <div className="page-head">
        <div>
          <div className="eyebrow">Office</div>
          <h1>Import students</h1>
        </div>
      </div>

      <div className="card">
        <ol className="import-steps">
          <li>
            Download the <a href={IMPORT_TEMPLATE_URL}>template (CSV)</a> and fill one row per student. Excel (.xlsx) works too. Required
            columns: <b>prn, name, programme, year</b>. Programme, division and category use the codes from College setup (e.g. BCA, FY, A, OBC).
          </li>
          <li>Upload it. Every row is checked first; nothing is saved until the whole file is correct.</li>
          <li>Create the students. Each gets a login with a temporary password, which you can print.</li>
        </ol>
        <form
          className="import-upload"
          onSubmit={(e) => {
            e.preventDefault();
            if (file) validate.mutate(file, { onSuccess: setReport });
          }}
        >
          <input type="file" aria-label="Spreadsheet" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={(e) => (setFile(e.target.files?.[0] ?? null), setReport(null))} />
          <button type="submit" className="btn btn-primary" disabled={!file || validate.isPending || !!progress}>
            {validate.isPending ? "Checking…" : "Check file"}
          </button>
        </form>
        {validate.error && <div className="form-error">{validate.error.message}</div>}
      </div>

      {report?.status === "has_errors" && (
        <div className="card">
          <div className="section-head">
            <h2>
              {report.error_count} problem{report.error_count === 1 ? "" : "s"} in {report.total} rows
            </h2>
            <StatusBadge tone="danger">Nothing was saved</StatusBadge>
          </div>
          <p className="muted">Fix these rows in your file and upload it again. Row numbers match the spreadsheet (row 1 is the header).</p>
          <div className="data-table-scroll">
            <table className="diff-table">
              <thead>
                <tr>
                  <th>Row</th>
                  <th>PRN</th>
                  <th>Column</th>
                  <th>Problem</th>
                </tr>
              </thead>
              <tbody>
                {report.errors.map((e, i) => (
                  <tr key={i}>
                    <td>{e.row}</td>
                    <td>{e.prn ?? "—"}</td>
                    <td>{e.field}</td>
                    <td>{e.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {report.error_count > report.errors.length && <p className="muted">Showing the first {report.errors.length}.</p>}
        </div>
      )}

      {report && report.status !== "has_errors" && (
        <div className="card">
          <div className="section-head">
            <h2>All {report.valid} rows are correct</h2>
            <StatusBadge tone="success">Ready</StatusBadge>
          </div>
          {report.preview && (
            <p className="muted">
              First rows: {report.preview.map((p) => `${p.prn} ${p.name}`).join(" · ")}
              {report.valid > report.preview.length ? " …" : ""}
            </p>
          )}
          {progress && (
            <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={progress.total} aria-valuenow={progress.committed}>
              <div style={{ width: `${(100 * progress.committed) / Math.max(progress.total, 1)}%` }} />
              <span>
                {progress.committed} of {progress.total} created
              </span>
            </div>
          )}
          {commit.error && <div className="form-error">{commit.error.message}</div>}
          <div className="modal-actions">
            <button type="button" className="btn btn-primary" disabled={commit.isPending} onClick={() => run(report)}>
              {commit.isPending ? "Creating…" : progress ? "Continue" : `Create ${report.valid} students and logins`}
            </button>
          </div>
        </div>
      )}
    </>
  );
}

function Credentials({ credentials }: { credentials: Credential[] }) {
  return (
    <div className="credentials">
      <div className="page-head no-print">
        <div>
          <div className="eyebrow">Import finished</div>
          <h1>{credentials.length} students created</h1>
        </div>
        <div className="row-actions">
          <Link className="btn btn-ghost" to="/app/students">
            Go to students
          </Link>
          <button type="button" className="btn btn-primary" onClick={() => window.print()}>
            Print login slips
          </button>
        </div>
      </div>
      <p className="form-error no-print">Print or save this page now: the temporary passwords are shown only once. A lost one can be reset from the student's login (Users).</p>
      <div className="slips">
        {credentials.map((c) => (
          <div className="slip" key={c.prn}>
            <div className="slip-title">CollegeConnect: your login</div>
            <div>
              <b>{c.name}</b>
            </div>
            <div>
              PRN (username): <b>{c.prn}</b>
            </div>
            <div>
              Temporary password: <span className="mono">{c.temporary_password}</span>
            </div>
            <div className="slip-note">Sign in at the college website. You will choose your own password the first time.</div>
            <div className="slip-note" lang="hi">कॉलेज की वेबसाइट पर साइन इन करें। पहली बार आप अपना पासवर्ड चुनेंगे।</div>
            <div className="slip-note" lang="mr">महाविद्यालयाच्या वेबसाइटवर साइन इन करा. पहिल्यांदा तुम्ही स्वतःचा पासवर्ड निवडाल.</div>
          </div>
        ))}
      </div>
    </div>
  );
}

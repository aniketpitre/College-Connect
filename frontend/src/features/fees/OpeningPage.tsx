import { useState } from "react";
import { Link } from "react-router";
import { MoneyText } from "../../components/MoneyText";
import { StatusBadge } from "../../components/StatusBadge";
import { OPENING_TEMPLATE_URL, useOpeningImport, type OpeningReport } from "../../lib/fees";
import { useSetup } from "../../lib/setup";
import "./fees.css";

/** Accounts (English): fees already paid this year before CollegeConnect, and older dues. */
export default function OpeningPage() {
  const setup = useSetup();
  const run = useOpeningImport();
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<OpeningReport | null>(null);
  return (
    <>
      <Link to="/app/fees" className="back-link">
        ← Fees
      </Link>
      <div className="page-head">
        <div>
          <div className="eyebrow">Accounts · {setup.data?.current_year?.name}</div>
          <h1>Opening balances</h1>
        </div>
      </div>
      <div className="card">
        <ol className="import-steps">
          <li>
            Charge this year's fees first (Fee setup), so paid amounts can be split over the fee heads.
          </li>
          <li>
            Download the <a href={OPENING_TEMPLATE_URL}>template (CSV)</a>: one row per student with the amount already <b>paid</b> this year (and the old
            receipt number), and any <b>previous_dues</b> from earlier years. Amounts in rupees.
          </li>
          <li>Upload it to check every row; nothing is saved until the whole file is correct. Each student's opening balance can be imported once.</li>
        </ol>
        <div className="import-upload">
          <input type="file" aria-label="Spreadsheet" accept=".csv,.xlsx" onChange={(e) => (setFile(e.target.files?.[0] ?? null), setReport(null))} />
          <button type="button" className="btn btn-primary" disabled={!file || run.isPending} onClick={() => file && run.mutate({ file, commit: false }, { onSuccess: setReport })}>
            Check file
          </button>
        </div>
        {run.error && <div className="form-error">{run.error.message}</div>}
      </div>
      {report && (
        <div className="card">
          {report.committed ? (
            <div className="auth-success" role="status">
              Saved: {report.valid} students, <MoneyText paise={report.paid} /> paid and <MoneyText paise={report.dues} /> previous dues.
            </div>
          ) : report.error_count ? (
            <>
              <div className="section-head">
                <h2>{report.error_count} problems</h2>
                <StatusBadge tone="danger">Nothing was saved</StatusBadge>
              </div>
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
            </>
          ) : (
            <>
              <div className="section-head">
                <h2>{report.valid} rows are correct</h2>
                <StatusBadge tone="success">Ready</StatusBadge>
              </div>
              <p>
                Paid before CollegeConnect: <MoneyText paise={report.paid} /> · Previous dues: <MoneyText paise={report.dues} />
              </p>
              <div className="modal-actions">
                <button type="button" className="btn btn-primary" disabled={run.isPending} onClick={() => file && run.mutate({ file, commit: true }, { onSuccess: setReport })}>
                  Save opening balances
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
}

import { useState } from "react";
import { Link } from "react-router";
import { MoneyText } from "../../components/MoneyText";
import { API_V1 } from "../../lib/api";
import { reportUrl, useReport, type Report } from "../../lib/fees";
import { useSetup } from "../../lib/setup";
import "./fees.css";

const REPORTS = [
  ["day-book", "Day book", "dates"],
  ["head-wise", "Head-wise", "dates"],
  ["mode-wise", "Mode-wise", "dates"],
  ["outstanding", "Outstanding", "class"],
  ["defaulters", "Defaulters", "class"],
  ["scholarships", "Scholarships receivable", "year"],
] as const;
type Name = (typeof REPORTS)[number][0];

const todayIso = () => new Date(Date.now() + 5.5 * 3600_000).toISOString().slice(0, 10); // India date
const NOT_MONEY = new Set(["Students", "Cancelled receipts"]);

/** Accounts reports (English) with Excel download. */
export default function ReportsPage() {
  const setup = useSetup();
  const [name, setName] = useState<Name>("day-book");
  const [from, setFrom] = useState(todayIso());
  const [to, setTo] = useState(todayIso());
  const [programmeId, setProgrammeId] = useState("");
  const [year, setYear] = useState("");
  const kind = REPORTS.find((r) => r[0] === name)![2];
  const params: Record<string, string | undefined> =
    kind === "dates" ? { date_from: from, date_to: to } : kind === "class" ? { programme_id: programmeId || undefined, year_of_study: year || undefined } : {};
  const report = useReport(name, params);
  const programme = setup.data?.programmes.find((p) => p.id === programmeId);

  return (
    <>
      <Link to="/app/fees" className="back-link">
        ← Fees
      </Link>
      <div className="page-head">
        <div>
          <div className="eyebrow">Accounts</div>
          <h1>Reports</h1>
        </div>
        <a className="btn btn-ghost" href={`${API_V1}${reportUrl(name, params, "xlsx")}`}>
          Download Excel
        </a>
      </div>
      <div className="tabs" role="tablist">
        {REPORTS.map(([key, label]) => (
          <button key={key} type="button" role="tab" aria-selected={name === key} className={name === key ? "active" : ""} onClick={() => setName(key)}>
            {label}
          </button>
        ))}
      </div>
      <div className="filters">
        {kind === "dates" && (
          <>
            <label className="muted small">
              From <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
            </label>
            <label className="muted small">
              To <input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
            </label>
          </>
        )}
        {kind === "class" && (
          <>
            <select aria-label="Programme" value={programmeId} onChange={(e) => (setProgrammeId(e.target.value), setYear(""))}>
              <option value="">All programmes</option>
              {setup.data?.programmes.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.code}
                </option>
              ))}
            </select>
            <select aria-label="Year" value={year} onChange={(e) => setYear(e.target.value)} disabled={!programme}>
              <option value="">All years</option>
              {programme?.year_labels.map((l, i) => (
                <option key={l} value={i + 1}>
                  {l}
                </option>
              ))}
            </select>
          </>
        )}
        {kind !== "dates" && <span className="muted small">Academic year {setup.data?.current_year?.name}</span>}
      </div>
      {report.error && <p className="form-error">{report.error.message}</p>}
      {report.data && <ReportTable report={report.data} />}
    </>
  );
}

function ReportTable({ report }: { report: Report }) {
  return (
    <>
      <div className="tiles fee-tiles">
        {Object.entries(report.totals).map(([label, value]) => (
          <div className="tile" key={label}>
            <div className="tile-label">{label}</div>
            <div className="tile-value" style={{ fontSize: "1.3rem" }}>
              {NOT_MONEY.has(label) ? value : <MoneyText paise={value} />}
            </div>
          </div>
        ))}
      </div>
      <div className="data-table-scroll">
        <table className="statement">
          <thead>
            <tr>
              {report.columns.map((c) => (
                <th key={c.key} className={c.kind === "money" || c.kind === "int" ? "num" : ""}>
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {report.rows.length === 0 && (
              <tr>
                <td colSpan={report.columns.length} className="muted">
                  Nothing for this period.
                </td>
              </tr>
            )}
            {report.rows.map((row, i) => (
              <tr key={i} className={row.status === "Cancelled" ? "reversed" : ""}>
                {report.columns.map((c) => (
                  <td key={c.key} className={c.kind === "money" || c.kind === "int" ? "num" : ""}>
                    {c.kind === "money" ? <MoneyText paise={Number(row[c.key])} /> : String(row[c.key] ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

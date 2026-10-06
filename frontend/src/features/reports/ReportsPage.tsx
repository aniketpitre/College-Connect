import { useState } from "react";
import { EmptyState } from "../../components/EmptyState";
import { StatusBadge } from "../../components/StatusBadge";
import { hasPermission, useMe } from "../../lib/auth";
import {
  reportUrl,
  useAddEvidence,
  useAishe,
  useApaar,
  useAqar,
  useCredits,
  useImportApaar,
  useNirf,
  useRemoveEvidence,
  useSaveNaacSettings,
  type Aqar,
  type Metric,
} from "../../lib/reports";
import { useSetup } from "../../lib/setup";
import "../campus/campus.css";
import "./reports.css";

type Tab = "naac" | "aishe" | "nirf" | "apaar";

/** IQAC, Principal and Office (English): NAAC AQAR tables with gaps and evidence, AISHE, NIRF, APAAR. */
export default function ReportsPage() {
  const { data: me } = useMe();
  const setup = useSetup();
  const [tab, setTab] = useState<Tab>("naac");
  const [yearId, setYearId] = useState("");
  const years = setup.data?.academic_years ?? [];
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Reports</div>
          <h1>Accreditation and government reports</h1>
        </div>
        <label className="report-year">
          Academic year{" "}
          <select value={yearId} onChange={(e) => setYearId(e.target.value)} aria-label="Academic year">
            <option value="">Current</option>
            {years.map((y) => (
              <option key={y.id} value={y.id}>
                {y.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="tabs" role="tablist">
        {(
          [
            ["naac", "NAAC (AQAR)"],
            ["aishe", "AISHE"],
            ["nirf", "NIRF"],
            ["apaar", "APAAR / ABC"],
          ] as const
        ).map(([k, label]) => (
          <button key={k} type="button" role="tab" aria-selected={tab === k} className={tab === k ? "active" : ""} onClick={() => setTab(k)}>
            {label}
          </button>
        ))}
      </div>
      {tab === "naac" && <Naac yearId={yearId} canManage={hasPermission(me, "naac.manage")} />}
      {tab === "aishe" && <AisheView yearId={yearId} />}
      {tab === "nirf" && <NirfView yearId={yearId} />}
      {tab === "apaar" && <ApaarView yearId={yearId} canImport={hasPermission(me, "students.manage")} />}
    </>
  );
}

function Table({ columns, rows }: { columns: { key: string; label: string }[]; rows: Record<string, unknown>[] }) {
  if (!rows.length) return <p className="small muted">No rows.</p>;
  return (
    <div className="data-table data-table-scroll">
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td key={c.key}>{r[c.key] === null || r[c.key] === undefined ? "—" : String(r[c.key])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Naac({ yearId, canManage }: { yearId: string; canManage: boolean }) {
  const aqar = useAqar(yearId);
  const [open, setOpen] = useState<string | null>(null);
  const [onlyGaps, setOnlyGaps] = useState(false);
  const a = aqar.data;
  if (aqar.error) return <p className="form-error">{aqar.error.message}</p>;
  if (!a) return null;
  const metrics = onlyGaps ? a.metrics.filter((m) => m.gaps.length) : a.metrics;
  return (
    <>
      <div className="tiles fee-tiles">
        <div className="tile">
          <div className="tile-label">Metrics ({a.year.name})</div>
          <div className="tile-value">{a.metrics.length}</div>
        </div>
        <div className="tile">
          <div className="tile-label">Complete</div>
          <div className="tile-value">{a.metrics.filter((m) => !m.gaps.length).length}</div>
        </div>
        <div className={`tile${a.gaps ? " tile-warn" : ""}`}>
          <div className="tile-label">Gaps to fix</div>
          <div className="tile-value">{a.gaps}</div>
        </div>
      </div>
      <div className="row-actions" style={{ justifyContent: "flex-start", marginBottom: 10 }}>
        <label className="check-label">
          <input type="checkbox" checked={onlyGaps} onChange={(e) => setOnlyGaps(e.target.checked)} /> Show only metrics with gaps
        </label>
      </div>
      {canManage && <NaacSettingsForm a={a} />}
      {metrics.map((m) => (
        <MetricCard key={m.id} m={m} yearId={yearId} open={open === m.id} onToggle={() => setOpen(open === m.id ? null : m.id)} canManage={canManage} />
      ))}
    </>
  );
}

function MetricCard({ m, yearId, open, onToggle, canManage }: { m: Metric; yearId: string; open: boolean; onToggle: () => void; canManage: boolean }) {
  const add = useAddEvidence();
  const remove = useRemoveEvidence();
  const [title, setTitle] = useState("");
  return (
    <section className="card metric-card">
      <button type="button" className="metric-head link-button" onClick={onToggle} aria-expanded={open}>
        <span>
          <span className="eyebrow">
            {m.id} · Criterion {m.criterion}: {m.criterion_name}
          </span>
          <b className="metric-title">{m.title}</b>
        </span>
        <span className="metric-value">
          {m.value}
          {m.gaps.length ? (
            <StatusBadge tone="warning">
              {m.gaps.length} gap{m.gaps.length > 1 ? "s" : ""}
            </StatusBadge>
          ) : (
            <StatusBadge tone="success">Complete</StatusBadge>
          )}
        </span>
      </button>
      {m.gaps.length > 0 && (
        <ul className="metric-gaps small">
          {m.gaps.map((g, i) => (
            <li key={i}>{g}</li>
          ))}
        </ul>
      )}
      {open && (
        <div className="metric-body">
          {!m.manual && (
            <>
              <Table columns={m.columns} rows={m.rows} />
              <a className="small" href={reportUrl(`naac/${m.id}.csv`, yearId)}>
                Download table (CSV)
              </a>
            </>
          )}
          <h3 className="dash-h3">Evidence</h3>
          {m.evidence_needed.length > 0 && <p className="small muted">NAAC expects: {m.evidence_needed.join("; ")}</p>}
          <ul className="campus-list">
            {m.evidence.map((e) => (
              <li key={e.id}>
                <a href={`/api/v1/reports/naac/evidence/${e.id}`} target="_blank" rel="noreferrer">
                  {e.title}
                </a>
                {canManage && (
                  <button type="button" className="link-button" onClick={() => remove.mutate(e.id)}>
                    remove
                  </button>
                )}
              </li>
            ))}
          </ul>
          {canManage && (
            <div className="row-actions" style={{ justifyContent: "flex-start" }}>
              <input
                aria-label={`Evidence title for ${m.id}`}
                placeholder="Title, e.g. Sanction letter 2026"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
              <label className="btn btn-ghost btn-sm file-button">
                Upload evidence (PDF/JPG/PNG)
                <input
                  type="file"
                  accept="application/pdf,image/png,image/jpeg"
                  aria-label={`Upload evidence for ${m.id}`}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) add.mutate({ metric: m.id, yearId, title, file }, { onSuccess: () => setTitle("") });
                    e.target.value = "";
                  }}
                />
              </label>
              {add.error && <span className="form-error">{add.error.message}</span>}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function NaacSettingsForm({ a }: { a: Aqar }) {
  const setup = useSetup();
  const save = useSaveNaacSettings();
  const [posts, setPosts] = useState<string>(a.settings.sanctioned_posts?.toString() ?? "");
  const [intake, setIntake] = useState<Record<string, number>>(a.settings.intake);
  const programmes = setup.data?.programmes ?? [];
  return (
    <details className="card naac-settings">
      <summary>Sanctioned posts and intake</summary>
      <form
        className="campus-form"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate({ sanctioned_posts: posts ? Number(posts) : null, intake });
        }}
      >
        <div className="field">
          <label htmlFor="naac-posts">Sanctioned teaching posts</label>
          <input id="naac-posts" type="number" min={0} value={posts} onChange={(e) => setPosts(e.target.value)} />
        </div>
        {programmes.map((p) => (
          <div className="field" key={p.id}>
            <label htmlFor={`intake-${p.id}`}>First-year intake: {p.code}</label>
            <input
              id={`intake-${p.id}`}
              type="number"
              min={0}
              placeholder="from admissions"
              value={intake[p.id] ?? ""}
              onChange={(e) => setIntake({ ...intake, [p.id]: Number(e.target.value) })}
            />
          </div>
        ))}
        <div>
          <button type="submit" className="btn btn-primary btn-sm" disabled={save.isPending}>
            Save
          </button>
          {save.isSuccess && <span className="small muted"> Saved.</span>}
        </div>
      </form>
    </details>
  );
}

const COUNT_COLUMNS = [
  { key: "total", label: "Total" },
  { key: "female", label: "Female" },
  { key: "male", label: "Male" },
  { key: "other", label: "Transgender" },
  { key: "general", label: "General" },
  { key: "ews", label: "EWS" },
  { key: "sc", label: "SC" },
  { key: "st", label: "ST" },
  { key: "obc", label: "OBC" },
];

function Gaps({ gaps }: { gaps: string[] }) {
  if (!gaps.length) return null;
  return (
    <ul className="metric-gaps small">
      {gaps.map((g, i) => (
        <li key={i}>{g}</li>
      ))}
    </ul>
  );
}

function AisheView({ yearId }: { yearId: string }) {
  const aishe = useAishe(yearId, true);
  const a = aishe.data;
  if (!a) return null;
  return (
    <>
      <Gaps gaps={a.gaps} />
      <h2 className="subhead">Students by programme and year</h2>
      <Table columns={[{ key: "programme", label: "Programme" }, { key: "year", label: "Year" }, ...COUNT_COLUMNS]} rows={a.students} />
      <a className="small" href={reportUrl("aishe/students.csv", yearId)}>
        Download (CSV)
      </a>
      <h2 className="subhead">Staff by designation</h2>
      <Table columns={[{ key: "staff", label: "Staff" }, { key: "designation", label: "Designation" }, ...COUNT_COLUMNS]} rows={a.staff} />
      <a className="small" href={reportUrl("aishe/staff.csv", yearId)}>
        Download (CSV)
      </a>
    </>
  );
}

function NirfView({ yearId }: { yearId: string }) {
  const nirf = useNirf(yearId, true);
  if (!nirf.data) return null;
  return (
    <>
      <p className="small muted">The data points CollegeConnect can fill for {nirf.data.year}; enter the rest (finances, research) on the NIRF portal.</p>
      <Table
        columns={[
          { key: "item", label: "Data point" },
          { key: "value", label: "Value" },
        ]}
        rows={nirf.data.points}
      />
      <a className="small" href={reportUrl("nirf.csv", yearId)}>
        Download (CSV)
      </a>
    </>
  );
}

function ApaarView({ yearId, canImport }: { yearId: string; canImport: boolean }) {
  const check = useApaar(true);
  const credits = useCredits(yearId, true);
  const imp = useImportApaar();
  const c = check.data;
  return (
    <>
      {c && (
        <div className="tiles fee-tiles">
          <div className="tile">
            <div className="tile-label">Students with a valid APAAR ID</div>
            <div className="tile-value">
              {c.valid}/{c.students}
            </div>
          </div>
          <div className={`tile${c.missing.length ? " tile-warn" : ""}`}>
            <div className="tile-label">Missing</div>
            <div className="tile-value">{c.missing.length}</div>
          </div>
          <div className={`tile${c.invalid.length + c.duplicate.length ? " tile-warn" : ""}`}>
            <div className="tile-label">Invalid or duplicate</div>
            <div className="tile-value">{c.invalid.length + c.duplicate.length}</div>
          </div>
        </div>
      )}
      {canImport && (
        <div className="row-actions" style={{ justifyContent: "flex-start", marginBottom: 12 }}>
          <label className="btn btn-ghost btn-sm file-button">
            Import APAAR IDs (CSV with PRN and APAAR ID columns)
            <input
              type="file"
              accept=".csv,text/csv"
              aria-label="Import APAAR IDs"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) imp.mutate(file);
                e.target.value = "";
              }}
            />
          </label>
          {imp.data && (
            <span className="small" role="status">
              {imp.data.updated} updated{imp.data.problems.length > 0 && `, ${imp.data.problems.length} row(s) with problems`}
            </span>
          )}
          {imp.error && <span className="form-error">{imp.error.message}</span>}
        </div>
      )}
      {imp.data && imp.data.problems.length > 0 && (
        <Table
          columns={[
            { key: "row", label: "Row" },
            { key: "prn", label: "PRN" },
            { key: "problem", label: "Problem" },
          ]}
          rows={imp.data.problems}
        />
      )}
      {c && c.invalid.length + c.duplicate.length > 0 && (
        <>
          <h2 className="subhead">To correct</h2>
          <ul className="campus-list">
            {[...c.invalid.map((s) => ({ ...s, why: "not 12 digits" })), ...c.duplicate.map((s) => ({ ...s, why: "used by another student" }))].map((s) => (
              <li key={`${s.id}-${s.why}`}>
                <span>
                  {s.name} ({s.prn}) · {s.apaar_id}
                </span>
                <span className="small att-critical">{s.why}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      <h2 className="subhead">Credits for the ABC portal</h2>
      {credits.data && credits.data.rows === 0 ? (
        <EmptyState title="No published results with credits for this year" />
      ) : (
        credits.data && (
          <>
            <p className="small">
              {credits.data.rows} course result(s) for {credits.data.students} student(s), {credits.data.credits} credits.
              {credits.data.skipped_without_apaar > 0 && ` ${credits.data.skipped_without_apaar} student(s) left out: no valid APAAR ID.`}
            </p>
            <a className="btn btn-primary btn-sm" href={reportUrl("apaar/credits.csv", yearId)}>
              Download credits (CSV)
            </a>
          </>
        )
      )}
      {c && c.missing.length > 0 && (
        <details className="card" style={{ marginTop: 12 }}>
          <summary>{c.missing.length} student(s) without an APAAR ID</summary>
          <p className="small">{c.missing.map((s) => `${s.name} (${s.prn})`).join(", ")}</p>
        </details>
      )}
    </>
  );
}

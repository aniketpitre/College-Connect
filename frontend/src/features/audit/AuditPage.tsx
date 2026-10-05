import { useState } from "react";
import { EmptyState } from "../../components/EmptyState";
import { useAudit, type AuditFilters, type AuditRow } from "../../lib/admin";
import "./audit.css";

const when = (iso: string) => new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "medium" });

function describe(row: AuditRow): string {
  const parts = Object.entries(row.details)
    .filter(([, v]) => v !== null && v !== "" && typeof v !== "object")
    .map(([k, v]) => `${k.replace(/_/g, " ")}: ${String(v)}`);
  return parts.join(" · ");
}

/** Read-only audit log (System Admin, Principal): who did what, when, from where. */
export default function AuditPage() {
  const [draft, setDraft] = useState<AuditFilters>({});
  const [filters, setFilters] = useState<AuditFilters>({});
  const audit = useAudit(filters);
  const rows = audit.data?.pages.flatMap((p) => p.rows) ?? [];
  const areas = audit.data?.pages[0]?.areas ?? {};

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Read-only</div>
          <h1>Audit log</h1>
        </div>
      </div>
      <p className="muted">Every sign-in, and every change to money, records, roles and notices. Entries can't be edited or deleted.</p>
      <form
        className="audit-filters card"
        onSubmit={(e) => {
          e.preventDefault();
          setFilters({ ...draft });
        }}
      >
        <div className="field">
          <label htmlFor="a-area">Area</label>
          <select id="a-area" value={draft.area ?? ""} onChange={(e) => setDraft({ ...draft, area: e.target.value })}>
            <option value="">Everything</option>
            {Object.entries(areas).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="a-actor">Done by</label>
          <input id="a-actor" placeholder="Name or email" value={draft.actor ?? ""} onChange={(e) => setDraft({ ...draft, actor: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor="a-from">From</label>
          <input id="a-from" type="date" value={draft.from ?? ""} onChange={(e) => setDraft({ ...draft, from: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor="a-to">To</label>
          <input id="a-to" type="date" value={draft.to ?? ""} onChange={(e) => setDraft({ ...draft, to: e.target.value })} />
        </div>
        <button type="submit" className="btn btn-primary">
          Show
        </button>
      </form>
      {audit.error && <p className="form-error">{audit.error.message}</p>}
      {audit.isSuccess && rows.length === 0 && <EmptyState title="No entries match" />}
      {rows.length > 0 && (
        <div className="table-wrap">
          <table className="audit-table">
            <thead>
              <tr>
                <th>When</th>
                <th>What</th>
                <th>Who</th>
                <th>About</th>
                <th>Details</th>
                <th>IP</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td className="nowrap">{when(r.at)}</td>
                  <td>
                    <code>{r.action}</code>
                  </td>
                  <td>{r.actor ?? <span className="muted">system</span>}</td>
                  <td>{r.target ?? (r.target_type ? <span className="muted">{r.target_type}</span> : "")}</td>
                  <td className="audit-details">
                    {r.reason && (
                      <div>
                        <span className="muted">Reason:</span> {r.reason}
                      </div>
                    )}
                    {describe(r)}
                  </td>
                  <td className="muted small">{r.ip}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {audit.hasNextPage && (
        <button type="button" className="btn btn-ghost" disabled={audit.isFetchingNextPage} onClick={() => audit.fetchNextPage()}>
          {audit.isFetchingNextPage ? "Loading…" : "Show older entries"}
        </button>
      )}
    </>
  );
}

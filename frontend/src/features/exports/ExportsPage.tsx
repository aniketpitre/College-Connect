import { useState } from "react";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { EmptyState } from "../../components/EmptyState";
import { StatusBadge } from "../../components/StatusBadge";
import { hasPermission, useMe } from "../../lib/auth";
import { downloadFullExport, exportDownloadUrl, fullExportName, useDecideExport, useExports, useRequestExport, type ExportRequest } from "../../lib/admin";
import "../fees/fees.css";

const when = (iso: string) => new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
const TONE = { pending: "warning", approved: "success", rejected: "danger" } as const;

/** Full CSV exports: the System Admin asks, the Principal approves, then the admin downloads within 24 hours. */
export default function ExportsPage() {
  const { data: me } = useMe();
  const list = useExports();
  const ask = useRequestExport();
  const decide = useDecideExport();
  const [dataset, setDataset] = useState("students");
  const [reason, setReason] = useState("");
  const [deciding, setDeciding] = useState<{ r: ExportRequest; approve: boolean } | null>(null);
  const canAsk = hasPermission(me, "export.request");
  const canDecide = hasPermission(me, "approvals.decide");
  const datasets = list.data?.datasets ?? {};
  const [progress, setProgress] = useState<{ id: string; text: string; error?: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const saveFull = async (r: ExportRequest) => {
    setBusy(true);
    setProgress({ id: r.id, text: "Starting…" });
    try {
      const blob = await downloadFullExport(r.id, (done, total, name) => setProgress({ id: r.id, text: name ? `Reading ${name} (${done + 1} of ${total})…` : "Saving…" }));
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = fullExportName();
      a.click();
      URL.revokeObjectURL(a.href);
      setProgress({ id: r.id, text: "Saved. Keep the file somewhere safe: it holds everyone's records." });
    } catch (e) {
      setProgress({ id: r.id, text: e instanceof Error ? e.message : "The export failed.", error: true });
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">{canDecide ? "Principal" : "System Admin"}</div>
          <h1>Data export</h1>
        </div>
      </div>
      <p className="muted">
        The college's data can be exported as CSV files that open in Excel, or everything at once as a ZIP that loads into a fresh database (no passwords are
        included). Each export needs the Principal's approval and can be downloaded for 24 hours.
      </p>
      {canAsk && (
        <form
          className="card export-form"
          onSubmit={(e) => {
            e.preventDefault();
            ask.mutate({ dataset, reason }, { onSuccess: () => setReason("") });
          }}
        >
          <h2 className="subhead">Ask for an export</h2>
          {ask.error && <p className="form-error">{ask.error.message}</p>}
          <div className="field-row">
            <div className="field">
              <label htmlFor="x-dataset">Data</label>
              <select id="x-dataset" value={dataset} onChange={(e) => setDataset(e.target.value)}>
                {Object.entries(datasets).map(([k, label]) => (
                  <option key={k} value={k}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="x-reason">Why is it needed?</label>
              <input id="x-reason" value={reason} onChange={(e) => setReason(e.target.value)} required minLength={5} placeholder="e.g. Annual audit by the CA" />
            </div>
          </div>
          <button type="submit" className="btn btn-primary" disabled={ask.isPending}>
            Send for approval
          </button>
        </form>
      )}
      {decide.error && <p className="form-error">{decide.error.message}</p>}
      {list.data?.requests.length === 0 && <EmptyState title="No export requests yet" />}
      <div className="request-list">
        {list.data?.requests.map((r) => (
          <div className="card request-card" key={r.id}>
            <div className="request-head">
              <StatusBadge tone={TONE[r.status]}>{r.status === "pending" ? "Waiting for approval" : r.status === "approved" ? "Approved" : "Rejected"}</StatusBadge>
              <b>{r.dataset_label}</b>
            </div>
            <p className="request-reason">
              <span className="muted">Reason:</span> {r.reason}
            </p>
            <p className="muted small">
              Asked by {r.requested_by} on {when(r.requested_at)}
              {r.decided_by && ` · ${r.status} by ${r.decided_by}${r.decision_reason ? `: ${r.decision_reason}` : ""}`}
              {r.expires_at && r.status === "approved" && ` · ${r.downloadable ? "available until" : "expired"} ${when(r.expires_at)}`}
            </p>
            <div className="row-actions">
              {canDecide && r.status === "pending" && r.requested_by_id !== me?.id && (
                <>
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => setDeciding({ r, approve: false })}>
                    Reject
                  </button>
                  <button type="button" className="btn btn-primary btn-sm" onClick={() => setDeciding({ r, approve: true })}>
                    Approve
                  </button>
                </>
              )}
              {canAsk && r.downloadable && r.requested_by_id === me?.id && r.dataset !== "full" && (
                <a className="btn btn-primary btn-sm" href={exportDownloadUrl(r.id)} download>
                  Download CSV
                </a>
              )}
              {canAsk && r.downloadable && r.requested_by_id === me?.id && r.dataset === "full" && (
                <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={() => void saveFull(r)}>
                  Download everything (ZIP)
                </button>
              )}
            </div>
            {progress?.id === r.id && (
              <p className={progress.error ? "form-error" : "small muted"} role="status">
                {progress.text}
              </p>
            )}
            <div>
            </div>
          </div>
        ))}
      </div>
      <ConfirmDialog
        open={!!deciding}
        title={deciding?.approve ? "Approve this export?" : "Reject this export?"}
        message={
          deciding?.approve
            ? `${deciding.r.requested_by} will be able to download "${deciding.r.dataset_label}" for 24 hours. The download is recorded in the audit log.`
            : "Say why, so the requester knows."
        }
        confirmLabel={deciding?.approve ? "Approve" : "Reject"}
        requireReason={deciding ? !deciding.approve : false}
        danger={deciding ? !deciding.approve : false}
        onCancel={() => setDeciding(null)}
        onConfirm={(why) => {
          if (deciding) decide.mutate({ id: deciding.r.id, approve: deciding.approve, reason: why || undefined });
          setDeciding(null);
        }}
      />
    </>
  );
}

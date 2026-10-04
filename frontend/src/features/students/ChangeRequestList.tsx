import { useState } from "react";
import { Link } from "react-router";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { EmptyState } from "../../components/EmptyState";
import { StatusBadge } from "../../components/StatusBadge";
import { STUDENT_STRINGS } from "../../i18n/student";
import { useSetup } from "../../lib/setup";
import { useChangeQueue, useDecideRequest, type ChangeRequest } from "../../lib/students";
import { describeValue } from "./describe";

const L = STUDENT_STRINGS.en;

/** Office view of correction requests: what the student asked for, against what is on record. */
export function ChangeRequestList({ status, studentId, canDecide }: { status: string; studentId?: string; canDecide: boolean }) {
  const requests = useChangeQueue(status, studentId);
  const decide = useDecideRequest();
  const setup = useSetup();
  const [rejecting, setRejecting] = useState<ChangeRequest | null>(null);

  if (requests.isLoading) return <p className="muted">Loading…</p>;
  if (!requests.data?.length) return <EmptyState title="No correction requests waiting" />;
  return (
    <div className="request-list">
      {decide.error && <p className="form-error">{decide.error.message}</p>}
      {requests.data.map((r) => (
        <div className="card request-card" key={r.id}>
          <div className="request-head">
            {r.student_name && !studentId && (
              <Link to={`/app/students/${r.student_id}`}>
                <b>{r.student_name}</b> · PRN {r.prn}
              </Link>
            )}
            <span className="muted">{new Date(r.created_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}</span>
            {r.status !== "pending" && <StatusBadge tone={r.status === "approved" ? "success" : "neutral"}>{L.requestStatus[r.status]}</StatusBadge>}
          </div>
          <table className="diff-table">
            <thead>
              <tr>
                <th>Field</th>
                <th>On record</th>
                <th>Asked for</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(r.changes).map(([field, value]) => (
                <tr key={field}>
                  <td>{L.fields[field] ?? L.sections[field as keyof typeof L.sections] ?? field}</td>
                  <td className="muted">{describeValue(field, r.current[field], setup.data)}</td>
                  <td>
                    <b>{describeValue(field, value, setup.data)}</b>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="request-reason">
            <span className="muted">Reason:</span> {r.reason}
          </p>
          {canDecide && r.status === "pending" && (
            <div className="row-actions">
              <button type="button" className="btn btn-ghost btn-sm" disabled={decide.isPending} onClick={() => setRejecting(r)}>
                Reject
              </button>
              <button type="button" className="btn btn-primary btn-sm" disabled={decide.isPending} onClick={() => decide.mutate({ id: r.id, approve: true })}>
                Approve and update record
              </button>
            </div>
          )}
        </div>
      ))}
      <ConfirmDialog
        open={rejecting !== null}
        title="Reject this correction?"
        message="The record stays as it is. Tell the student why, so they know what to do."
        confirmLabel="Reject"
        requireReason
        onCancel={() => setRejecting(null)}
        onConfirm={(reason) => {
          decide.mutate({ id: rejecting!.id, approve: false, reason });
          setRejecting(null);
        }}
      />
    </div>
  );
}

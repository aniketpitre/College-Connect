import { useState } from "react";
import { Link } from "react-router";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { EmptyState } from "../../components/EmptyState";
import { MoneyText } from "../../components/MoneyText";
import { StatusBadge } from "../../components/StatusBadge";
import { hasPermission, useMe } from "../../lib/auth";
import { useApprovals, useDecide, type Approval } from "../../lib/fees";
import "../fees/fees.css";

/** Principal's inbox (English): concessions, receipt cancellations and refunds waiting for a decision. */
export default function ApprovalsPage() {
  const { data: me } = useMe();
  const [status, setStatus] = useState<"pending" | "approved" | "rejected">("pending");
  const list = useApprovals(status);
  const decide = useDecide();
  const [rejecting, setRejecting] = useState<Approval | null>(null);
  const [approving, setApproving] = useState<Approval | null>(null);
  const canDecide = hasPermission(me, "approvals.decide");

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Principal</div>
          <h1>Approvals</h1>
        </div>
      </div>
      <div className="tabs" role="tablist">
        {(["pending", "approved", "rejected"] as const).map((s) => (
          <button key={s} type="button" role="tab" aria-selected={status === s} className={status === s ? "active" : ""} onClick={() => setStatus(s)}>
            {s === "pending" ? "Waiting" : s === "approved" ? "Approved" : "Rejected"}
          </button>
        ))}
      </div>
      {decide.error && <p className="form-error">{decide.error.message}</p>}
      {list.data?.length === 0 && <EmptyState title={status === "pending" ? "Nothing waiting for you" : "Nothing here yet"} />}
      <div className="request-list">
        {list.data?.map((r) => (
          <div className="card request-card" key={r.id}>
            <div className="request-head">
              <StatusBadge tone={r.kind === "concession" ? "info" : "warning"}>{r.kind_label}</StatusBadge>
              <b>
                <MoneyText paise={r.amount} />
              </b>
              <Link to={`/app/fees/students/${r.student_id}`}>
                {r.student_name} · PRN {r.prn}
              </Link>
            </div>
            <p className="request-reason">
              {r.kind === "concession" && (
                <>
                  {r.details.concession_label} concession on {r.details.head}.{" "}
                </>
              )}
              {r.details.receipt_number && <>Receipt {r.details.receipt_number}. </>}
              <span className="muted">Reason:</span> {r.reason}
            </p>
            <p className="muted small">
              Asked by {r.requested_by} on {new Date(r.requested_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
              {r.decided_by && ` · ${r.status} by ${r.decided_by}${r.decision_reason ? `: ${r.decision_reason}` : ""}`}
            </p>
            {canDecide && r.status === "pending" && (
              <div className="row-actions">
                {r.requested_by_id === me?.id ? (
                  <span className="muted small">You asked for this; another approver must decide.</span>
                ) : (
                  <>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => setRejecting(r)}>
                      Reject
                    </button>
                    <button type="button" className="btn btn-primary btn-sm" onClick={() => setApproving(r)}>
                      Approve
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
      <ConfirmDialog
        open={approving !== null}
        title={`Approve ${approving?.kind_label.toLowerCase() ?? ""}?`}
        message="The student's fee account changes immediately and the decision is recorded."
        confirmLabel="Approve"
        onCancel={() => setApproving(null)}
        onConfirm={() => {
          decide.mutate({ id: approving!.id, approve: true });
          setApproving(null);
        }}
      />
      <ConfirmDialog
        open={rejecting !== null}
        title="Reject this request?"
        message="Nothing changes in the student's account. Accounts sees your reason."
        confirmLabel="Reject"
        requireReason
        danger
        onCancel={() => setRejecting(null)}
        onConfirm={(reason) => {
          decide.mutate({ id: rejecting!.id, approve: false, reason });
          setRejecting(null);
        }}
      />
    </>
  );
}

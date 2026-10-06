import { useState } from "react";
import { EmptyState } from "../../components/EmptyState";
import { StatusBadge } from "../../components/StatusBadge";
import { useMessageLog, useRunQueue } from "../../lib/messages";

/** Staff: what was sent to whom (last 180 days), and the queue waiting for the daily job. */
export default function MessagesPage() {
  const [template, setTemplate] = useState("");
  const [status, setStatus] = useState("");
  const log = useMessageLog({ template, status });
  const run = useRunQueue();
  const d = log.data;
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Messages</div>
          <h1>Delivery log</h1>
        </div>
        <div className="row-actions">
          <select aria-label="Message" value={template} onChange={(e) => setTemplate(e.target.value)}>
            <option value="">All messages</option>
            {Object.entries(d?.templates ?? {}).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </select>
          <select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Sent and failed</option>
            <option value="sent">Sent</option>
            <option value="failed">Failed</option>
          </select>
        </div>
      </div>
      {d && (
        <p className="muted">
          Channels: email{d.available.sms ? ", SMS" : " (SMS not set up)"}
          {d.available.whatsapp ? ", WhatsApp" : " (WhatsApp not set up)"}. Results, fee reminders and attendance alerts are queued and sent by the daily job
          at 9:00.
        </p>
      )}
      {d && d.waiting > 0 && (
        <div className="row-actions" style={{ justifyContent: "flex-start", marginBottom: 12 }}>
          <span>
            <b>{d.waiting}</b> waiting to be sent.
          </span>
          <button type="button" className="btn btn-primary btn-sm" disabled={run.isPending} onClick={() => run.mutate()}>
            {run.isPending ? "Sending…" : "Send now"}
          </button>
        </div>
      )}
      {run.isSuccess && <p className="muted small">Sent {run.data} messages.</p>}
      {(log.error ?? run.error) && <p className="form-error">{(log.error ?? run.error)?.message}</p>}
      {d?.messages.length === 0 && <EmptyState title="No messages yet" />}
      {d && d.messages.length > 0 && (
        <div className="data-table data-table-scroll">
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>To</th>
                <th>Message</th>
                <th>Channel</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {d.messages.map((m, i) => (
                <tr key={i}>
                  <td>{new Date(m.at).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</td>
                  <td>
                    {m.to_name}
                    <div className="muted small">{m.to}</div>
                  </td>
                  <td>{m.template_label}</td>
                  <td>{m.channel === "sms" ? "SMS" : m.channel === "whatsapp" ? "WhatsApp" : "Email"}</td>
                  <td>
                    <StatusBadge tone={m.status === "sent" ? "success" : "danger"}>{m.status === "sent" ? "Sent" : "Failed"}</StatusBadge>
                    {m.error && <div className="muted small">{m.error}</div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

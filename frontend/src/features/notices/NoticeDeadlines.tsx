import { useState } from "react";
import { StatusBadge } from "../../components/StatusBadge";
import { useDeadlineActions, useNoticeDeadlines, type Deadline } from "../../lib/deadlines";

const day = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
const SOURCE = { ai: "found by AI", pattern: "found in the text", staff: "added by staff" };

/** Staff (English): dates found in the notice; confirmed ones remind its students (deadline radar). */
export function NoticeDeadlines({ noticeId }: { noticeId: string }) {
  const list = useNoticeDeadlines(noticeId);
  const { decide, add, find } = useDeadlineActions(noticeId);
  const [date, setDate] = useState("");
  const [what, setWhat] = useState("");
  const error = decide.error ?? add.error ?? find.error;
  return (
    <section className="card">
      <h2 className="card-title">Deadlines for students</h2>
      <p className="small muted">
        Confirm the dates students must act by. Confirmed deadlines show on their home page two weeks ahead, and they get a reminder 3 days before and on the
        day. Nothing goes out until you confirm it.
      </p>
      {error && <p className="form-error">{error.message}</p>}
      {list.data?.length === 0 && <p className="small muted">No dates found in this notice.</p>}
      <ul className="campus-list">
        {list.data?.map((d) => (
          <Row key={d.id} d={d} onDecide={(status, change) => decide.mutate({ id: d.id, status, ...change })} busy={decide.isPending} />
        ))}
      </ul>
      <form
        className="row-actions"
        style={{ justifyContent: "flex-start", flexWrap: "wrap" }}
        onSubmit={(e) => {
          e.preventDefault();
          add.mutate({ date, what }, { onSuccess: () => (setDate(""), setWhat("")) });
        }}
      >
        <input type="date" aria-label="Deadline date" value={date} onChange={(e) => setDate(e.target.value)} required />
        <input
          aria-label="What students must do"
          placeholder="What students must do"
          value={what}
          onChange={(e) => setWhat(e.target.value)}
          required
          minLength={3}
        />
        <button type="submit" className="btn btn-ghost btn-sm" disabled={add.isPending}>
          Add a deadline
        </button>
        <button type="button" className="btn btn-ghost btn-sm" disabled={find.isPending} onClick={() => find.mutate()}>
          Look for dates again
        </button>
      </form>
    </section>
  );
}

function Row({
  d,
  onDecide,
  busy,
}: {
  d: Deadline;
  onDecide: (status: "confirmed" | "dismissed", change?: { date?: string; what?: string }) => void;
  busy: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [date, setDate] = useState(d.date);
  const [what, setWhat] = useState(d.what.en);
  return (
    <li>
      <div>
        {editing ? (
          <span className="row-actions" style={{ justifyContent: "flex-start" }}>
            <input type="date" aria-label="Date" value={date} onChange={(e) => setDate(e.target.value)} />
            <input aria-label="What" value={what} onChange={(e) => setWhat(e.target.value)} />
          </span>
        ) : (
          <>
            <b>{day(d.date)}</b> · {d.what.en}
            <div className="small muted">
              {SOURCE[d.source]}
              {d.what.hi || d.what.mr ? ` · ${[d.what.hi, d.what.mr].filter(Boolean).join(" · ")}` : ""}
            </div>
          </>
        )}
      </div>
      <span className="row-actions">
        <StatusBadge tone={d.status === "confirmed" ? "success" : d.status === "proposed" ? "warning" : "neutral"}>{d.status}</StatusBadge>
        {d.status !== "confirmed" && (
          <button
            type="button"
            className="btn btn-primary btn-sm"
            disabled={busy}
            onClick={() => (onDecide("confirmed", editing ? { date, what } : undefined), setEditing(false))}
          >
            Confirm
          </button>
        )}
        {d.status === "proposed" && !editing && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditing(true)}>
            Correct
          </button>
        )}
        {d.status !== "dismissed" && (
          <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => onDecide("dismissed")}>
            {d.status === "confirmed" ? "Cancel reminder" : "Dismiss"}
          </button>
        )}
      </span>
    </li>
  );
}

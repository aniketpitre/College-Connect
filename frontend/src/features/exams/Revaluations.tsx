import { useState } from "react";
import { EmptyState } from "../../components/EmptyState";
import { Modal } from "../../components/Modal";
import { StatusBadge } from "../../components/StatusBadge";
import { useDecideReval, useRevaluations, type Revaluation } from "../../lib/results";

/** Exam Cell: revaluation requests, sent to the university and their outcome recorded. */
export default function Revaluations({ canManage }: { canManage: boolean }) {
  const [status, setStatus] = useState("requested");
  const list = useRevaluations(status);
  const decide = useDecideReval();
  const [changing, setChanging] = useState<Revaluation | null>(null);
  return (
    <>
      <div className="day-pick">
        {[
          ["requested", "New"],
          ["forwarded", "Sent to university"],
          ["changed", "Changed"],
          ["unchanged", "No change"],
        ].map(([v, label]) => (
          <button key={v} type="button" className={`btn btn-sm ${status === v ? "btn-primary" : "btn-ghost"}`} onClick={() => setStatus(v)}>
            {label}
          </button>
        ))}
      </div>
      {decide.error && <p className="form-error">{decide.error.message}</p>}
      {list.data?.length === 0 && <EmptyState title="Nothing here" />}
      <div className="request-list">
        {list.data?.map((r) => (
          <div key={r.id} className="card request-card">
            <div className="request-head">
              <b>
                {r.name} · {r.prn}
              </b>
              <span className="muted">
                {r.code} · {r.exam}
              </span>
              <StatusBadge tone={r.status === "changed" ? "success" : r.status === "requested" ? "info" : "neutral"}>{r.status_label}</StatusBadge>
            </div>
            <p className="small">
              Was: total {r.old.total ?? "–"}, grade {r.old.grade}
              {r.new && ` → now total ${r.new.total ?? "–"}, grade ${r.new.grade}`}
            </p>
            {canManage && (r.status === "requested" || r.status === "forwarded") && (
              <div className="row-actions">
                {r.status === "requested" && (
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => decide.mutate({ id: r.id, status: "forwarded" })}>
                    Mark sent to university
                  </button>
                )}
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => decide.mutate({ id: r.id, status: "unchanged" })}>
                  No change
                </button>
                <button type="button" className="btn btn-primary btn-sm" onClick={() => setChanging(r)}>
                  Marks changed
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
      {changing && <ChangedModal r={changing} onClose={() => setChanging(null)} />}
    </>
  );
}

function ChangedModal({ r, onClose }: { r: Revaluation; onClose: () => void }) {
  const decide = useDecideReval();
  const [external, setExternal] = useState("");
  const [total, setTotal] = useState("");
  const [grade, setGrade] = useState("");
  return (
    <Modal open title={`${r.code} · ${r.name}`} onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          decide.mutate(
            { id: r.id, status: "changed", external: external ? Number(external) : null, total: total ? Number(total) : null, grade: grade.toUpperCase() },
            { onSuccess: onClose },
          );
        }}
      >
        {decide.error && <div className="form-error">{decide.error.message}</div>}
        <div className="field-row">
          <div className="field">
            <label htmlFor="rv-ext">New external marks</label>
            <input id="rv-ext" type="number" value={external} onChange={(e) => setExternal(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="rv-total">New total</label>
            <input id="rv-total" type="number" value={total} onChange={(e) => setTotal(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="rv-grade">New grade</label>
            <input id="rv-grade" value={grade} onChange={(e) => setGrade(e.target.value)} required />
          </div>
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={decide.isPending}>
            Save
          </button>
        </div>
      </form>
    </Modal>
  );
}

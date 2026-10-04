import { useState } from "react";
import { Link } from "react-router";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { StatusBadge } from "../../components/StatusBadge";
import { useSetup } from "../../lib/setup";
import { usePromote, type PromotionPlan } from "../../lib/students";
import "./students.css";

const OUTCOME = {
  promoted: ["Moves up", "success"],
  graduates: ["Graduates", "info"],
  held_back: ["Stays", "warning"],
  already_promoted: ["Already moved this year", "neutral"],
} as const;

/** Office screen (English): move a whole class up one year at the end of the academic year. */
export default function PromotePage() {
  const setup = useSetup();
  const promote = usePromote();
  const [programmeId, setProgrammeId] = useState("");
  const [fromYear, setFromYear] = useState(0);
  const [held, setHeld] = useState<string[]>([]);
  const [plan, setPlan] = useState<PromotionPlan | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [result, setResult] = useState<PromotionPlan | null>(null);
  const programme = setup.data?.programmes.find((p) => p.id === programmeId);

  const preview = (hold: string[]) =>
    promote.mutate({ programme_id: programmeId, from_year: fromYear, hold_back: hold, dry_run: true }, { onSuccess: setPlan });

  return (
    <>
      <Link to="/app/students" className="back-link">
        ← Students
      </Link>
      <div className="page-head">
        <div>
          <div className="eyebrow">Office · end of year</div>
          <h1>Promote a class</h1>
        </div>
      </div>
      <p className="muted">
        Moves every active student of a year up by one (the final year graduates). Untick students who stay back. Each student moves at most
        once per academic year, so the order of classes doesn't matter.
      </p>
      <div className="filters">
        <select aria-label="Programme" value={programmeId} onChange={(e) => (setProgrammeId(e.target.value), setFromYear(0), setPlan(null))}>
          <option value="">Programme…</option>
          {setup.data?.programmes
            .filter((p) => p.status === "active")
            .map((p) => (
              <option key={p.id} value={p.id}>
                {p.code}
              </option>
            ))}
        </select>
        <select aria-label="Year" value={fromYear || ""} onChange={(e) => (setFromYear(Number(e.target.value)), setPlan(null))} disabled={!programme}>
          <option value="">Year…</option>
          {programme?.year_labels.map((label, i) => (
            <option key={label} value={i + 1}>
              {label}
            </option>
          ))}
        </select>
        <button type="button" className="btn btn-primary btn-sm" disabled={!fromYear || promote.isPending} onClick={() => (setHeld([]), setResult(null), preview([]))}>
          Show students
        </button>
      </div>
      {promote.error && <div className="form-error">{promote.error.message}</div>}

      {result && (
        <div className="auth-success" role="status">
          Done for {result.academic_year}: {result.counts.promoted} moved to {result.to_year ?? "—"}, {result.counts.graduates} graduated, {result.counts.held_back} stayed.
        </div>
      )}

      {plan && !result && (
        <div className="card">
          <div className="section-head">
            <h2>
              {plan.programme} {plan.from_year} → {plan.to_year ?? "graduation"} ({plan.academic_year})
            </h2>
            <span className="muted">
              {plan.counts.promoted + plan.counts.graduates} move · {plan.counts.held_back} stay
              {plan.counts.already_promoted ? ` · ${plan.counts.already_promoted} already moved` : ""}
            </span>
          </div>
          <ul className="promote-list">
            {plan.students.map((s) => (
              <li key={s.id}>
                <label className="check-label">
                  <input
                    type="checkbox"
                    disabled={s.outcome === "already_promoted"}
                    checked={!held.includes(s.id) && s.outcome !== "already_promoted"}
                    onChange={(e) => {
                      const next = e.target.checked ? held.filter((h) => h !== s.id) : [...held, s.id];
                      setHeld(next);
                      preview(next);
                    }}
                  />
                  <span>
                    {s.name} <span className="muted">· {s.prn}</span>
                  </span>
                </label>
                <StatusBadge tone={OUTCOME[s.outcome][1]}>{OUTCOME[s.outcome][0]}</StatusBadge>
              </li>
            ))}
          </ul>
          <div className="modal-actions">
            <button type="button" className="btn btn-primary" disabled={!(plan.counts.promoted + plan.counts.graduates) || promote.isPending} onClick={() => setConfirming(true)}>
              {plan.to_year ? `Move ${plan.counts.promoted} students to ${plan.to_year}` : `Mark ${plan.counts.graduates} students graduated`}
            </button>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={confirming}
        title="Promote this class?"
        message="Each student's year (or graduation) is updated and recorded in their history."
        confirmLabel="Promote"
        requireReason
        onCancel={() => setConfirming(false)}
        onConfirm={(reason) => {
          setConfirming(false);
          promote.mutate(
            { programme_id: programmeId, from_year: fromYear, hold_back: held, dry_run: false, reason },
            { onSuccess: (r) => (setResult(r), setPlan(null)) },
          );
        }}
      />
    </>
  );
}

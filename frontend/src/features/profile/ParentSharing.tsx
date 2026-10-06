import { useState } from "react";
import { PARENT_STRINGS } from "../../i18n/parent";
import type { Language } from "../../lib/types";
import { useSetSharing, useSharing, type Access, type Area } from "../../lib/parent";

const AREAS: Area[] = ["fees", "attendance", "results"];

/** The student decides what linked parents see (DPDP Act); under-18s can't change it. */
export function ParentSharing({ language }: { language: Language }) {
  const P = PARENT_STRINGS[language];
  const sharing = useSharing();
  const save = useSetSharing();
  const [draft, setDraft] = useState<Access | null>(null); // null: nothing changed yet
  const d = sharing.data;
  if (!d) return null;
  const value = draft ?? d.access;
  const changed = AREAS.some((a) => value[a] !== d.access[a]);
  return (
    <section className="card sharing-card">
      <p className="muted small">{P.sharingIntro}</p>
      <p className="small">{d.parents.length ? P.linked(d.parents.map((x) => (x.relation ? `${x.name} (${x.relation})` : x.name)).join(", ")) : P.noParents}</p>
      {!d.can_change && <p className="small">{P.minorNote}</p>}
      {AREAS.map((a) => (
        <label key={a} className="check-label">
          <input type="checkbox" checked={value[a]} disabled={!d.can_change} onChange={(e) => setDraft({ ...value, [a]: e.target.checked })} />
          {P.areas[a]}
        </label>
      ))}
      {d.can_change && (
        <div className="row-actions">
          <button type="button" className="btn btn-primary btn-sm" disabled={!changed || save.isPending} onClick={() => save.mutate(value, { onSuccess: () => setDraft(null) })}>
            {P.save}
          </button>
          {save.isSuccess && !changed && (
            <span className="muted small" role="status">
              {P.saved}
            </span>
          )}
        </div>
      )}
      {save.error && <p className="form-error">{save.error.message}</p>}
    </section>
  );
}

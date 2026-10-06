import { useState } from "react";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { EmptyState } from "../../components/EmptyState";
import { Modal } from "../../components/Modal";
import { StatusBadge } from "../../components/StatusBadge";
import { useLinkParent, useStudentParents, useUnlinkParent } from "../../lib/parent";

const AREA_LABELS = { fees: "fees", attendance: "attendance", results: "marks and results" } as const;

/** Office: the parents linked to a student, and linking a new one (found or created by mobile number). */
export function ParentsTab({ studentId, canManage }: { studentId: string; canManage: boolean }) {
  const parents = useStudentParents(studentId);
  const unlink = useUnlinkParent(studentId);
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<{ id: string; name: string } | null>(null);
  const d = parents.data;
  if (parents.error) return <p className="form-error">{parents.error.message}</p>;
  if (!d) return <p className="muted">Loading…</p>;
  const hidden = (Object.keys(AREA_LABELS) as (keyof typeof AREA_LABELS)[]).filter((a) => !d.access[a]);
  return (
    <>
      <p className="muted small">
        Parents sign in with their mobile number and a code sent to their email (or a password they set with “Forgot password”). They see this
        student's pages read-only.{" "}
        {d.minor
          ? `The student is under 18: parents see everything${d.consent_recorded ? " (parental consent recorded)" : "; record the parent's consent when linking"}.`
          : hidden.length
            ? `The student has chosen not to share: ${hidden.map((a) => AREA_LABELS[a]).join(", ")}.`
            : "The student shares fees, attendance and results."}
      </p>
      {canManage && (
        <div className="row-actions">
          <button type="button" className="btn btn-primary btn-sm" onClick={() => setAdding(true)}>
            Link a parent
          </button>
        </div>
      )}
      {d.parents.length === 0 ? (
        <EmptyState title="No parent linked" />
      ) : (
        <div className="request-list">
          {d.parents.map((p) => (
            <section key={p.id} className="card request-card">
              <div className="request-head">
                <b>
                  {p.name}
                  {p.relation ? ` · ${p.relation}` : ""}
                </b>
                {p.status !== "active" && <StatusBadge tone="neutral">Disabled</StatusBadge>}
              </div>
              <p className="small">
                {p.phone}
                {p.email ? ` · ${p.email}` : " · no email (can't get a sign-in code yet)"}
                {p.children > 1 ? ` · ${p.children} children at the college` : ""}
              </p>
              <p className="muted small">{p.last_login_at ? `Last signed in ${new Date(p.last_login_at).toLocaleString("en-IN")}` : "Has not signed in yet"}</p>
              {canManage && (
                <div className="row-actions">
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => setRemoving({ id: p.id, name: p.name })}>
                    Unlink
                  </button>
                </div>
              )}
            </section>
          ))}
        </div>
      )}
      {adding && <LinkModal studentId={studentId} minor={d.minor && !d.consent_recorded} onClose={() => setAdding(false)} />}
      <ConfirmDialog
        open={removing !== null}
        title={`Unlink ${removing?.name ?? ""}?`}
        message="They will no longer see this student. If this was their only child at the college, their account is closed."
        confirmLabel="Unlink"
        danger
        onCancel={() => setRemoving(null)}
        onConfirm={() => removing && unlink.mutate(removing.id, { onSuccess: () => setRemoving(null) })}
      />
    </>
  );
}

function LinkModal({ studentId, minor, onClose }: { studentId: string; minor: boolean; onClose: () => void }) {
  const link = useLinkParent(studentId);
  const [form, setForm] = useState({ name: "", phone: "", email: "", relation: "Father", consent: false });
  return (
    <Modal open title="Link a parent" onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          link.mutate({ ...form, email: form.email.trim() || undefined }, { onSuccess: onClose });
        }}
      >
        <p className="muted small">If this mobile number already has a parent account (a brother or sister studies here), the same account is linked.</p>
        <div className="field">
          <label htmlFor="pl-name">Name</label>
          <input id="pl-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
        </div>
        <div className="field">
          <label htmlFor="pl-phone">Mobile number</label>
          <input id="pl-phone" type="tel" inputMode="numeric" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} required />
        </div>
        <div className="field">
          <label htmlFor="pl-email">Email (sign-in codes are sent here)</label>
          <input id="pl-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor="pl-rel">Relation</label>
          <select id="pl-rel" value={form.relation} onChange={(e) => setForm({ ...form, relation: e.target.value })}>
            {["Father", "Mother", "Guardian"].map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        </div>
        {minor && (
          <label className="check-label">
            <input type="checkbox" checked={form.consent} onChange={(e) => setForm({ ...form, consent: e.target.checked })} />
            The student is under 18: the parent's consent is recorded (signed form on file)
          </label>
        )}
        {link.error && <p className="form-error">{link.error.message}</p>}
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={link.isPending || (minor && !form.consent)}>
            Link parent
          </button>
        </div>
      </form>
    </Modal>
  );
}

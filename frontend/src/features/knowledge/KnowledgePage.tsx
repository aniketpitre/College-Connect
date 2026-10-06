import { useState } from "react";
import { Link } from "react-router";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { StatusBadge } from "../../components/StatusBadge";
import { useAddDocument, useKnowledge, useReindex, useRemoveDocument, type KbDocument } from "../../lib/knowledge";
import { Gaps } from "./Gaps";
import "../campus/campus.css";

const OFFICES: Record<string, string> = {
  admissions: "Admissions",
  fees: "Fees & Accounts",
  examinations: "Examinations",
  placements: "Placements",
  hostel: "Hostel & Campus",
  notices: "Notices",
};
const AUDIENCE: Record<KbDocument["audience"], string> = {
  public: "Public help desk",
  everyone: "Signed-in members",
  students: "All students",
  staff: "Staff",
  class: "A class",
};
const SOURCE: Record<KbDocument["source"], string> = { bundled: "Built in", upload: "Uploaded", text: "Typed", notice: "Notice" };

/** Office / System Admin (English): the documents the help desk answers from. */
export default function KnowledgePage() {
  const kb = useKnowledge();
  const add = useAddDocument();
  const remove = useRemoveDocument();
  const reindex = useReindex();
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("notices");
  const [audience, setAudience] = useState("public");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [formKey, setFormKey] = useState(0);
  const [removing, setRemoving] = useState<KbDocument | null>(null);
  const s = kb.data?.status;
  const docs = kb.data?.documents ?? [];
  const notices = docs.filter((d) => d.source === "notice");
  const others = docs.filter((d) => d.source !== "notice");

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">CollegeConnect AI</div>
          <h1>Help desk documents</h1>
        </div>
        <span className="row-actions">
          <Link className="btn btn-ghost" to="/app/analytics">
            Questions asked
          </Link>
          <button type="button" className="btn btn-ghost" disabled={reindex.isPending} onClick={() => reindex.mutate()}>
            {reindex.isPending ? "Re-indexing…" : "Re-index"}
          </button>
        </span>
      </div>
      <p className="small muted">
        The help desk answers only from these documents and from published notices, and shows the source. Notices are added automatically for their own audience
        and drop out when they expire.
      </p>
      {kb.error && <p className="form-error">{kb.error.message}</p>}
      {s && (
        <p className="small" role="status">
          {docs.length} documents · {s.chunks_total} sections · search by {s.retrieval === "vector" ? "meaning (embeddings)" : "keywords"} · answers{" "}
          {s.generation === "extractive" ? "quote the document (no AI key set)" : "written by AI from the documents"}
          {s.embeddings_configured && s.chunks_embedded < s.chunks_total && ` · ${s.chunks_total - s.chunks_embedded} sections wait for Re-index`}
        </p>
      )}
      {reindex.data && (
        <p className="auth-success" role="status">
          Re-indexed: {reindex.data.notices} notices, {reindex.data.embedded} sections embedded
          {reindex.data.remaining ? `, ${reindex.data.remaining} left (run again)` : ""}.
        </p>
      )}

      <Gaps />

      <form
        key={formKey}
        className="card"
        onSubmit={(e) => {
          e.preventDefault();
          add.mutate(
            { title, category, audience, text, file },
            {
              onSuccess: () => {
                setTitle("");
                setText("");
                setFile(null);
                setFormKey((k) => k + 1);
              },
            },
          );
        }}
      >
        <h2 className="card-title">Add a document</h2>
        {add.error && <p className="form-error">{add.error.message}</p>}
        <div className="campus-form">
          <div className="field">
            <label htmlFor="kb-title">Title</label>
            <input id="kb-title" value={title} onChange={(e) => setTitle(e.target.value)} required minLength={3} placeholder="e.g. Fee Structure 2026-27" />
          </div>
          <div className="field">
            <label htmlFor="kb-cat">Office</label>
            <select id="kb-cat" value={category} onChange={(e) => setCategory(e.target.value)}>
              {(kb.data?.categories ?? Object.keys(OFFICES)).map((c) => (
                <option key={c} value={c}>
                  {OFFICES[c] ?? c}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="kb-aud">Who gets answers from it</label>
            <select id="kb-aud" value={audience} onChange={(e) => setAudience(e.target.value)}>
              <option value="public">Anyone (public help desk too)</option>
              <option value="everyone">Signed-in students, parents and staff only</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="kb-file">File: PDF with text, .md or .txt</label>
            <input
              id="kb-file"
              type="file"
              accept=".pdf,.md,.txt,application/pdf,text/plain,text/markdown"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>
        </div>
        {!file && (
          <div className="field">
            <label htmlFor="kb-text">…or type the text (start sections with "## Heading" for clearer sources)</label>
            <textarea id="kb-text" rows={6} value={text} onChange={(e) => setText(e.target.value)} />
          </div>
        )}
        <button type="submit" className="btn btn-primary" disabled={add.isPending}>
          {add.isPending ? "Adding…" : "Add to the help desk"}
        </button>
      </form>

      <section className="card">
        <h2 className="card-title">Documents</h2>
        <DocList docs={others} onRemove={setRemoving} />
      </section>
      <section className="card">
        <h2 className="card-title">Notices in the help desk</h2>
        <p className="small muted">Withdraw a notice or change its expiry on the notice itself.</p>
        <DocList docs={notices} />
      </section>
      <ConfirmDialog
        open={removing !== null}
        title="Remove this document?"
        message="The help desk stops answering from it at once. Add it again to bring it back."
        confirmLabel="Remove"
        danger
        onCancel={() => setRemoving(null)}
        onConfirm={() => {
          if (removing) remove.mutate(removing.id);
          setRemoving(null);
        }}
      />
    </>
  );
}

function DocList({ docs, onRemove }: { docs: KbDocument[]; onRemove?: (d: KbDocument) => void }) {
  if (docs.length === 0) return <p className="small muted">None.</p>;
  return (
    <ul className="campus-list">
      {docs.map((d) => (
        <li key={d.id}>
          <div>
            <b>{d.notice_id ? <Link to={`/app/notices/${d.notice_id}`}>{d.title}</Link> : d.title}</b>
            <div className="small muted">
              {OFFICES[d.category] ?? d.category} · {d.document} · {d.chunks} sections · {SOURCE[d.source]}
              {d.created_by ? ` by ${d.created_by}` : ""} · {new Date(d.created_at).toLocaleDateString("en-IN")}
            </div>
          </div>
          <span className="row-actions">
            <StatusBadge tone={d.audience === "public" ? "success" : "info"}>{AUDIENCE[d.audience]}</StatusBadge>
            {onRemove && (
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => onRemove(d)}>
                Remove
              </button>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

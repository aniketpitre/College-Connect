import { useState } from "react";
import { EmptyState } from "../../components/EmptyState";
import { StatusBadge } from "../../components/StatusBadge";
import { STUDENT_STRINGS } from "../../i18n/student";
import type { Language } from "../../lib/types";
import { fileUrl, useUpload, type StudentDocument } from "../../lib/students";

const TONE = { pending: "warning", verified: "success", rejected: "danger" } as const;

export function DocumentList({ docs, lang, actions }: { docs: StudentDocument[]; lang: Language; actions?: (d: StudentDocument) => React.ReactNode }) {
  const T = STUDENT_STRINGS[lang];
  if (!docs.length) return <EmptyState title={T.noDocuments} />;
  return (
    <ul className="doc-list">
      {docs.map((d) => (
        <li key={d.id}>
          <div>
            <div className="doc-name">
              {T.docTypes[d.type] ?? d.type} <StatusBadge tone={TONE[d.status]}>{T.docStatus[d.status]}</StatusBadge>
            </div>
            <div className="muted doc-meta">
              {d.filename} · {new Date(d.uploaded_at).toLocaleDateString(lang === "en" ? "en-IN" : `${lang}-IN`)}
            </div>
            {d.reason && (
              <div className="doc-reason">
                {T.officeNote}: {d.reason}
              </div>
            )}
          </div>
          <div className="row-actions">
            <a className="link-btn" href={fileUrl(d.url)} target="_blank" rel="noreferrer">
              {T.view}
            </a>
            {actions?.(d)}
          </div>
        </li>
      ))}
    </ul>
  );
}

/** Choose a document type and a file; `base` is `/students/<id>` (office) or `/me/student` (student). */
export function UploadDocument({ base, lang }: { base: string; lang: Language }) {
  const T = STUDENT_STRINGS[lang];
  const upload = useUpload(base);
  const [type, setType] = useState("hsc_marksheet");
  const [file, setFile] = useState<File | null>(null);
  const [key, setKey] = useState(0);
  return (
    <form
      className="card upload-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (file)
          upload.mutate(
            { kind: "documents", file, type },
            {
              onSuccess: () => {
                setFile(null);
                setKey((k) => k + 1);
              },
            },
          );
      }}
    >
      <h3>{T.uploadDocument}</h3>
      <div className="field-row">
        <div className="field">
          <label htmlFor="doc-type">{T.documentType}</label>
          <select id="doc-type" value={type} onChange={(e) => setType(e.target.value)}>
            {Object.entries(T.docTypes).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="doc-file">{T.chooseFile}</label>
          <input key={key} id="doc-file" type="file" accept="application/pdf,image/jpeg,image/png" onChange={(e) => setFile(e.target.files?.[0] ?? null)} required />
        </div>
      </div>
      {upload.error && <div className="form-error">{upload.error.message}</div>}
      <div className="modal-actions">
        <button type="submit" className="btn btn-primary" disabled={!file || upload.isPending}>
          {upload.isPending ? T.uploading : T.upload}
        </button>
      </div>
    </form>
  );
}

import { useState } from "react";
import { Link, useParams } from "react-router";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { Modal } from "../../components/Modal";
import { StatusBadge } from "../../components/StatusBadge";
import { STUDENT_STRINGS } from "../../i18n/student";
import { hasPermission, useMe } from "../../lib/auth";
import { useSetup } from "../../lib/setup";
import { fileUrl, useDecideDocument, useStudent, useStudentHistory, useUpdateStudent, useUpload, type Student } from "../../lib/students";
import { ChangeRequestList } from "./ChangeRequestList";
import { describeValue } from "./describe";
import { DocumentList, UploadDocument } from "./Documents";
import { RecordView } from "./RecordView";
import { StudentFields } from "./StudentForm";
import { toBody, toValues } from "./studentValues";
import "./students.css";

const L = STUDENT_STRINGS.en;

const ACTIONS: Record<string, string> = {
  "students.created": "Record created",
  "students.updated": "Record updated",
  "students.change_requested": "Student asked for a correction",
  "students.change_approved": "Correction approved",
  "students.change_rejected": "Correction rejected",
  "students.photo_changed": "Photo changed",
  "students.document_added": "Document uploaded",
  "students.document_verified": "Document verified",
  "students.document_rejected": "Document rejected",
  "students.imported": "Imported from a file",
  "students.promoted": "Promoted",
  "students.contact_confirmed": "Student confirmed contact details",
  "students.privacy_accepted": "Student accepted the privacy notice",
};

/** Office screen (English): one student's record, documents, corrections and history. */
export default function StudentDetailPage() {
  const { id = "" } = useParams();
  const { data: me } = useMe();
  const student = useStudent(id);
  const setup = useSetup();
  const [editing, setEditing] = useState(false);
  const [tab, setTab] = useState<"record" | "documents" | "requests" | "history">("record");
  const canManage = hasPermission(me, "students.manage");
  const s = student.data;

  if (student.error) return <p className="form-error">{student.error.message}</p>;
  if (!s) return <p className="muted">Loading…</p>;
  const pendingDocs = s.documents.filter((d) => d.status === "pending").length;

  return (
    <>
      <Link to="/app/students" className="back-link">
        ← Students
      </Link>
      <div className="student-head">
        <Photo student={s} canChange={canManage} />
        <div className="student-head-text">
          <h1>{s.name}</h1>
          <div className="muted">
            PRN {s.prn} · {[s.programme_code, s.year_label, s.division].filter(Boolean).join(" · ")}
            {s.roll_no ? ` · Roll ${s.roll_no}` : ""}
          </div>
          <div className="badge-row">
            <StatusBadge tone={s.status === "active" ? "success" : "neutral"}>{L.studentStatus[s.status]}</StatusBadge>
            {pendingDocs > 0 && <StatusBadge tone="warning">{pendingDocs} document(s) to check</StatusBadge>}
          </div>
        </div>
        {canManage && (
          <button type="button" className="btn btn-primary" onClick={() => setEditing(true)} disabled={!setup.data}>
            Edit record
          </button>
        )}
      </div>

      <div className="tabs" role="tablist">
        {(
          [
            ["record", "Record"],
            ["documents", `Documents (${s.documents.length})`],
            ["requests", "Correction requests"],
            ["history", "History"],
          ] as const
        ).map(([key, label]) => (
          <button key={key} type="button" role="tab" aria-selected={tab === key} className={tab === key ? "active" : ""} onClick={() => setTab(key)}>
            {label}
          </button>
        ))}
      </div>

      {tab === "record" && <RecordView s={s} />}
      {tab === "documents" && <DocumentsTab s={s} canManage={canManage} />}
      {tab === "requests" && (
        <>
          <ChangeRequestList status="pending" studentId={s.id} canDecide={canManage} />
          <h2 className="subhead">Decided</h2>
          <ChangeRequestList status="approved" studentId={s.id} canDecide={false} />
          <ChangeRequestList status="rejected" studentId={s.id} canDecide={false} />
        </>
      )}
      {tab === "history" && <HistoryTab id={s.id} />}

      {editing && setup.data && <EditModal s={s} onClose={() => setEditing(false)} />}
    </>
  );
}

function Photo({ student, canChange }: { student: Student; canChange: boolean }) {
  const upload = useUpload(`/students/${student.id}`);
  return (
    <div className="photo-box">
      {student.photo_url ? <img src={fileUrl(student.photo_url)} alt={`Photo of ${student.name}`} /> : <span className="photo-empty">{student.name.slice(0, 1)}</span>}
      {canChange && (
        <label className="photo-change">
          {upload.isPending ? "…" : "Change"}
          <input type="file" accept="image/jpeg,image/png" hidden onChange={(e) => e.target.files?.[0] && upload.mutate({ kind: "photo", file: e.target.files[0] })} />
        </label>
      )}
      {upload.error && <span className="field-error">{upload.error.message}</span>}
    </div>
  );
}

function DocumentsTab({ s, canManage }: { s: Student; canManage: boolean }) {
  const decide = useDecideDocument(s.id);
  const [rejecting, setRejecting] = useState<string | null>(null);
  return (
    <>
      <DocumentList
        docs={s.documents}
        lang="en"
        actions={(d) =>
          canManage && d.status !== "verified" ? (
            <>
              <button type="button" className="link-btn" onClick={() => setRejecting(d.id)} disabled={d.status === "rejected"}>
                Reject
              </button>
              <button type="button" className="link-btn" onClick={() => decide.mutate({ docId: d.id, verified: true })}>
                Verify
              </button>
            </>
          ) : null
        }
      />
      {canManage && <UploadDocument base={`/students/${s.id}`} lang="en" />}
      <ConfirmDialog
        open={rejecting !== null}
        title="Reject this document?"
        message="The student sees your reason and can upload a better copy."
        confirmLabel="Reject"
        requireReason
        onCancel={() => setRejecting(null)}
        onConfirm={(reason) => {
          decide.mutate({ docId: rejecting!, verified: false, reason });
          setRejecting(null);
        }}
      />
    </>
  );
}

function HistoryTab({ id }: { id: string }) {
  const history = useStudentHistory(id);
  const setup = useSetup();
  return (
    <ul className="history-list">
      {(history.data ?? []).map((h, i) => (
        <li key={`${h.at}-${i}`}>
          <div className="history-head">
            <b>{ACTIONS[h.action] ?? h.action}</b>
            <span className="muted">
              {new Date(h.at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
              {h.by ? ` · ${h.by}` : ""}
            </span>
          </div>
          {h.reason && <div className="muted">Reason: {h.reason}</div>}
          {h.details?.before && h.details.after && (
            <ul className="history-changes">
              {Object.keys(h.details.after).map((k) => (
                <li key={k}>
                  {L.fields[k] ?? L.sections[k as keyof typeof L.sections] ?? k}: <s>{describeValue(k, h.details!.before![k], setup.data)}</s> → {describeValue(k, h.details!.after![k], setup.data)}
                </li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ul>
  );
}

function EditModal({ s, onClose }: { s: Student; onClose: () => void }) {
  const setup = useSetup();
  const [initial] = useState(() => toValues(s));
  const [values, setValues] = useState(initial);
  const [reason, setReason] = useState("");
  const update = useUpdateStudent(s.id);
  const statusChanged = values.status !== initial.status;
  return (
    <Modal open title={`Edit ${s.name}`} onClose={onClose} wide>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          update.mutate({ ...toBody(values, initial), reason: reason.trim() || undefined }, { onSuccess: onClose });
        }}
      >
        <StudentFields setup={setup.data!} values={values} onChange={setValues} error={update.error} isNew={false} />
        <div className="field">
          <label htmlFor="edit-reason">Reason {statusChanged ? "(required for a status change)" : "(optional)"}: recorded in the history</label>
          <input id="edit-reason" value={reason} onChange={(e) => setReason(e.target.value)} required={statusChanged} />
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={update.isPending}>
            {update.isPending ? "Saving…" : "Save changes"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

import { useState } from "react";
import { useNavigate } from "react-router";
import { Modal } from "../../components/Modal";
import { ApiError } from "../../lib/api";
import { useCreateNotice } from "../../lib/notices";
import { useSetup } from "../../lib/setup";

/** Staff form (English): a new notice, with optional Hindi/Marathi versions and a PDF. */
export function NoticeForm({ onClose }: { onClose: () => void }) {
  const setup = useSetup();
  const create = useCreateNotice();
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [hi, setHi] = useState({ title: "", body: "" });
  const [mr, setMr] = useState({ title: "", body: "" });
  const [showTranslations, setShowTranslations] = useState(false);
  const [kind, setKind] = useState("students");
  const [programmeId, setProgrammeId] = useState("");
  const [year, setYear] = useState("");
  const [divisionId, setDivisionId] = useState("");
  const [publishAt, setPublishAt] = useState("");
  const [expires, setExpires] = useState("");
  const [pinned, setPinned] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const err = create.error instanceof ApiError ? create.error : null;
  const programme = setup.data?.programmes.find((p) => p.id === programmeId);
  const divisions = setup.data?.divisions.filter((d) => d.programme_id === programmeId && String(d.year_of_study) === year && d.status === "active") ?? [];

  return (
    <Modal open title="New notice" onClose={onClose} wide>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate(
            {
              body: {
                title,
                body,
                hi: showTranslations ? hi : null,
                mr: showTranslations ? mr : null,
                audience: { kind, programme_id: programmeId || null, year_of_study: year ? Number(year) : null, division_id: divisionId || null },
                publish_at: publishAt ? new Date(publishAt).toISOString() : null,
                expires_on: expires || null,
                pinned,
              },
              file,
            },
            { onSuccess: (n) => navigate(`/app/notices/${n.id}`) },
          );
        }}
      >
        {err && <div className="form-error">{err.message}</div>}
        <div className="field">
          <label htmlFor="n-title">Title</label>
          <input id="n-title" value={title} onChange={(e) => setTitle(e.target.value)} required minLength={3} />
        </div>
        <div className="field">
          <label htmlFor="n-body">Text</label>
          <textarea id="n-body" rows={6} value={body} onChange={(e) => setBody(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="n-file">PDF (optional)</label>
          <input id="n-file" type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </div>
        <button type="button" className="link-btn" onClick={() => setShowTranslations(!showTranslations)}>
          {showTranslations ? "− Hide" : "+ Add"} Hindi / Marathi versions
        </button>
        {showTranslations && (
          <div className="field-row translations">
            <div>
              <div className="field">
                <label htmlFor="n-hi-title">Title in Hindi</label>
                <input id="n-hi-title" lang="hi" value={hi.title} onChange={(e) => setHi({ ...hi, title: e.target.value })} />
              </div>
              <div className="field">
                <label htmlFor="n-hi-body">Text in Hindi</label>
                <textarea id="n-hi-body" lang="hi" rows={4} value={hi.body} onChange={(e) => setHi({ ...hi, body: e.target.value })} />
              </div>
            </div>
            <div>
              <div className="field">
                <label htmlFor="n-mr-title">Title in Marathi</label>
                <input id="n-mr-title" lang="mr" value={mr.title} onChange={(e) => setMr({ ...mr, title: e.target.value })} />
              </div>
              <div className="field">
                <label htmlFor="n-mr-body">Text in Marathi</label>
                <textarea id="n-mr-body" lang="mr" rows={4} value={mr.body} onChange={(e) => setMr({ ...mr, body: e.target.value })} />
              </div>
            </div>
          </div>
        )}
        <h3 className="form-section">Who sees it</h3>
        <div className="field-row">
          <div className="field">
            <label htmlFor="n-aud">Audience</label>
            <select id="n-aud" value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="everyone">Everyone (students and staff)</option>
              <option value="students">All students</option>
              <option value="class">A class</option>
              <option value="staff">Staff only</option>
            </select>
          </div>
          {kind === "class" && (
            <>
              <div className="field">
                <label htmlFor="n-prog">Programme</label>
                <select id="n-prog" value={programmeId} onChange={(e) => (setProgrammeId(e.target.value), setYear(""), setDivisionId(""))} required>
                  <option value="">Choose…</option>
                  {setup.data?.programmes.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.code}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="n-year">Year</label>
                <select id="n-year" value={year} onChange={(e) => (setYear(e.target.value), setDivisionId(""))}>
                  <option value="">All years</option>
                  {programme?.year_labels.map((l, i) => (
                    <option key={l} value={i + 1}>
                      {l}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="n-div">Division</label>
                <select id="n-div" value={divisionId} onChange={(e) => setDivisionId(e.target.value)} disabled={!year}>
                  <option value="">All divisions</option>
                  {divisions.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </div>
            </>
          )}
        </div>
        <div className="field-row">
          <div className="field">
            <label htmlFor="n-pub">Show from (empty: now)</label>
            <input id="n-pub" type="datetime-local" value={publishAt} onChange={(e) => setPublishAt(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="n-exp">Show until (optional)</label>
            <input id="n-exp" type="date" value={expires} onChange={(e) => setExpires(e.target.value)} />
          </div>
        </div>
        <label className="check-label">
          <input type="checkbox" checked={pinned} onChange={(e) => setPinned(e.target.checked)} /> Pin to the top
        </label>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={create.isPending}>
            {create.isPending ? "Publishing…" : "Publish"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

import { useState } from "react";
import LanguageToggle from "../../app/LanguageToggle";
import { EmptyState } from "../../components/EmptyState";
import { StatusBadge } from "../../components/StatusBadge";
import { CAMPUS_STRINGS } from "../../i18n/campus";
import { API_V1 } from "../../lib/api";
import { hasPermission, useMe } from "../../lib/auth";
import { useDriveResults, useDrives, useMyPlacement, usePlacementMine, usePlacementStats, useRegistrations, useSaveDrive, type Drive } from "../../lib/campus";
import { useLanguage } from "../../lib/language";
import { useSetup } from "../../lib/setup";
import "./campus.css";

export default function PlacementPage() {
  const { data: me } = useMe();
  return me?.kind === "student" ? <MyPlacement /> : <PlacementCell canManage={hasPermission(me, "placement.manage")} />;
}

function MyPlacement() {
  const [language, setLanguage] = useLanguage();
  const t = CAMPUS_STRINGS[language].placement;
  const mine = useMyPlacement();
  const act = usePlacementMine();
  const [draft, setDraft] = useState<{ skills: string; linkedin: string } | null>(null);
  const m = mine.data;
  if (!m) return null;
  const profile = draft ?? { skills: m.profile.skills, linkedin: m.profile.linkedin };
  const locale = language === "en" ? "en-IN" : `${language}-IN`;
  const day = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(locale, { day: "numeric", month: "short" });
  return (
    <div lang={language}>
      <div className="page-head">
        <h1>{t.title}</h1>
        <LanguageToggle value={language} onChange={setLanguage} />
      </div>
      <p className="muted">{t.standing(m.cgpa == null ? "–" : String(m.cgpa), m.backlogs)}</p>
      {act.error && <p className="form-error">{act.error.message}</p>}
      <h2 className="subhead">{t.profile}</h2>
      <form
        className="card campus-form"
        onSubmit={(e) => {
          e.preventDefault();
          act.mutate({ path: "/profile", method: "PUT", body: profile }, { onSuccess: () => setDraft(null) });
        }}
      >
        <div className="field">
          <label htmlFor="pl-skills">{t.skills}</label>
          <input id="pl-skills" value={profile.skills} onChange={(e) => setDraft({ ...profile, skills: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor="pl-li">{t.linkedin}</label>
          <input id="pl-li" value={profile.linkedin} onChange={(e) => setDraft({ ...profile, linkedin: e.target.value })} />
        </div>
        <div>
          <button type="submit" className="btn btn-ghost btn-sm" disabled={!draft || act.isPending}>
            {t.save}
          </button>
        </div>
        <div className="field">
          <span className="small">
            <b>{t.resume}:</b>{" "}
            {m.profile.resume_url ? (
              <a href={`${API_V1}${m.profile.resume_url}`} target="_blank" rel="noreferrer">
                {m.profile.resume_name}
              </a>
            ) : (
              t.noResume
            )}
          </span>
          <label className="btn btn-ghost btn-sm file-button" htmlFor="pl-cv">
            {t.uploadResume}
            <input
              id="pl-cv"
              type="file"
              accept=".pdf"
              aria-label={t.uploadResume}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                const form = new FormData();
                form.append("file", file);
                act.mutate({ path: "/resume", body: form });
                e.target.value = "";
              }}
            />
          </label>
        </div>
      </form>
      <h2 className="subhead">{t.drives}</h2>
      {m.drives.length === 0 && <p className="muted">{t.noDrives}</p>}
      <div className="request-list">
        {m.drives.map((d) => (
          <section key={d.id} className="card request-card">
            <div className="request-head">
              <b>
                {d.company} · {d.role}
              </b>
              {d.registration ? (
                <StatusBadge tone={d.registration.status === "selected" ? "success" : d.registration.status === "rejected" ? "danger" : "info"}>{d.registration.stage}</StatusBadge>
              ) : (
                <StatusBadge tone={d.eligible ? "success" : "neutral"}>{d.eligible ? t.eligible : t.notEligible}</StatusBadge>
              )}
            </div>
            <p className="small">
              {t.package(d.ctc_lpa)}
              {d.location && ` · ${d.location}`} · {t.registerBy(day(d.register_by))}
              {!d.eligible && !d.registration && ` · ${t.notEligible} ${d.reasons?.map((r) => t.reasons[r]).join(", ")}`}
            </p>
            {d.description && <p className="muted small">{d.description}</p>}
            {d.registration?.offer_lpa != null && <p className="small">{t.offer(d.registration.offer_lpa)}</p>}
            <div className="row-actions">
              {!d.registration && d.eligible && d.open_now && (
                <button type="button" className="btn btn-primary btn-sm" disabled={act.isPending} onClick={() => act.mutate({ path: `/drives/${d.id}/register` })}>
                  {t.register}
                </button>
              )}
              {d.registration?.status === "registered" && (
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => act.mutate({ path: `/drives/${d.id}/withdraw` })}>
                  {t.withdraw}
                </button>
              )}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

function PlacementCell({ canManage }: { canManage: boolean }) {
  const drives = useDrives();
  const stats = usePlacementStats();
  const [open, setOpen] = useState<string>("");
  const [editing, setEditing] = useState<Drive | "new" | null>(null);
  const s = stats.data;
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Placement</div>
          <h1>Placement cell</h1>
        </div>
        {canManage && (
          <button type="button" className="btn btn-primary" onClick={() => setEditing("new")}>
            New drive
          </button>
        )}
      </div>
      {s && (
        <div className="tiles fee-tiles">
          {(
            [
              ["Companies", s.companies],
              ["Offers", s.offers],
              ["Students placed", s.students_placed],
              ["Highest (LPA)", s.highest_lpa ?? "–"],
              ["Median (LPA)", s.median_lpa ?? "–"],
            ] as const
          ).map(([label, n]) => (
            <div className="tile" key={label}>
              <div className="tile-label">{label}</div>
              <div className="tile-value">{n}</div>
            </div>
          ))}
        </div>
      )}
      {editing && <DriveForm drive={editing === "new" ? null : editing} onDone={() => setEditing(null)} />}
      {drives.data?.length === 0 && <EmptyState title="No drives yet" />}
      <div className="request-list">
        {drives.data?.map((d) => (
          <section key={d.id} className="card request-card">
            <div className="request-head">
              <b>
                {d.company} · {d.role} · {d.ctc_lpa} LPA
              </b>
              <StatusBadge tone={d.open_now ? "success" : "neutral"}>{d.open_now ? "Open" : d.status}</StatusBadge>
            </div>
            <p className="small">
              Register by {d.register_by} · {d.eligibility.programmes.join(", ") || "all programmes"}
              {d.eligibility.min_cgpa != null && ` · CGPA ≥ ${d.eligibility.min_cgpa}`}
              {d.eligibility.max_backlogs != null && ` · backlogs ≤ ${d.eligibility.max_backlogs}`} · rounds: {d.rounds.join(" → ")}
            </p>
            <p className="muted small">
              {d.counts && Object.entries(d.counts).filter(([, n]) => n).map(([k, n]) => `${n} ${k.replace("_", " ")}`).join(" · ")}
            </p>
            <div className="row-actions">
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setOpen(open === d.id ? "" : d.id)}>
                {open === d.id ? "Hide students" : "Students"}
              </button>
              {canManage && (
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditing(d)}>
                  Edit
                </button>
              )}
            </div>
            {open === d.id && <Registrants driveId={d.id} canManage={canManage} />}
          </section>
        ))}
      </div>
    </>
  );
}

function Registrants({ driveId, canManage }: { driveId: string; canManage: boolean }) {
  const regs = useRegistrations(driveId);
  const results = useDriveResults(driveId);
  const [picked, setPicked] = useState<string[]>([]);
  const rows = regs.data?.registrations ?? [];
  const act = (action: string) => results.mutate({ registration_ids: picked, action }, { onSuccess: () => setPicked([]) });
  return (
    <>
      {results.error && <p className="form-error">{results.error.message}</p>}
      {rows.length === 0 ? (
        <p className="muted small">No registrations yet.</p>
      ) : (
        <div className="data-table data-table-scroll">
          <table>
            <thead>
              <tr>
                <th />
                <th>Student</th>
                <th>Class</th>
                <th className="num">CGPA</th>
                <th className="num">Backlogs</th>
                <th>Stage</th>
                <th>Resume</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>
                    {canManage && ["registered", "in_process"].includes(r.status) && (
                      <input
                        type="checkbox"
                        aria-label={`Pick ${r.name}`}
                        checked={picked.includes(r.id)}
                        onChange={(e) => setPicked(e.target.checked ? [...picked, r.id] : picked.filter((x) => x !== r.id))}
                      />
                    )}
                  </td>
                  <td>
                    {r.name}
                    <div className="muted small">{r.prn}</div>
                  </td>
                  <td>{r.class}</td>
                  <td className="num">{r.cgpa ?? "–"}</td>
                  <td className="num">{r.backlogs}</td>
                  <td>
                    {r.stage}
                    {r.offer_lpa != null && ` · ${r.offer_lpa} LPA`}
                  </td>
                  <td>
                    {r.has_resume && canManage && (
                      <a href={`${API_V1}/placement/registrations/${r.id}/resume`} target="_blank" rel="noreferrer">
                        PDF
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {canManage && (
        <div className="row-actions">
          <a className="btn btn-ghost btn-sm" href={`${API_V1}/placement/drives/${driveId}/registrations.csv`}>
            Download list (CSV)
          </a>
          <button type="button" className="btn btn-ghost btn-sm" disabled={!picked.length} onClick={() => act("next")}>
            Next round
          </button>
          <button type="button" className="btn btn-ghost btn-sm" disabled={!picked.length} onClick={() => act("reject")}>
            Not selected
          </button>
          <button type="button" className="btn btn-primary btn-sm" disabled={!picked.length} onClick={() => act("select")}>
            Selected (offer)
          </button>
        </div>
      )}
    </>
  );
}

function DriveForm({ drive, onDone }: { drive: Drive | null; onDone: () => void }) {
  const setup = useSetup();
  const save = useSaveDrive();
  const [f, setF] = useState({
    company: drive?.company ?? "",
    role: drive?.role ?? "",
    ctc_lpa: String(drive?.ctc_lpa ?? ""),
    location: drive?.location ?? "",
    description: drive?.description ?? "",
    register_by: drive?.register_by ?? "",
    rounds: (drive?.rounds ?? ["Aptitude test", "Interview"]).join(", "),
    programme_id: drive?.eligibility.programme_ids[0] ?? "",
    years: (drive?.eligibility.years ?? [3]).join(","),
    min_cgpa: drive?.eligibility.min_cgpa != null ? String(drive.eligibility.min_cgpa) : "",
    max_backlogs: drive?.eligibility.max_backlogs != null ? String(drive.eligibility.max_backlogs) : "",
    status: drive?.status ?? "open",
  });
  return (
    <form
      className="card"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate(
          {
            id: drive?.id,
            body: {
              company: f.company,
              role: f.role,
              ctc_lpa: Number(f.ctc_lpa),
              location: f.location,
              description: f.description,
              register_by: f.register_by,
              rounds: f.rounds.split(",").map((r) => r.trim()).filter(Boolean),
              status: f.status,
              eligibility: {
                programme_ids: f.programme_id ? [f.programme_id] : [],
                years: f.years.split(",").map((y) => Number(y.trim())).filter(Boolean),
                min_cgpa: f.min_cgpa ? Number(f.min_cgpa) : null,
                max_backlogs: f.max_backlogs ? Number(f.max_backlogs) : null,
              },
            },
          },
          { onSuccess: onDone },
        );
      }}
    >
      <h2 className="card-title">{drive ? "Edit drive" : "New drive"}</h2>
      <div className="campus-form">
        {(
          [
            ["company", "Company"],
            ["role", "Role"],
            ["ctc_lpa", "Package (lakh a year)"],
            ["location", "Location"],
            ["rounds", "Rounds (comma-separated)"],
            ["years", "Years of study (e.g. 3)"],
            ["min_cgpa", "Minimum CGPA"],
            ["max_backlogs", "Most backlogs allowed"],
          ] as const
        ).map(([k, label]) => (
          <div className="field" key={k}>
            <label htmlFor={`dr-${k}`}>{label}</label>
            <input id={`dr-${k}`} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} required={k === "company" || k === "role" || k === "ctc_lpa"} />
          </div>
        ))}
        <div className="field">
          <label htmlFor="dr-by">Register by</label>
          <input id="dr-by" type="date" value={f.register_by} onChange={(e) => setF({ ...f, register_by: e.target.value })} required />
        </div>
        <div className="field">
          <label htmlFor="dr-prog">Programme</label>
          <select id="dr-prog" value={f.programme_id} onChange={(e) => setF({ ...f, programme_id: e.target.value })}>
            <option value="">All programmes</option>
            {setup.data?.programmes.map((p) => (
              <option key={p.id} value={p.id}>
                {p.code}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="dr-status">Status</label>
          <select id="dr-status" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value as Drive["status"] })}>
            <option value="open">Open</option>
            <option value="closed">Closed</option>
            <option value="completed">Completed</option>
          </select>
        </div>
      </div>
      <div className="field">
        <label htmlFor="dr-desc">Description</label>
        <input id="dr-desc" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
      </div>
      {save.error && <p className="form-error">{save.error.message}</p>}
      <div className="row-actions" style={{ justifyContent: "flex-start" }}>
        <button type="submit" className="btn btn-primary" disabled={save.isPending}>
          Save drive
        </button>
        <button type="button" className="btn btn-ghost" onClick={onDone}>
          Cancel
        </button>
      </div>
    </form>
  );
}

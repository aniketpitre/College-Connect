import { useState } from "react";
import { EmptyState } from "../../components/EmptyState";
import { Modal } from "../../components/Modal";
import { StatusBadge } from "../../components/StatusBadge";
import { hasPermission, useMe } from "../../lib/auth";
import {
  useAddNote,
  useAssign,
  useAssignments,
  useAtRisk,
  useMentees,
  useRecompute,
  useRiskDetail,
  useRules,
  useSaveRules,
  type Level,
  type RiskRow,
  type Rules,
} from "../../lib/mentoring";
import { useSetup } from "../../lib/setup";
import "../campus/campus.css";
import "./mentoring.css";

type Tab = "mentees" | "risk" | "assign" | "rules";
const LEVEL: Record<Level, { label: string; tone: "danger" | "warning" | "neutral" }> = {
  high: { label: "High risk", tone: "danger" },
  medium: { label: "To watch", tone: "warning" },
  none: { label: "No concerns", tone: "neutral" },
};
const day = (iso: string) => new Date(iso.length > 10 ? iso : `${iso}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short" });

/** Staff only (English): mentees with the reasons for concern, the early-warning list, mentor assignment, rules.
 * Students and parents never see any of this. */
export default function MentoringPage() {
  const { data: me } = useMe();
  const isMentor = hasPermission(me, "mentoring.mentees");
  const canSeeRisk = hasPermission(me, "risk.read") || hasPermission(me, "risk.read.dept");
  const canAssign = hasPermission(me, "mentoring.assign");
  const canManage = hasPermission(me, "risk.manage");
  const tabs = [
    ...(isMentor ? ([["mentees", "My mentees"]] as const) : []),
    ...(canSeeRisk ? ([["risk", "Early warning"]] as const) : []),
    ...(canAssign ? ([["assign", "Assign mentors"]] as const) : []),
    ...(canManage ? ([["rules", "Rules"]] as const) : []),
  ];
  const [picked, setPicked] = useState<Tab | null>(null);
  const tab = picked ?? tabs[0]?.[0];
  const [open, setOpen] = useState<string | null>(null);
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Mentoring</div>
          <h1>Students who may need help</h1>
        </div>
      </div>
      <p className="small muted">
        Reasons come from attendance, internal marks, results and fees. They are a prompt to talk to the student, never a penalty, and only the mentor, the HOD
        and the Principal see them.
      </p>
      <div className="tabs" role="tablist">
        {tabs.map(([k, label]) => (
          <button key={k} type="button" role="tab" aria-selected={tab === k} className={tab === k ? "active" : ""} onClick={() => setPicked(k)}>
            {label}
          </button>
        ))}
      </div>
      {tab === "mentees" && <Mentees onOpen={setOpen} />}
      {tab === "risk" && <AtRisk onOpen={setOpen} canRecompute={canManage} />}
      {tab === "assign" && <Assign />}
      {tab === "rules" && <RulesForm />}
      {open && <Student id={open} onClose={() => setOpen(null)} />}
    </>
  );
}

function Rows({ rows, onOpen }: { rows: RiskRow[]; onOpen: (id: string) => void }) {
  if (rows.length === 0) return <EmptyState title="Nobody here" />;
  return (
    <ul className="campus-list">
      {rows.map((r) => (
        <li key={r.student_id} className={r.level === "high" ? "late" : ""}>
          <button type="button" className="link-button risk-row" onClick={() => onOpen(r.student_id)}>
            <b>
              {r.name} <span className="muted small">({r.prn})</span>
            </b>
            <span className="small muted">
              {r.class}
              {r.mentor && ` · mentor ${r.mentor}`}
              {r.notes > 0 && ` · ${r.notes} note${r.notes > 1 ? "s" : ""}`}
              {r.follow_up_on && ` · follow up ${day(r.follow_up_on)}`}
            </span>
            {r.reasons.length > 0 && (
              <span className="risk-reasons small">
                {r.reasons.map((x) => (
                  <span key={x}>{x}</span>
                ))}
              </span>
            )}
          </button>
          <StatusBadge tone={LEVEL[r.level].tone}>{LEVEL[r.level].label}</StatusBadge>
        </li>
      ))}
    </ul>
  );
}

function Mentees({ onOpen }: { onOpen: (id: string) => void }) {
  const mine = useMentees(true);
  if (!mine.data) return null;
  if (mine.data.students.length === 0) return <EmptyState title="No mentees assigned to you yet" />;
  return (
    <>
      <p className="small">
        {mine.data.students.length} mentees · {mine.data.high} high risk · {mine.data.medium} to watch
      </p>
      <Rows rows={mine.data.students} onOpen={onOpen} />
    </>
  );
}

function AtRisk({ onOpen, canRecompute }: { onOpen: (id: string) => void; canRecompute: boolean }) {
  const [level, setLevel] = useState("");
  const list = useAtRisk(level, true);
  const recompute = useRecompute();
  return (
    <>
      <div className="row-actions" style={{ justifyContent: "space-between", marginBottom: 10 }}>
        <div className="day-pick" role="group" aria-label="Level">
          {(
            [
              ["", "All"],
              ["high", "High risk"],
              ["medium", "To watch"],
            ] as const
          ).map(([k, label]) => (
            <button key={k} type="button" className={level === k ? "active" : ""} aria-pressed={level === k} onClick={() => setLevel(k)}>
              {label}
            </button>
          ))}
        </div>
        <span className="small muted">
          {list.data?.computed_at &&
            `Worked out ${new Date(list.data.computed_at).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })}`}
          {canRecompute && (
            <button type="button" className="btn btn-ghost btn-sm" style={{ marginLeft: 8 }} disabled={recompute.isPending} onClick={() => recompute.mutate()}>
              Work it out now
            </button>
          )}
        </span>
      </div>
      {list.data && <Rows rows={list.data.students} onOpen={onOpen} />}
    </>
  );
}

function Student({ id, onClose }: { id: string; onClose: () => void }) {
  const detail = useRiskDetail(id);
  const add = useAddNote();
  const [text, setText] = useState("");
  const [followUp, setFollowUp] = useState("");
  const d = detail.data;
  return (
    <Modal open title={d ? `${d.name} (${d.prn})` : "Student"} onClose={onClose} wide>
      {d && (
        <>
          <p>
            <StatusBadge tone={LEVEL[d.level].tone}>{LEVEL[d.level].label}</StatusBadge> <span className="small muted">{d.class}</span>
          </p>
          {d.reasons.length > 0 ? (
            <ul className="small">
              {d.reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          ) : (
            <p className="small muted">No concerns from the rules right now.</p>
          )}
          <h3 className="subhead">Counselling notes</h3>
          <form
            className="risk-note"
            onSubmit={(e) => {
              e.preventDefault();
              add.mutate({ id, text, follow_up_on: followUp || null }, { onSuccess: () => (setText(""), setFollowUp("")) });
            }}
          >
            <label htmlFor="risk-note">What you discussed and agreed</label>
            <textarea id="risk-note" rows={3} value={text} onChange={(e) => setText(e.target.value)} required minLength={3} />
            <label htmlFor="risk-follow">Follow up on (optional)</label>
            <input id="risk-follow" type="date" value={followUp} onChange={(e) => setFollowUp(e.target.value)} />
            {add.error && <p className="form-error">{add.error.message}</p>}
            <div>
              <button type="submit" className="btn btn-primary btn-sm" disabled={add.isPending}>
                Save note
              </button>
            </div>
          </form>
          <ul className="campus-list">
            {d.history.map((n) => (
              <li key={n.id}>
                <div>
                  <div className="small muted">
                    {n.by} · {day(n.at)}
                    {n.follow_up_on && ` · follow up ${day(n.follow_up_on)}`}
                  </div>
                  {n.text}
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </Modal>
  );
}

function Assign() {
  const setup = useSetup();
  const [divisionId, setDivisionId] = useState("");
  const list = useAssignments(divisionId);
  const assign = useAssign();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [mentor, setMentor] = useState("");
  const programmes = new Map((setup.data?.programmes ?? []).map((p) => [p.id, p.code]));
  return (
    <>
      <select className="campus-search" value={divisionId} onChange={(e) => (setDivisionId(e.target.value), setSelected(new Set()))} aria-label="Class">
        <option value="">Pick a class</option>
        {setup.data?.divisions.map((d) => (
          <option key={d.id} value={d.id}>
            {programmes.get(d.programme_id)} year {d.year_of_study} {d.name}
          </option>
        ))}
      </select>
      {list.data && (
        <>
          <div className="row-actions" style={{ justifyContent: "flex-start", marginBottom: 8 }}>
            <button type="button" className="link-button" onClick={() => setSelected(new Set(list.data.students.map((s) => s.id)))}>
              select all
            </button>
            <select value={mentor} onChange={(e) => setMentor(e.target.value)} aria-label="Mentor">
              <option value="">No mentor</option>
              {list.data.mentors.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              disabled={!selected.size || assign.isPending}
              onClick={() => assign.mutate({ mentor_id: mentor || null, student_ids: [...selected] }, { onSuccess: () => setSelected(new Set()) })}
            >
              Set mentor for {selected.size} student{selected.size === 1 ? "" : "s"}
            </button>
            {assign.error && <span className="form-error">{assign.error.message}</span>}
          </div>
          <ul className="campus-list">
            {list.data.students.map((s) => (
              <li key={s.id}>
                <label className="check-label">
                  <input
                    type="checkbox"
                    checked={selected.has(s.id)}
                    onChange={(e) => {
                      const next = new Set(selected);
                      if (e.target.checked) next.add(s.id);
                      else next.delete(s.id);
                      setSelected(next);
                    }}
                  />
                  {s.name} <span className="muted small">({s.prn})</span>
                </label>
                <span className="small">{s.mentor ?? <span className="muted">no mentor</span>}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}

const RULES: [keyof Rules, string, string][] = [
  ["attendance_below", "Overall attendance below", "%"],
  ["attendance_drop", "Attendance fell in the last 4 weeks by at least", "points"],
  ["marks_below", "Internal marks below, in any subject", "% of the marks"],
  ["backlogs", "Subjects still to clear, at least", ""],
  ["fee_overdue", "Fees overdue for at least", "days"],
];

function RulesForm() {
  const rules = useRules(true);
  const save = useSaveRules();
  const [draft, setDraft] = useState<Rules | null>(null);
  const r = draft ?? rules.data;
  if (!r) return null;
  return (
    <form
      className="card"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate(r);
      }}
    >
      <p className="small muted">One reason makes a student "to watch"; two or more make them "high risk".</p>
      {RULES.map(([key, label, unit]) => (
        <div key={key} className="row-actions" style={{ justifyContent: "flex-start", marginBottom: 6 }}>
          <label className="check-label">
            <input type="checkbox" checked={r[key].on} onChange={(e) => setDraft({ ...r, [key]: { ...r[key], on: e.target.checked } })} /> {label}
          </label>
          <input
            aria-label={label}
            type="number"
            min={0}
            value={r[key].value}
            onChange={(e) => setDraft({ ...r, [key]: { ...r[key], value: Number(e.target.value) } })}
            style={{ width: 80 }}
          />
          <span className="small muted">{unit}</span>
        </div>
      ))}
      {save.error && <p className="form-error">{save.error.message}</p>}
      {save.isSuccess && <p className="small muted">Saved. The new rules apply from the next run.</p>}
      <button type="submit" className="btn btn-primary" disabled={save.isPending}>
        Save rules
      </button>
    </form>
  );
}

import { useState } from "react";
import LanguageToggle from "../../app/LanguageToggle";
import { EmptyState } from "../../components/EmptyState";
import { StatusBadge } from "../../components/StatusBadge";
import { GRIEVANCE_STRINGS } from "../../i18n/grievance";
import { hasPermission, useMe } from "../../lib/auth";
import {
  useCommentGrievance,
  useGrievance,
  useGrievanceAction,
  useGrievanceFeedback,
  useGrievances,
  useGrievanceSettings,
  useGrievanceStats,
  useMyGrievance,
  useMyGrievances,
  useRaiseGrievance,
  useSaveGrievanceSettings,
  type Grievance,
} from "../../lib/grievance";
import { useLanguage } from "../../lib/language";
import "../campus/campus.css";
import "./grievance.css";

const tone = (g: Grievance) => (g.status === "closed" || g.status === "resolved" ? "success" : g.overdue ? "danger" : "warning");

export default function GrievancePage() {
  const { data: me } = useMe();
  if (me?.kind === "student") return <MyGrievances />;
  return <GrievanceDesk canManage={hasPermission(me, "grievance.manage")} />;
}

// --- students (en/hi/mr) --------------------------------------------------------------------

function MyGrievances() {
  const [language, setLanguage] = useLanguage();
  const t = GRIEVANCE_STRINGS[language];
  const mine = useMyGrievances();
  const raise = useRaiseGrievance();
  const [open, setOpen] = useState<string | null>(null);
  const [form, setForm] = useState({
    category: "academic",
    subject: "",
    text: "",
    anonymous: false,
  });
  const locale = language === "en" ? "en-IN" : `${language}-IN`;
  const day = (iso: string) =>
    new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString(locale, {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  const m = mine.data;
  if (!m) return null;
  return (
    <div lang={language}>
      <div className="page-head">
        <h1>{t.title}</h1>
        <LanguageToggle value={language} onChange={setLanguage} />
      </div>
      {open ? (
        <MyGrievanceDetail id={open} onBack={() => setOpen(null)} day={day} />
      ) : (
        <>
          <p className="muted">{t.intro}</p>
          <h2 className="subhead">{t.raise}</h2>
          <form
            className="card campus-form"
            onSubmit={(e) => {
              e.preventDefault();
              raise.mutate(form, {
                onSuccess: (g) => (
                  setForm({
                    category: "academic",
                    subject: "",
                    text: "",
                    anonymous: false,
                  }),
                  setOpen(g.id)
                ),
              });
            }}
          >
            <div className="field">
              <label htmlFor="gr-cat">{t.category}</label>
              <select id="gr-cat" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                {m.categories.map((c) => (
                  <option key={c.key} value={c.key}>
                    {t.categories[c.key] ?? c.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="gr-subject">{t.subject}</label>
              <input
                id="gr-subject"
                value={form.subject}
                onChange={(e) => setForm({ ...form, subject: e.target.value })}
                required
                minLength={3}
                maxLength={120}
              />
            </div>
            <div className="field grievance-wide">
              <label htmlFor="gr-text">{t.details}</label>
              <textarea
                id="gr-text"
                rows={4}
                value={form.text}
                onChange={(e) => setForm({ ...form, text: e.target.value })}
                required
                minLength={10}
                maxLength={3000}
              />
            </div>
            {["ragging", "harassment"].includes(form.category) && <p className="grievance-wide small grievance-note">{t.sensitiveNote}</p>}
            <label className="check-label grievance-wide">
              <input type="checkbox" checked={form.anonymous} onChange={(e) => setForm({ ...form, anonymous: e.target.checked })} /> {t.anonymous}
              <span className="muted small"> · {t.anonymousHint}</span>
            </label>
            {raise.error && <p className="form-error grievance-wide">{raise.error.message}</p>}
            <div>
              <button type="submit" className="btn btn-primary" disabled={raise.isPending}>
                {t.submit}
              </button>
            </div>
          </form>
          <h2 className="subhead">{t.mine}</h2>
          {m.grievances.length === 0 ? (
            <p className="muted">{t.none}</p>
          ) : (
            <ul className="campus-list">
              {m.grievances.map((g) => (
                <li key={g.id}>
                  <button type="button" className="link-button grievance-row" onClick={() => setOpen(g.id)}>
                    <b>{g.subject}</b>
                    <span className="muted small">
                      {g.number} · {t.categories[g.category]} · {day(g.created_at)}
                    </span>
                  </button>
                  <StatusBadge tone={tone(g)}>{g.escalated && g.status === "open" ? t.escalated : t.statuses[g.status]}</StatusBadge>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}

function MyGrievanceDetail({ id, onBack, day }: { id: string; onBack: () => void; day: (iso: string) => string }) {
  const [language] = useLanguage();
  const t = GRIEVANCE_STRINGS[language];
  const one = useMyGrievance(id);
  const comment = useCommentGrievance();
  const feedback = useGrievanceFeedback();
  const [text, setText] = useState("");
  const [fb, setFb] = useState({ satisfied: true, rating: 4, comment: "" });
  const g = one.data;
  if (!g) return null;
  const days = Math.max(0, Math.round((new Date(g.due_date).getTime() - new Date(g.created_at.slice(0, 10)).getTime()) / 86_400_000));
  return (
    <>
      <button type="button" className="link-button" onClick={onBack}>
        ← {t.back}
      </button>
      <section className="card grievance-card">
        <div className="grievance-head">
          <div>
            <div className="eyebrow">
              {g.number} · {t.categories[g.category]}
            </div>
            <h2 className="card-title">{g.subject}</h2>
          </div>
          <div className="grievance-badges">
            {g.anonymous && <StatusBadge tone="neutral">{t.anonymousBadge}</StatusBadge>}
            <StatusBadge tone={tone(g)}>{t.statuses[g.status]}</StatusBadge>
          </div>
        </div>
        <p>{g.text}</p>
        {g.status !== "closed" && g.status !== "resolved" && <p className="small muted">{t.dueBy(day(g.due_date), days)}</p>}
        {g.escalated && g.status === "open" && <p className="small grievance-note">{t.escalated}</p>}
        <ol className="grievance-history">
          {(g.history ?? [])
            .filter((h) => h.kind !== "raised")
            .map((h, i) => (
              <li key={i} className={h.by === "staff" ? "from-college" : ""}>
                <span className="small muted">
                  {t.events[h.kind] ?? h.kind} · {day(h.at)}
                </span>
                {h.text && <div>{h.text}</div>}
              </li>
            ))}
        </ol>
        {g.resolution && (
          <p>
            <b>{t.resolution}:</b> {g.resolution}
          </p>
        )}
        {(g.status === "open" || g.status === "in_progress") && (
          <form
            className="grievance-reply"
            onSubmit={(e) => {
              e.preventDefault();
              comment.mutate({ id: g.id, text }, { onSuccess: () => (setText(""), void one.refetch()) });
            }}
          >
            <label htmlFor="gr-more">{t.addComment}</label>
            <textarea id="gr-more" rows={2} value={text} onChange={(e) => setText(e.target.value)} required />
            <button type="submit" className="btn btn-ghost btn-sm" disabled={comment.isPending}>
              {t.send}
            </button>
          </form>
        )}
        {g.status === "resolved" && (
          <form
            className="grievance-reply"
            onSubmit={(e) => {
              e.preventDefault();
              feedback.mutate({ id: g.id, ...fb }, { onSuccess: () => void one.refetch() });
            }}
          >
            <b>{t.feedbackAsk}</b>
            <div className="row-actions" style={{ justifyContent: "flex-start" }} role="radiogroup" aria-label={t.feedbackAsk}>
              <label className="check-label">
                <input type="radio" name="sat" checked={fb.satisfied} onChange={() => setFb({ ...fb, satisfied: true })} /> {t.yes}
              </label>
              <label className="check-label">
                <input type="radio" name="sat" checked={!fb.satisfied} onChange={() => setFb({ ...fb, satisfied: false })} /> {t.no}
              </label>
              <label>
                {t.rating}{" "}
                <select value={fb.rating} onChange={(e) => setFb({ ...fb, rating: Number(e.target.value) })}>
                  {[5, 4, 3, 2, 1].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {g.reopened === 0 && <p className="small muted">{t.reopenNote}</p>}
            <label htmlFor="gr-fb">{t.comment}</label>
            <textarea id="gr-fb" rows={2} value={fb.comment} onChange={(e) => setFb({ ...fb, comment: e.target.value })} />
            {feedback.error && <p className="form-error">{feedback.error.message}</p>}
            <button type="submit" className="btn btn-primary btn-sm" disabled={feedback.isPending}>
              {t.sendFeedback}
            </button>
          </form>
        )}
        {g.feedback && <p className="small muted">{t.yourFeedback("★".repeat(g.feedback.rating))}</p>}
      </section>
    </>
  );
}

// --- staff (English) ------------------------------------------------------------------------

function GrievanceDesk({ canManage }: { canManage: boolean }) {
  const stats = useGrievanceStats();
  const [tab, setTab] = useState<"open" | "overdue" | "resolved" | "closed" | "report" | "settings">("open");
  const [category, setCategory] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const s = stats.data;
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Grievance redressal</div>
          <h1>Grievances</h1>
        </div>
      </div>
      {s && (
        <div className="tiles fee-tiles">
          <div className="tile">
            <div className="tile-label">Open</div>
            <div className="tile-value">{s.open}</div>
          </div>
          <div className={`tile${s.overdue ? " tile-warn" : ""}`}>
            <div className="tile-label">Past the time limit</div>
            <div className="tile-value">{s.overdue}</div>
          </div>
          <div className="tile">
            <div className="tile-label">Resolved in time</div>
            <div className="tile-value">
              {s.resolved_in_time}/{s.resolved}
            </div>
          </div>
          <div className="tile">
            <div className="tile-label">Satisfied</div>
            <div className="tile-value">
              {s.satisfied}/{s.feedback}
            </div>
          </div>
        </div>
      )}
      <div className="tabs" role="tablist">
        {(
          [
            ["open", "Open"],
            ["overdue", "Overdue"],
            ["resolved", "Resolved"],
            ["closed", "Closed"],
            ["report", "Report"],
            ...(canManage ? ([["settings", "Time limits"]] as const) : []),
          ] as const
        ).map(([k, label]) => (
          <button key={k} type="button" role="tab" aria-selected={tab === k} className={tab === k ? "active" : ""} onClick={() => (setTab(k), setOpen(null))}>
            {label}
          </button>
        ))}
      </div>
      {tab === "report" ? (
        <Report />
      ) : tab === "settings" ? (
        <Settings />
      ) : open ? (
        <Detail id={open} onBack={() => setOpen(null)} />
      ) : (
        <Listing status={tab} category={category} setCategory={setCategory} onOpen={setOpen} />
      )}
    </>
  );
}

const CATEGORY_LABELS = GRIEVANCE_STRINGS.en.categories;
const date = (iso: string) =>
  new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
  });

function Listing({
  status,
  category,
  setCategory,
  onOpen,
}: {
  status: string;
  category: string;
  setCategory: (c: string) => void;
  onOpen: (id: string) => void;
}) {
  const list = useGrievances(status, category);
  return (
    <>
      <select className="campus-search" value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Category">
        <option value="">All categories</option>
        {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
          <option key={k} value={k}>
            {v}
          </option>
        ))}
      </select>
      {list.data?.length === 0 && <EmptyState title="Nothing here" />}
      <ul className="campus-list">
        {list.data?.map((g) => (
          <li key={g.id} className={g.overdue ? "late" : ""}>
            <button type="button" className="link-button grievance-row" onClick={() => onOpen(g.id)}>
              <b>{g.subject}</b>
              <span className="muted small">
                {g.number} · {g.category_label} · {g.student ? `${g.student.name} (${g.student.prn})` : "Anonymous"} · due {date(g.due_date)}
                {g.handler && ` · ${g.handler}`}
              </span>
            </button>
            <span className="grievance-badges">
              {g.escalated && g.status !== "closed" && <StatusBadge tone="danger">Escalated</StatusBadge>}
              <StatusBadge tone={tone(g)}>{g.status_label}</StatusBadge>
            </span>
          </li>
        ))}
      </ul>
    </>
  );
}

const EVENT_LABELS: Record<string, string> = {
  raised: "Raised",
  comment: "Student added",
  reply: "Reply to student",
  note: "Internal note",
  taken: "Taken up",
  resolved: "Resolved",
  feedback: "Student feedback",
  reopened: "Reopened by the student",
  closed: "Closed",
  escalated: "Escalated (time limit passed)",
};

function Detail({ id, onBack }: { id: string; onBack: () => void }) {
  const one = useGrievance(id);
  const act = useGrievanceAction();
  const [text, setText] = useState("");
  const g = one.data;
  if (!g) return null;
  const run = (action: string) => act.mutate({ id: g.id, action, text: text || undefined }, { onSuccess: () => (setText(""), void one.refetch()) });
  const live = g.status === "open" || g.status === "in_progress";
  return (
    <>
      <button type="button" className="link-button" onClick={onBack}>
        ← Back to the list
      </button>
      <section className="card grievance-card">
        <div className="grievance-head">
          <div>
            <div className="eyebrow">
              {g.number} · {g.category_label}
              {g.sensitive && " · confidential (ICC)"}
            </div>
            <h2 className="card-title">{g.subject}</h2>
            <div className="small muted">
              {g.student ? `${g.student.name} (${g.student.prn})` : "Anonymous: the student's name is hidden"} · raised {date(g.created_at)} · due{" "}
              {date(g.due_date)}
            </div>
          </div>
          <div className="grievance-badges">
            {g.escalated && live && <StatusBadge tone="danger">Escalated</StatusBadge>}
            <StatusBadge tone={tone(g)}>{g.status_label}</StatusBadge>
          </div>
        </div>
        <p>{g.text}</p>
        <ol className="grievance-history">
          {(g.history ?? [])
            .filter((h) => h.kind !== "raised")
            .map((h, i) => (
              <li key={i} className={h.kind === "note" ? "note" : h.by === "staff" ? "from-college" : ""}>
                <span className="small muted">
                  {EVENT_LABELS[h.kind] ?? h.kind}
                  {h.name && ` · ${h.name}`} · {date(h.at)}
                </span>
                {h.text && <div>{h.text}</div>}
              </li>
            ))}
        </ol>
        {g.resolution && (
          <p>
            <b>Resolution:</b> {g.resolution}
          </p>
        )}
        {g.feedback && (
          <p className="small">
            Feedback: {g.feedback.satisfied ? "satisfied" : "not satisfied"} · {"★".repeat(g.feedback.rating)}
            {g.feedback.comment && ` · “${g.feedback.comment}”`}
          </p>
        )}
        {live && g.can_act && (
          <div className="grievance-reply">
            <label htmlFor="gr-staff-text">Reply, internal note or resolution</label>
            <textarea id="gr-staff-text" rows={3} value={text} onChange={(e) => setText(e.target.value)} />
            {act.error && <p className="form-error">{act.error.message}</p>}
            <div className="row-actions" style={{ justifyContent: "flex-start" }}>
              {g.status === "open" && (
                <button type="button" className="btn btn-ghost btn-sm" disabled={act.isPending} onClick={() => run("take")}>
                  Take it up
                </button>
              )}
              <button type="button" className="btn btn-ghost btn-sm" disabled={act.isPending || !text.trim()} onClick={() => run("reply")}>
                Reply to student
              </button>
              <button type="button" className="btn btn-ghost btn-sm" disabled={act.isPending || !text.trim()} onClick={() => run("note")}>
                Add internal note
              </button>
              <button type="button" className="btn btn-primary btn-sm" disabled={act.isPending || !text.trim()} onClick={() => run("resolve")}>
                Resolve
              </button>
            </div>
          </div>
        )}
        {live && !g.can_act && <p className="small muted">You can read this grievance; the Grievance Cell acts on it.</p>}
      </section>
    </>
  );
}

function Report() {
  const stats = useGrievanceStats();
  const s = stats.data;
  if (!s) return null;
  return (
    <section className="card">
      <h2 className="card-title">Received and redressed (for NAAC)</h2>
      <p className="small muted">
        {s.received} received · {s.resolved} resolved
        {s.average_days !== null && ` in ${s.average_days} days on average`} · {s.resolved_in_time} within the time limit
        {s.average_rating !== null && ` · average rating ${s.average_rating}/5`}
      </p>
      <div className="data-table">
        <table>
          <thead>
            <tr>
              <th>Category</th>
              <th>Received</th>
              <th>Open</th>
              <th>Resolved</th>
            </tr>
          </thead>
          <tbody>
            {s.by_category.map((c) => (
              <tr key={c.category}>
                <td>{c.label}</td>
                <td>{c.received}</td>
                <td>{c.open}</td>
                <td>{c.resolved}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Settings() {
  const settings = useGrievanceSettings(true);
  const save = useSaveGrievanceSettings();
  const [draft, setDraft] = useState<Record<string, number> | null>(null);
  const [closeAfter, setCloseAfter] = useState<number | null>(null);
  if (!settings.data) return null;
  const sla = draft ?? settings.data.sla_days;
  const close = closeAfter ?? settings.data.close_after_days;
  return (
    <form
      className="card"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate({ sla_days: sla, close_after_days: close });
      }}
    >
      <h2 className="card-title">Time limits (working days)</h2>
      <div className="campus-form">
        {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
          <div className="field" key={k}>
            <label htmlFor={`sla-${k}`}>{v}</label>
            <input id={`sla-${k}`} type="number" min={1} max={90} value={sla[k] ?? 7} onChange={(e) => setDraft({ ...sla, [k]: Number(e.target.value) })} />
          </div>
        ))}
        <div className="field">
          <label htmlFor="sla-close">Close resolved cases without feedback after (days)</label>
          <input id="sla-close" type="number" min={1} max={60} value={close} onChange={(e) => setCloseAfter(Number(e.target.value))} />
        </div>
      </div>
      {save.error && <p className="form-error">{save.error.message}</p>}
      {save.isSuccess && <p className="small muted">Saved.</p>}
      <button type="submit" className="btn btn-primary" disabled={save.isPending}>
        Save
      </button>
    </form>
  );
}

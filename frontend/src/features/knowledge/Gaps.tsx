import { useState } from "react";
import { Link } from "react-router";
import { useGapActions, useGaps, type Gap } from "../../lib/knowledge";

const LANG: Record<string, string> = { en: "English", hi: "Hindi", mr: "Marathi" };

/** The knowledge-gap loop (plan 5.7): questions the help desk couldn't answer, turned into answers. */
export function Gaps() {
  const gaps = useGaps();
  const { answer, dismiss } = useGapActions();
  const [open, setOpen] = useState<string | null>(null);
  return (
    <section className="card" id="gaps">
      <h2 className="card-title">Questions the help desk couldn't answer</h2>
      <p className="small muted">
        Last 30 days, most asked first. Answer one as an FAQ (the help desk answers from it at once), publish a notice about it, or dismiss it.
      </p>
      {(answer.error ?? dismiss.error) && <p className="form-error">{(answer.error ?? dismiss.error)?.message}</p>}
      {answer.data && (
        <p className="auth-success" role="status">
          Added "{answer.data.title}"; {answer.data.questions_closed} question{answer.data.questions_closed === 1 ? "" : "s"} answered.
        </p>
      )}
      {gaps.data?.length === 0 && <p className="small muted">Nothing unanswered. 🎉</p>}
      <ul className="campus-list">
        {gaps.data?.map((g) => (
          <li key={g.key} style={{ flexWrap: "wrap" }}>
            <div>
              <b>{g.question}</b>
              <div className="small muted">
                asked {g.count} time{g.count === 1 ? "" : "s"} · {g.languages.map((l) => LANG[l] ?? l).join(", ")} · last{" "}
                {new Date(g.last_at).toLocaleDateString("en-IN")}
              </div>
            </div>
            <span className="row-actions">
              <button type="button" className="btn btn-primary btn-sm" onClick={() => setOpen(open === g.key ? null : g.key)}>
                Answer as FAQ
              </button>
              <Link className="btn btn-ghost btn-sm" to={`/app/notices?draft=${encodeURIComponent(g.question)}`}>
                Make a notice
              </Link>
              <button type="button" className="btn btn-ghost btn-sm" disabled={dismiss.isPending} onClick={() => dismiss.mutate(g.key)}>
                Dismiss
              </button>
            </span>
            {open === g.key && <AnswerForm gap={g} busy={answer.isPending} onSave={(body) => answer.mutate(body, { onSuccess: () => setOpen(null) })} />}
          </li>
        ))}
      </ul>
    </section>
  );
}

function AnswerForm({
  gap,
  busy,
  onSave,
}: {
  gap: Gap;
  busy: boolean;
  onSave: (body: { key: string; question: string; answer: string; category: string; audience: string }) => void;
}) {
  const [question, setQuestion] = useState(gap.question);
  const [text, setText] = useState("");
  const [category, setCategory] = useState("notices");
  const [audience, setAudience] = useState("public");
  return (
    <form
      className="campus-form"
      style={{ width: "100%" }}
      onSubmit={(e) => {
        e.preventDefault();
        onSave({ key: gap.key, question, answer: text, category, audience });
      }}
    >
      <div className="field">
        <label htmlFor={`gq-${gap.key}`}>Question (as it should read)</label>
        <input id={`gq-${gap.key}`} value={question} onChange={(e) => setQuestion(e.target.value)} required />
      </div>
      <div className="field">
        <label htmlFor={`ga-${gap.key}`}>Answer</label>
        <textarea id={`ga-${gap.key}`} rows={3} value={text} onChange={(e) => setText(e.target.value)} required minLength={5} />
      </div>
      <div className="field">
        <label htmlFor={`gc-${gap.key}`}>Office</label>
        <select id={`gc-${gap.key}`} value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="admissions">Admissions</option>
          <option value="fees">Fees & Accounts</option>
          <option value="examinations">Examinations</option>
          <option value="placements">Placements</option>
          <option value="hostel">Hostel & Campus</option>
          <option value="notices">Notices</option>
        </select>
      </div>
      <div className="field">
        <label htmlFor={`gw-${gap.key}`}>Who gets answers from it</label>
        <select id={`gw-${gap.key}`} value={audience} onChange={(e) => setAudience(e.target.value)}>
          <option value="public">Anyone (public help desk too)</option>
          <option value="everyone">Signed-in members only</option>
        </select>
      </div>
      <div>
        <button type="submit" className="btn btn-primary btn-sm" disabled={busy}>
          Save the FAQ
        </button>
      </div>
    </form>
  );
}

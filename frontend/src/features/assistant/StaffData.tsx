import { useState } from "react";
import { Link } from "react-router";
import { useAskStaff, type StaffAnswer } from "../../lib/assistant";
import { formatPaise } from "../../lib/money";

const EXAMPLES = [
  "How many SY BCA students owe more than ₹10,000?",
  "Who is below 75% attendance in FY?",
  "Which certificate requests are past the promised date?",
];

function cell(value: unknown, type: string) {
  if (value === null || value === undefined) return "";
  if (type === "money") return formatPaise(Number(value));
  if (type === "number") return `${value}`;
  if (type === "date") return new Date(`${value}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
  return String(value);
}

/** Staff (English): questions about the college's own numbers, answered by fixed, permission-checked reports. */
export function StaffData({ onNavigate }: { onNavigate: () => void }) {
  const ask = useAskStaff();
  const [input, setInput] = useState("");
  const [result, setResult] = useState<StaffAnswer | null>(null);
  const send = (q: string) => {
    if (!q.trim() || ask.isPending) return;
    setInput(q);
    ask.mutate(q.trim(), { onSuccess: setResult });
  };
  return (
    <>
      <div className="assistant-list">
        {!result && !ask.error && (
          <div className="assistant-intro">
            <p className="small">
              Ask about fees outstanding, attendance, open certificate requests or backlogs. The answer comes from the college's records, only what your role
              may see, with the list behind the number.
            </p>
            {EXAMPLES.map((q) => (
              <button key={q} type="button" className="assistant-chip" onClick={() => send(q)}>
                {q}
              </button>
            ))}
          </div>
        )}
        {ask.isPending && <p className="small muted">Looking it up…</p>}
        {ask.error && <p className="form-error">{ask.error.message}</p>}
        {result && !ask.isPending && (
          <div className="assistant-msg assistant" style={{ maxWidth: "100%" }}>
            <div className="assistant-text">{result.summary}</div>
            {!result.answered &&
              result.examples?.map((q) => (
                <button key={q} type="button" className="assistant-chip" onClick={() => send(q)}>
                  {q}
                </button>
              ))}
            {result.answered && result.rows && result.columns && result.rows.length > 0 && (
              <div className="assistant-table">
                <table>
                  <thead>
                    <tr>
                      {result.columns.map((c) => (
                        <th key={c.key}>{c.label}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.rows.map((r, i) => (
                      <tr key={i}>
                        {result.columns!.map((c) => (
                          <td key={c.key}>
                            {c.key === "student" && r.student_id ? (
                              <Link to={`/app/students/${r.student_id}`} onClick={onNavigate}>
                                {cell(r[c.key], c.type)}
                              </Link>
                            ) : (
                              cell(r[c.key], c.type)
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {!!result.more && <p className="small muted">…and {result.more} more: open the full report.</p>}
            {result.link && (
              <Link className="small" to={result.link} onClick={onNavigate}>
                Open the full report →
              </Link>
            )}
          </div>
        )}
      </div>
      <form
        className="assistant-form"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <textarea
          rows={2}
          maxLength={300}
          value={input}
          placeholder="Ask about the college's numbers…"
          aria-label="Question about college data"
          onChange={(e) => setInput(e.target.value)}
        />
        <button type="submit" className="btn btn-primary btn-sm" disabled={ask.isPending || input.trim().length < 3}>
          Ask
        </button>
      </form>
    </>
  );
}

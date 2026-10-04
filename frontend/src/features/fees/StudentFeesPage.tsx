import { useState } from "react";
import { Link, useParams } from "react-router";
import { AmountInput } from "../../components/AmountInput";
import { MoneyText } from "../../components/MoneyText";
import { Modal } from "../../components/Modal";
import { StatusBadge } from "../../components/StatusBadge";
import { ApiError } from "../../lib/api";
import { hasPermission, useMe } from "../../lib/auth";
import {
  useAddCharge,
  useApplyLateFees,
  useApprovals,
  useCreateScholarship,
  useFeeAccount,
  useFeeHeads,
  useRequestConcession,
  useScholarshipAction,
  useScholarships,
  receiptPdfUrl,
  type FeeAccount,
  type Scholarship,
} from "../../lib/fees";
import { formatPaise, parseRupees } from "../../lib/money";
import { useSetup } from "../../lib/setup";
import "./fees.css";

const fmtDate = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });

/** Accounts screen (English): one student's fee account for a year. */
export default function StudentFeesPage() {
  const { id = "" } = useParams();
  const { data: me } = useMe();
  const setup = useSetup();
  const [yearId, setYearId] = useState("");
  const year = yearId || setup.data?.current_year?.id || "";
  const account = useFeeAccount(id, year || undefined);
  const [dialog, setDialog] = useState<"concession" | "charge" | "scholarship" | null>(null);
  const late = useApplyLateFees();
  const canManage = hasPermission(me, "fees.manage");
  const canCollect = hasPermission(me, "fees.collect");
  const a = account.data;

  if (account.error) return <p className="form-error">{account.error.message}</p>;
  if (!a) return <p className="muted">Loading…</p>;
  const st = a.student;
  const lateDue = a.late_fee > 0 && a.installments.some((i) => i.overdue);

  return (
    <>
      <Link to="/app/fees" className="back-link">
        ← Fees
      </Link>
      <div className="page-head">
        <div>
          <div className="eyebrow">Fee account</div>
          <h1>{st?.name}</h1>
          <div className="muted">
            PRN {st?.prn} · {[st?.programme_code, st?.year_label, st?.division].filter(Boolean).join(" · ")} · {st?.category_code ?? "No category"}
          </div>
        </div>
        <div className="row-actions">
          <select aria-label="Academic year" className="year-select" value={year} onChange={(e) => setYearId(e.target.value)}>
            {setup.data?.academic_years.map((y) => (
              <option key={y.id} value={y.id}>
                {y.name}
              </option>
            ))}
          </select>
          {canCollect && a.balance > 0 && (
            <Link className="btn btn-primary" to={`/app/fees/collect/${id}`}>
              Collect fee
            </Link>
          )}
        </div>
      </div>

      <div className="tiles fee-tiles">
        <Tile label="Total fee" paise={a.demand + a.charges} />
        <Tile label="Paid" paise={a.paid} />
        <Tile label="Concessions + scholarships" paise={a.concessions + a.scholarships} />
        <Tile label="Balance due" paise={a.balance} strong />
        {a.overdue > 0 && <Tile label="Overdue now" paise={a.overdue} warn />}
      </div>
      {!a.has_demand && <p className="muted">This year's fee hasn't been charged to this student yet (Fee setup → Charge the year's fees).</p>}

      <div className="row-actions action-bar">
        {canCollect && a.has_demand && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setDialog("concession")}>
            Request concession
          </button>
        )}
        {canManage && (
          <>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setDialog("scholarship")}>
              Record scholarship
            </button>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setDialog("charge")}>
              Add a charge
            </button>
            {lateDue && (
              <button type="button" className="btn btn-ghost btn-sm" disabled={late.isPending} onClick={() => late.mutate({ studentId: id, yearId: year })}>
                Apply late fee ({formatPaise(a.late_fee)} per overdue installment)
              </button>
            )}
          </>
        )}
      </div>
      {late.error && <p className="form-error">{late.error.message}</p>}

      <div className="record-grid">
        <section className="card">
          <h2>Installments</h2>
          <table className="mini-table">
            <tbody>
              {a.installments.map((i) => (
                <tr key={i.label}>
                  <td>
                    {i.label}
                    <div className="muted small">due {fmtDate(i.due_date)}</div>
                  </td>
                  <td className="num">
                    <MoneyText paise={i.amount} />
                  </td>
                  <td className="num">
                    {i.due === 0 ? <StatusBadge tone="success">Paid</StatusBadge> : i.overdue ? <StatusBadge tone="danger">{formatPaise(i.due)} overdue</StatusBadge> : <StatusBadge tone="warning">{formatPaise(i.due)} due</StatusBadge>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <section className="card">
          <h2>Outstanding by fee head</h2>
          <table className="mini-table">
            <tbody>
              {a.by_head.map((h) => (
                <tr key={h.head_id}>
                  <td>{h.name}</td>
                  <td className="num">
                    <MoneyText paise={h.outstanding} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>

      <h2 className="subhead">Statement</h2>
      <Statement account={a} />

      <h2 className="subhead">Scholarships</h2>
      <Scholarships studentId={id} yearId={year} canManage={canManage} />

      <h2 className="subhead">Requests</h2>
      <Requests studentId={id} />

      {dialog === "concession" && <ConcessionDialog account={a} onClose={() => setDialog(null)} />}
      {dialog === "charge" && <ChargeDialog account={a} onClose={() => setDialog(null)} />}
      {dialog === "scholarship" && <ScholarshipDialog account={a} onClose={() => setDialog(null)} />}
    </>
  );
}

function Tile({ label, paise, strong, warn }: { label: string; paise: number; strong?: boolean; warn?: boolean }) {
  return (
    <div className={`tile${warn ? " tile-warn" : ""}`}>
      <div className="tile-label">{label}</div>
      <div className="tile-value" style={strong ? undefined : { fontSize: "1.4rem" }}>
        <MoneyText paise={paise} />
      </div>
    </div>
  );
}

export function Statement({ account }: { account: FeeAccount }) {
  const balances = account.entries.reduce<number[]>((acc, e) => [...acc, (acc.at(-1) ?? 0) + e.amount], []);
  return (
    <div className="data-table-scroll">
      <table className="statement">
        <thead>
          <tr>
            <th>Date</th>
            <th>Entry</th>
            <th className="num">Charged</th>
            <th className="num">Credited</th>
            <th className="num">Balance</th>
          </tr>
        </thead>
        <tbody>
          {account.entries.map((e, i) => {
            const running = balances[i];
            return (
              <tr key={e.id} className={e.reversed ? "reversed" : ""}>
                <td className="nowrap">{fmtDate(e.at)}</td>
                <td>
                  {e.label}
                  {e.receipt_number && e.receipt_id ? (
                    <>
                      {" · "}
                      <a href={receiptPdfUrl(e.receipt_id)} target="_blank" rel="noreferrer" className="mono-link">
                        {e.receipt_number}
                      </a>
                    </>
                  ) : null}
                  {e.reversed ? " (cancelled)" : ""}
                  <div className="muted small">{e.reason ?? e.lines.map((l) => `${l.head} ${formatPaise(Math.abs(l.amount))}`).join(", ")}</div>
                </td>
                <td className="num">{e.amount > 0 ? <MoneyText paise={e.amount} /> : ""}</td>
                <td className="num">{e.amount < 0 ? <MoneyText paise={-e.amount} /> : ""}</td>
                <td className="num">
                  <MoneyText paise={running} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Scholarships({ studentId, yearId, canManage }: { studentId: string; yearId: string; canManage: boolean }) {
  const list = useScholarships(studentId, yearId);
  const act = useScholarshipAction();
  const [acting, setActing] = useState<{ s: Scholarship; action: "sanction" | "receive" | "reject" } | null>(null);
  const TONE = { expected: "info", sanctioned: "warning", received: "success", rejected: "neutral" } as const;
  if (!list.data?.length) return <p className="muted">None recorded.</p>;
  return (
    <>
      {act.error && <p className="form-error">{act.error.message}</p>}
      <ul className="doc-list">
        {list.data.map((s) => (
          <li key={s.id}>
            <div>
              <div className="doc-name">
                {s.scheme} <StatusBadge tone={TONE[s.status]}>{s.status}</StatusBadge>
              </div>
              <div className="muted doc-meta">
                Expected {formatPaise(s.expected)} · Sanctioned {formatPaise(s.sanctioned)} · Received {formatPaise(s.received)}
                {s.reference ? ` · Ref ${s.reference}` : ""}
              </div>
            </div>
            {canManage && (
              <div className="row-actions">
                {s.status === "expected" && (
                  <button type="button" className="link-btn" onClick={() => setActing({ s, action: "sanction" })}>
                    Sanctioned
                  </button>
                )}
                {s.status === "sanctioned" && (
                  <button type="button" className="link-btn" onClick={() => setActing({ s, action: "receive" })}>
                    Money received
                  </button>
                )}
                {(s.status === "expected" || (s.status === "sanctioned" && s.received === 0)) && (
                  <button type="button" className="link-btn" onClick={() => setActing({ s, action: "reject" })}>
                    Rejected
                  </button>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
      {acting && <ScholarshipActionDialog {...acting} onClose={() => setActing(null)} />}
    </>
  );
}

function ScholarshipActionDialog({ s, action, onClose }: { s: Scholarship; action: "sanction" | "receive" | "reject"; onClose: () => void }) {
  const act = useScholarshipAction();
  const [amount, setAmount] = useState(action === "sanction" ? String(s.expected / 100) : action === "receive" ? String((s.sanctioned - s.received) / 100) : "");
  const [reference, setReference] = useState("");
  const [reason, setReason] = useState("");
  const title = { sanction: "Scholarship sanctioned", receive: "Scholarship money received", reject: "Scholarship rejected" }[action];
  return (
    <Modal open title={title} onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          act.mutate(
            { id: s.id, body: { action, amount: action === "reject" ? null : parseRupees(amount), reference: reference || null, reason: reason || null } },
            { onSuccess: onClose },
          );
        }}
      >
        {action === "sanction" && <p className="muted">The student will owe this much less.</p>}
        {act.error && <div className="form-error">{act.error.message}</div>}
        {action !== "reject" && (
          <div className="field">
            <label htmlFor="sch-amt">Amount</label>
            <AmountInput id="sch-amt" value={amount} onChange={setAmount} required />
          </div>
        )}
        {action !== "reject" && (
          <div className="field">
            <label htmlFor="sch-ref">Reference (optional)</label>
            <input id="sch-ref" value={reference} onChange={(e) => setReference(e.target.value)} />
          </div>
        )}
        {action === "reject" && (
          <div className="field">
            <label htmlFor="sch-reason">Reason</label>
            <input id="sch-reason" value={reason} onChange={(e) => setReason(e.target.value)} required minLength={3} />
          </div>
        )}
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={act.isPending}>
            Save
          </button>
        </div>
      </form>
    </Modal>
  );
}

function Requests({ studentId }: { studentId: string }) {
  const pending = useApprovals("pending", studentId);
  const approved = useApprovals("approved", studentId);
  const rejected = useApprovals("rejected", studentId);
  const all = [...(pending.data ?? []), ...(approved.data ?? []), ...(rejected.data ?? [])];
  if (!all.length) return <p className="muted">No concession, cancellation or refund requests.</p>;
  const TONE = { pending: "warning", approved: "success", rejected: "neutral" } as const;
  return (
    <ul className="doc-list">
      {all.map((r) => (
        <li key={r.id}>
          <div>
            <div className="doc-name">
              {r.kind_label} · <MoneyText paise={r.amount} /> <StatusBadge tone={TONE[r.status]}>{r.status}</StatusBadge>
            </div>
            <div className="muted doc-meta">
              {r.reason} · asked by {r.requested_by} on {fmtDate(r.requested_at)}
              {r.decided_by ? ` · ${r.status} by ${r.decided_by}${r.decision_reason ? `: ${r.decision_reason}` : ""}` : ""}
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}

function useHeadOptions(account: FeeAccount) {
  const heads = useFeeHeads();
  return { all: (heads.data ?? []).filter((h) => h.status === "active"), owed: account.by_head.filter((h) => h.outstanding > 0) };
}

function ConcessionDialog({ account, onClose }: { account: FeeAccount; onClose: () => void }) {
  const send = useRequestConcession();
  const { owed } = useHeadOptions(account);
  const [headId, setHeadId] = useState(owed[0]?.head_id ?? "");
  const [amount, setAmount] = useState("");
  const [kind, setKind] = useState("merit");
  const [reason, setReason] = useState("");
  const err = send.error instanceof ApiError ? send.error : null;
  const head = owed.find((h) => h.head_id === headId);
  return (
    <Modal open title="Request a concession" onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          send.mutate({ student_id: account.student_id, academic_year_id: account.academic_year_id, head_id: headId, amount: parseRupees(amount), kind, reason }, { onSuccess: onClose });
        }}
      >
        <p className="muted">The Principal approves it before the student's balance changes.</p>
        {err && <div className="form-error">{err.message}</div>}
        <div className="field">
          <label htmlFor="c-head">On fee head</label>
          <select id="c-head" value={headId} onChange={(e) => setHeadId(e.target.value)}>
            {owed.map((h) => (
              <option key={h.head_id} value={h.head_id}>
                {h.name} ({formatPaise(h.outstanding)} owed)
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="c-amt">Amount{head ? ` (up to ${formatPaise(head.outstanding)})` : ""}</label>
          <AmountInput id="c-amt" value={amount} onChange={setAmount} required />
        </div>
        <div className="field">
          <label htmlFor="c-kind">Type</label>
          <select id="c-kind" value={kind} onChange={(e) => setKind(e.target.value)}>
            {[
              ["staff_ward", "Staff ward"],
              ["sibling", "Sibling"],
              ["merit", "Merit"],
              ["sports", "Sports"],
              ["need_based", "Need-based"],
              ["other", "Other"],
            ].map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="c-reason">Reason</label>
          <input id="c-reason" value={reason} onChange={(e) => setReason(e.target.value)} required minLength={5} />
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={send.isPending || parseRupees(amount) === null}>
            Send for approval
          </button>
        </div>
      </form>
    </Modal>
  );
}

function ChargeDialog({ account, onClose }: { account: FeeAccount; onClose: () => void }) {
  const add = useAddCharge();
  const { all } = useHeadOptions(account);
  const [headId, setHeadId] = useState("");
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  return (
    <Modal open title="Add a charge" onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          add.mutate({ studentId: account.student_id, body: { academic_year_id: account.academic_year_id, head_id: headId, amount: parseRupees(amount), reason } }, { onSuccess: onClose });
        }}
      >
        <p className="muted">For something extra the student owes, e.g. a fine or a duplicate ID card.</p>
        {add.error && <div className="form-error">{add.error.message}</div>}
        <div className="field">
          <label htmlFor="ch-head">Fee head</label>
          <select id="ch-head" value={headId} onChange={(e) => setHeadId(e.target.value)} required>
            <option value="">Choose…</option>
            {all.map((h) => (
              <option key={h.id} value={h.id}>
                {h.code} · {h.name}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="ch-amt">Amount</label>
          <AmountInput id="ch-amt" value={amount} onChange={setAmount} required />
        </div>
        <div className="field">
          <label htmlFor="ch-reason">Reason</label>
          <input id="ch-reason" value={reason} onChange={(e) => setReason(e.target.value)} required minLength={3} />
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={add.isPending || parseRupees(amount) === null}>
            Add charge
          </button>
        </div>
      </form>
    </Modal>
  );
}

function ScholarshipDialog({ account, onClose }: { account: FeeAccount; onClose: () => void }) {
  const create = useCreateScholarship();
  const [scheme, setScheme] = useState("MahaDBT Post-Matric Scholarship");
  const [reference, setReference] = useState("");
  const [expected, setExpected] = useState("");
  return (
    <Modal open title="Record a scholarship" onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate({ student_id: account.student_id, academic_year_id: account.academic_year_id, scheme, reference, expected: parseRupees(expected) }, { onSuccess: onClose });
        }}
      >
        <p className="muted">Recorded as expected. When it is sanctioned the student owes that much less.</p>
        {create.error && <div className="form-error">{create.error.message}</div>}
        <div className="field">
          <label htmlFor="s-scheme">Scheme</label>
          <input id="s-scheme" list="schemes" value={scheme} onChange={(e) => setScheme(e.target.value)} required />
          <datalist id="schemes">
            <option value="MahaDBT Post-Matric Scholarship" />
            <option value="MahaDBT Freeship" />
            <option value="Rajarshi Chhatrapati Shahu Maharaj Shikshan Shulkh Shishyavrutti" />
            <option value="NSP Central Sector Scholarship" />
          </datalist>
        </div>
        <div className="field">
          <label htmlFor="s-ref">Application ID (optional)</label>
          <input id="s-ref" value={reference} onChange={(e) => setReference(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="s-exp">Expected amount</label>
          <AmountInput id="s-exp" value={expected} onChange={setExpected} required />
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={create.isPending || parseRupees(expected) === null}>
            Save
          </button>
        </div>
      </form>
    </Modal>
  );
}

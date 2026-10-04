import { useState } from "react";
import { Link, useParams } from "react-router";
import { AmountInput } from "../../components/AmountInput";
import { MoneyText } from "../../components/MoneyText";
import { ApiError } from "../../lib/api";
import { MODES, receiptPdfUrl, useCollect, useEmailReceipt, useFeeAccount, type Receipt } from "../../lib/fees";
import { formatPaise, paiseToInput, parseRupees } from "../../lib/money";
import { useSetup } from "../../lib/setup";
import "./fees.css";

/** Accounts counter (English): take a payment and issue the receipt. */
export default function CollectPage() {
  const { id = "" } = useParams();
  const setup = useSetup();
  const year = setup.data?.current_year?.id;
  const account = useFeeAccount(id, year);
  const collect = useCollect();
  const [amount, setAmount] = useState("");
  const [mode, setMode] = useState("cash");
  const [reference, setReference] = useState("");
  const [bank, setBank] = useState("");
  const [instrumentDate, setInstrumentDate] = useState("");
  const [note, setNote] = useState("");
  const [done, setDone] = useState<Receipt | null>(null);
  const a = account.data;
  const err = collect.error instanceof ApiError ? collect.error : null;

  if (done) return <Done receipt={done} />;
  if (account.error) return <p className="form-error">{account.error.message}</p>;
  if (!a) return <p className="muted">Loading…</p>;
  const nextDue = a.installments.find((i) => i.due > 0);
  const paise = parseRupees(amount);
  const quick: [string, number][] = [
    ["Full balance", a.balance],
    ...(a.overdue > 0 && a.overdue !== a.balance ? ([["Overdue now", a.overdue]] as [string, number][]) : []),
    ...(nextDue && nextDue.due !== a.balance && nextDue.due !== a.overdue ? ([[nextDue.label, nextDue.due]] as [string, number][]) : []),
  ];

  return (
    <>
      <Link to={`/app/fees/students/${id}`} className="back-link">
        ← Fee account
      </Link>
      <div className="page-head">
        <div>
          <div className="eyebrow">Collect fee · {setup.data?.current_year?.name}</div>
          <h1>{a.student?.name}</h1>
          <div className="muted">
            PRN {a.student?.prn} · {[a.student?.programme_code, a.student?.year_label, a.student?.division].filter(Boolean).join(" · ")}
          </div>
        </div>
        <div className="balance-box">
          <div className="tile-label">Balance due</div>
          <div className="tile-value">
            <MoneyText paise={a.balance} />
          </div>
          {a.overdue > 0 && <div className="field-error">{formatPaise(a.overdue)} overdue</div>}
        </div>
      </div>

      {a.balance <= 0 ? (
        <p className="auth-success">Nothing is due for this year.</p>
      ) : (
        <form
          className="card collect-form"
          onSubmit={(e) => {
            e.preventDefault();
            collect.mutate(
              {
                student_id: id,
                academic_year_id: a.academic_year_id,
                amount: paise,
                mode,
                reference,
                bank,
                instrument_date: instrumentDate || null,
                note,
              },
              { onSuccess: setDone },
            );
          }}
        >
          {err && !err.field && <div className="form-error">{err.message}</div>}
          <div className="field">
            <label htmlFor="col-amount">Amount received</label>
            <AmountInput id="col-amount" value={amount} onChange={setAmount} required />
            <div className="quick-amounts">
              {quick.map(([label, value]) => (
                <button key={label} type="button" className="chip" onClick={() => setAmount(paiseToInput(value))}>
                  {label}: {formatPaise(value)}
                </button>
              ))}
            </div>
            {err?.field === "amount" && <span className="field-error">{err.message}</span>}
          </div>
          <div className="field">
            <span className="field-label">Payment mode</span>
            <div className="mode-picker" role="radiogroup" aria-label="Payment mode">
              {MODES.map(([value, label]) => (
                <label key={value} className={mode === value ? "selected" : ""}>
                  <input type="radio" name="mode" value={value} checked={mode === value} onChange={() => setMode(value)} />
                  {label}
                </label>
              ))}
            </div>
          </div>
          {mode !== "cash" && (
            <div className="field-row">
              <div className="field">
                <label htmlFor="col-ref">{mode === "upi" ? "UPI transaction ID" : mode === "cheque" ? "Cheque number" : mode === "dd" ? "DD number" : mode === "card" ? "Card slip / approval code" : "UTR / reference"}</label>
                <input id="col-ref" value={reference} onChange={(e) => setReference(e.target.value)} required />
                {err?.field === "reference" && <span className="field-error">{err.message}</span>}
              </div>
              {(mode === "cheque" || mode === "dd" || mode === "bank_transfer") && (
                <div className="field">
                  <label htmlFor="col-bank">Bank</label>
                  <input id="col-bank" value={bank} onChange={(e) => setBank(e.target.value)} required={mode !== "bank_transfer"} />
                  {err?.field === "bank" && <span className="field-error">{err.message}</span>}
                </div>
              )}
              {(mode === "cheque" || mode === "dd") && (
                <div className="field">
                  <label htmlFor="col-date">{mode === "cheque" ? "Cheque date" : "DD date"}</label>
                  <input id="col-date" type="date" value={instrumentDate} onChange={(e) => setInstrumentDate(e.target.value)} />
                </div>
              )}
            </div>
          )}
          <div className="field">
            <label htmlFor="col-note">Note (optional)</label>
            <input id="col-note" value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
          <div className="modal-actions">
            <button type="submit" className="btn btn-primary" disabled={collect.isPending || !paise}>
              {collect.isPending ? "Saving…" : paise ? `Receive ${formatPaise(paise)} and issue receipt` : "Issue receipt"}
            </button>
          </div>
        </form>
      )}
    </>
  );
}

function Done({ receipt }: { receipt: Receipt }) {
  const email = useEmailReceipt();
  return (
    <div className="card done-card" role="status">
      <div className="eyebrow">Receipt issued</div>
      <h1>{receipt.number}</h1>
      <p>
        <MoneyText paise={receipt.amount} /> from <b>{receipt.student.name}</b> ({receipt.student.prn}) by {receipt.mode_label}
        {receipt.reference ? ` · ${receipt.reference}` : ""}
      </p>
      <table className="mini-table">
        <tbody>
          {receipt.lines.map((l) => (
            <tr key={l.code}>
              <td>{l.name}</td>
              <td className="num">
                <MoneyText paise={l.amount} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="row-actions done-actions">
        <a className="btn btn-primary" href={receiptPdfUrl(receipt.id)} target="_blank" rel="noreferrer">
          Print receipt
        </a>
        <button type="button" className="btn btn-ghost" disabled={email.isPending || email.isSuccess} onClick={() => email.mutate(receipt.id)}>
          {email.isSuccess ? `Emailed to ${email.data.sent_to}` : "Email to student"}
        </button>
        <Link className="btn btn-ghost" to="/app/fees">
          Next student
        </Link>
      </div>
      {email.error && <p className="form-error">{email.error.message}</p>}
    </div>
  );
}

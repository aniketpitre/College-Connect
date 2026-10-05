import { useState } from "react";
import LanguageToggle from "../../app/LanguageToggle";
import { EmptyState } from "../../components/EmptyState";
import { MoneyText } from "../../components/MoneyText";
import { StatusBadge } from "../../components/StatusBadge";
import { PORTAL_STRINGS } from "../../i18n/portal";
import { ApiError } from "../../lib/api";
import { useLanguage } from "../../lib/language";
import { formatPaise } from "../../lib/money";
import { myReceiptPdf, myStatementPdf, useMyFees } from "../../lib/portal";
import "../fees/fees.css";
import "./portal.css";

/** Student's own fees (spec R13 "Fees"), in their language. */
export default function MyFeesPage() {
  const [language, setLanguage] = useLanguage();
  const t = PORTAL_STRINGS[language];
  const [yearId, setYearId] = useState<string | undefined>();
  const fees = useMyFees(yearId);
  const f = fees.data;
  const locale = language === "en" ? "en-IN" : `${language}-IN`;
  const day = (iso: string) => new Date(iso.length === 10 ? `${iso}T00:00:00` : iso).toLocaleDateString(locale, { day: "numeric", month: "short", year: "numeric" });
  const balances = (f?.entries ?? []).reduce<number[]>((acc, e) => [...acc, (acc.at(-1) ?? 0) + e.amount], []);

  return (
    <div lang={language}>
      <div className="page-head">
        <h1>{t.feesTitle}</h1>
        <div className="row-actions">
          {f && f.years.length > 1 && (
            <select aria-label={t.year} className="year-select" value={f.academic_year_id} onChange={(e) => setYearId(e.target.value)}>
              {f.years.map((y) => (
                <option key={y.id} value={y.id}>
                  {y.name}
                </option>
              ))}
            </select>
          )}
          <LanguageToggle value={language} onChange={setLanguage} />
        </div>
      </div>
      {fees.error && (fees.error instanceof ApiError && fees.error.code === "no_fees" ? <EmptyState title={t.noFees} /> : <p className="form-error">{fees.error.message}</p>)}
      {f && (
        <>
          {!f.has_demand && <p className="muted">{t.noFees}</p>}
          <div className="tiles fee-tiles">
            <div className="tile">
              <div className="tile-label">{t.totalFee}</div>
              <div className="tile-value" style={{ fontSize: "1.4rem" }}>
                <MoneyText paise={f.demand + f.charges} />
              </div>
            </div>
            <div className="tile">
              <div className="tile-label">{t.paid}</div>
              <div className="tile-value" style={{ fontSize: "1.4rem" }}>
                <MoneyText paise={f.paid} />
              </div>
            </div>
            {f.concessions + f.scholarships > 0 && (
              <div className="tile">
                <div className="tile-label">{t.concessionsScholarships}</div>
                <div className="tile-value" style={{ fontSize: "1.4rem" }}>
                  <MoneyText paise={f.concessions + f.scholarships} />
                </div>
              </div>
            )}
            <div className={`tile${f.overdue > 0 ? " tile-warn" : ""}`}>
              <div className="tile-label">{f.balance >= 0 ? t.balanceDue : t.inCredit}</div>
              <div className="tile-value">
                <MoneyText paise={Math.abs(f.balance)} />
              </div>
              {f.overdue > 0 && <div className="field-error">{formatPaise(f.overdue)} {t.overdue}</div>}
            </div>
          </div>

          {f.installments.length > 0 && (
            <section className="card">
              <h2 className="card-title">{t.installments}</h2>
              <ul className="inst-list">
                {f.installments.map((i) => (
                  <li key={i.label}>
                    <div>
                      <b>{i.label}</b>
                      <div className="muted small">{t.dueBy(day(i.due_date))}</div>
                    </div>
                    <div className="inst-right">
                      <MoneyText paise={i.amount} />
                      {i.due === 0 ? (
                        <StatusBadge tone="success">{t.paidLabel}</StatusBadge>
                      ) : (
                        <StatusBadge tone={i.overdue ? "danger" : "warning"}>
                          {formatPaise(i.due)} {i.overdue ? t.overdue : t.due}
                        </StatusBadge>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className="card">
            <h2 className="card-title">{t.receipts}</h2>
            {f.receipts.length === 0 ? (
              <p className="muted">{t.noReceipts}</p>
            ) : (
              <ul className="inst-list">
                {f.receipts.map((r) => (
                  <li key={r.id}>
                    <div>
                      <b className="mono-link">{r.number}</b>
                      <div className="muted small">
                        {day(r.collected_at)} · {r.mode_label}
                      </div>
                    </div>
                    <div className="inst-right">
                      <MoneyText paise={r.amount} />
                      {r.status === "cancelled" ? (
                        <StatusBadge tone="danger">{t.cancelled}</StatusBadge>
                      ) : (
                        <a className="link-btn" href={myReceiptPdf(r.id)} target="_blank" rel="noreferrer">
                          {t.download}
                        </a>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <div className="section-head">
            <h2 className="subhead">{t.statement}</h2>
            <a className="btn btn-ghost btn-sm" href={myStatementPdf(f.academic_year_id)} target="_blank" rel="noreferrer">
              {t.statementPdf}
            </a>
          </div>
          <div className="data-table-scroll">
            <table className="statement">
              <thead>
                <tr>
                  <th>{t.date}</th>
                  <th>{t.entry}</th>
                  <th className="num">{t.charged}</th>
                  <th className="num">{t.credited}</th>
                  <th className="num">{t.balance}</th>
                </tr>
              </thead>
              <tbody>
                {f.entries.map((e, i) => (
                  <tr key={e.id} className={e.reversed ? "reversed" : ""}>
                    <td className="nowrap">{day(e.at)}</td>
                    <td>
                      {t.entryLabels[e.type] ?? e.label}
                      {e.receipt_number ? ` · ${e.receipt_number}` : ""}
                    </td>
                    <td className="num">{e.amount > 0 ? <MoneyText paise={e.amount} /> : ""}</td>
                    <td className="num">{e.amount < 0 ? <MoneyText paise={-e.amount} /> : ""}</td>
                    <td className="num">
                      <MoneyText paise={balances[i]} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

import { useState } from "react";
import LanguageToggle from "../../app/LanguageToggle";
import { EmptyState } from "../../components/EmptyState";
import { StatusBadge } from "../../components/StatusBadge";
import { CAMPUS_STRINGS } from "../../i18n/campus";
import { hasPermission, useMe } from "../../lib/auth";
import {
  isbnLookup,
  useAddBook,
  useBooks,
  useCancelReservation,
  useIssue,
  useLibraryOverview,
  useLoans,
  useLost,
  useMyLibrary,
  useRenewMine,
  useReserve,
  useReturn,
  type Loan,
} from "../../lib/campus";
import { useLanguage } from "../../lib/language";
import { formatPaise, parseRupees } from "../../lib/money";
import "./campus.css";

export default function LibraryPage() {
  const { data: me } = useMe();
  return me?.kind === "student" ? <MyLibrary /> : <LibraryDesk canManage={hasPermission(me, "library.manage")} />;
}

function MyLibrary() {
  const [language, setLanguage] = useLanguage();
  const t = CAMPUS_STRINGS[language].library;
  const mine = useMyLibrary();
  const renew = useRenewMine();
  const cancel = useCancelReservation();
  const reserve = useReserve();
  const [q, setQ] = useState("");
  const books = useBooks(q);
  const locale = language === "en" ? "en-IN" : `${language}-IN`;
  const day = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(locale, { day: "numeric", month: "short" });
  const m = mine.data;
  const error = renew.error ?? cancel.error ?? reserve.error;
  return (
    <div lang={language}>
      <div className="page-head">
        <h1>{t.title}</h1>
        <LanguageToggle value={language} onChange={setLanguage} />
      </div>
      {m && <p className="muted">{t.rules(m.rules.loan_days, m.rules.max_books, formatPaise(m.rules.fine_per_day))}</p>}
      {error && <p className="form-error">{error.message}</p>}
      <h2 className="subhead">{t.myBooks}</h2>
      {m && m.loans.length === 0 && <p className="muted">{t.none}</p>}
      <ul className="campus-list">
        {m?.loans.map((l) => (
          <li key={l.id} className={l.days_late ? "late" : ""}>
            <div>
              <b>{l.title}</b>
              <div className="muted small">
                {t.due(day(l.due_date))}
                {l.days_late > 0 && ` · ${t.late(l.days_late, formatPaise(l.fine_so_far))}`}
              </div>
            </div>
            {l.days_late === 0 && l.renewals < (m?.rules.max_renewals ?? 0) && (
              <button type="button" className="btn btn-ghost btn-sm" disabled={renew.isPending} onClick={() => renew.mutate(l.id)}>
                {t.renew}
              </button>
            )}
          </li>
        ))}
      </ul>
      {m && m.reservations.length > 0 && (
        <>
          <h2 className="subhead">{t.reservations}</h2>
          <ul className="campus-list">
            {m.reservations.map((r) => (
              <li key={r.id}>
                <div>
                  <b>{r.title}</b>
                  <div className="muted small">{r.status === "ready" && r.ready_until ? t.ready(day(r.ready_until)) : t.position(r.position)}</div>
                </div>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => cancel.mutate(r.id)}>
                  {t.cancel}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      <h2 className="subhead">{t.search}</h2>
      <input className="campus-search" aria-label={t.search} placeholder={t.searchHint} value={q} onChange={(e) => setQ(e.target.value)} />
      <ul className="campus-list">
        {books.data?.map((b) => (
          <li key={b.id}>
            <div>
              <b>{b.title}</b>
              <div className="muted small">
                {b.authors.join(", ")} · {t.available(b.available, b.copies)}
              </div>
            </div>
            {b.available === 0 && b.copies > 0 && !m?.reservations.some((r) => r.book_id === b.id) && (
              <button type="button" className="btn btn-ghost btn-sm" disabled={reserve.isPending} onClick={() => reserve.mutate(b.id)}>
                {t.reserve}
              </button>
            )}
          </li>
        ))}
      </ul>
      {m && m.history.length > 0 && (
        <>
          <h2 className="subhead">{t.history}</h2>
          <ul className="campus-list">
            {m.history.map((l) => (
              <li key={l.id}>
                <div>
                  <b>{l.title}</b>
                  <div className="muted small">
                    {l.returned_on && day(l.returned_on)}
                    {l.fine > 0 && ` · ${t.fine(formatPaise(l.fine))}`}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function LoanRow({ l, canManage }: { l: Loan; canManage: boolean }) {
  const lost = useLost();
  return (
    <tr>
      <td>
        {l.student?.name}
        <div className="muted small">{l.student?.prn}</div>
      </td>
      <td>
        {l.title}
        <div className="muted small">{l.barcode}</div>
      </td>
      <td>{l.status === "open" ? l.due_date : (l.returned_on ?? "")}</td>
      <td>{l.status === "open" ? (l.days_late ? <StatusBadge tone="danger">{l.days_late} days late</StatusBadge> : "On time") : l.fine ? formatPaise(l.fine) : "—"}</td>
      <td>
        {canManage && l.status === "open" && l.days_late > 0 && (
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => {
              const price = parseRupees(window.prompt("Book lost: charge the student how much (₹)?") ?? "");
              if (price !== null) lost.mutate({ id: l.id, price });
            }}
          >
            Lost…
          </button>
        )}
      </td>
    </tr>
  );
}

function LibraryDesk({ canManage }: { canManage: boolean }) {
  const overview = useLibraryOverview();
  const [tab, setTab] = useState<"desk" | "open" | "overdue" | "returned" | "catalogue">("desk");
  const [q, setQ] = useState("");
  const loans = useLoans(tab === "desk" || tab === "catalogue" ? "open" : tab, q);
  const o = overview.data;
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Library</div>
          <h1>Circulation desk</h1>
        </div>
      </div>
      {o && (
        <div className="tiles fee-tiles">
          {(
            [
              ["Titles", o.titles],
              ["Copies", o.copies],
              ["Issued", o.issued],
              ["Overdue", o.overdue],
              ["Reservations", o.reservations],
            ] as const
          ).map(([label, n]) => (
            <div className={`tile${label === "Overdue" && n ? " tile-warn" : ""}`} key={label}>
              <div className="tile-label">{label}</div>
              <div className="tile-value">{n}</div>
            </div>
          ))}
        </div>
      )}
      <div className="tabs" role="tablist">
        {(
          [
            ["desk", "Issue / return"],
            ["open", "On loan"],
            ["overdue", "Overdue"],
            ["returned", "Returned"],
            ["catalogue", "Catalogue"],
          ] as const
        ).map(([k, label]) => (
          <button key={k} type="button" role="tab" aria-selected={tab === k} className={tab === k ? "active" : ""} onClick={() => setTab(k)}>
            {label}
          </button>
        ))}
      </div>
      {tab === "desk" && canManage && <Desk fine={o?.settings.fine_per_day ?? 0} />}
      {tab === "catalogue" && <Catalogue canManage={canManage} />}
      {["open", "overdue", "returned"].includes(tab) && (
        <>
          <input className="campus-search" aria-label="Student PRN" placeholder="Filter by PRN" value={q} onChange={(e) => setQ(e.target.value)} />
          {loans.data?.length === 0 && <EmptyState title="Nothing here" />}
          {loans.data && loans.data.length > 0 && (
            <div className="data-table data-table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Student</th>
                    <th>Book</th>
                    <th>{tab === "returned" ? "Returned" : "Due"}</th>
                    <th>{tab === "returned" ? "Fine" : "State"}</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {loans.data.map((l) => (
                    <LoanRow key={l.id} l={l} canManage={canManage} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </>
  );
}

function Desk({ fine }: { fine: number }) {
  const issue = useIssue();
  const ret = useReturn();
  const [barcode, setBarcode] = useState("");
  const [prn, setPrn] = useState("");
  const [back, setBack] = useState("");
  const last = issue.data;
  const returned = ret.data;
  return (
    <div className="campus-grid">
      <form
        className="card"
        onSubmit={(e) => {
          e.preventDefault();
          issue.mutate({ barcode, prn }, { onSuccess: () => setBarcode("") });
        }}
      >
        <h2 className="card-title">Issue</h2>
        <div className="field">
          <label htmlFor="is-prn">Student PRN</label>
          <input id="is-prn" value={prn} onChange={(e) => setPrn(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="is-bc">Book barcode (scan)</label>
          <input id="is-bc" value={barcode} onChange={(e) => setBarcode(e.target.value)} required />
        </div>
        {issue.error && <p className="form-error">{issue.error.message}</p>}
        {last && (
          <p className="small" role="status">
            Issued “{last.title}” to {last.student?.name}, due {last.due_date}.
          </p>
        )}
        <button type="submit" className="btn btn-primary" disabled={issue.isPending}>
          Issue book
        </button>
      </form>
      <form
        className="card"
        onSubmit={(e) => {
          e.preventDefault();
          ret.mutate(back, { onSuccess: () => setBack("") });
        }}
      >
        <h2 className="card-title">Return</h2>
        <div className="field">
          <label htmlFor="rt-bc">Book barcode (scan)</label>
          <input id="rt-bc" value={back} onChange={(e) => setBack(e.target.value)} required />
        </div>
        <p className="muted small">Late returns are fined {formatPaise(fine)} a day, added to the student's fees.</p>
        {ret.error && <p className="form-error">{ret.error.message}</p>}
        {returned && (
          <p className="small" role="status">
            “{returned.title}” returned by {returned.student?.name}
            {returned.fine ? `: fine ${formatPaise(returned.fine)} added to fees` : ", on time"}.{returned.held_for_reservation ? " Keep it aside: it is reserved." : ""}
          </p>
        )}
        <button type="submit" className="btn btn-primary" disabled={ret.isPending}>
          Return book
        </button>
      </form>
    </div>
  );
}

function Catalogue({ canManage }: { canManage: boolean }) {
  const [q, setQ] = useState("");
  const books = useBooks(q);
  const add = useAddBook();
  const [form, setForm] = useState({ isbn: "", title: "", authors: "", publisher: "", year: "", subject: "", copies: "1" });
  const [looking, setLooking] = useState(false);
  return (
    <>
      {canManage && (
        <form
          className="card"
          onSubmit={(e) => {
            e.preventDefault();
            add.mutate(
              {
                isbn: form.isbn || undefined,
                title: form.title,
                authors: form.authors.split(",").map((a) => a.trim()).filter(Boolean),
                publisher: form.publisher,
                year: form.year ? Number(form.year) : undefined,
                subject: form.subject,
                copies: Number(form.copies),
              },
              { onSuccess: () => setForm({ isbn: "", title: "", authors: "", publisher: "", year: "", subject: "", copies: "1" }) },
            );
          }}
        >
          <h2 className="card-title">Add a book</h2>
          <div className="campus-grid">
            <div className="field">
              <label htmlFor="bk-isbn">ISBN</label>
              <div className="row-actions" style={{ justifyContent: "flex-start" }}>
                <input id="bk-isbn" value={form.isbn} onChange={(e) => setForm({ ...form, isbn: e.target.value })} />
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  disabled={!form.isbn || looking}
                  onClick={async () => {
                    setLooking(true);
                    const r = await isbnLookup(form.isbn).catch(() => ({ found: false }) as { found: boolean });
                    setLooking(false);
                    if ("title" in r && r.found)
                      setForm({ ...form, title: r.title ?? "", authors: (r.authors ?? []).join(", "), publisher: r.publisher ?? "", year: r.year ? String(r.year) : "", subject: r.subject ?? "" });
                  }}
                >
                  {looking ? "Looking up…" : "Look up"}
                </button>
              </div>
            </div>
            {(
              [
                ["title", "Title"],
                ["authors", "Authors (comma-separated)"],
                ["publisher", "Publisher"],
                ["year", "Year"],
                ["subject", "Subject"],
                ["copies", "Copies"],
              ] as const
            ).map(([k, label]) => (
              <div className="field" key={k}>
                <label htmlFor={`bk-${k}`}>{label}</label>
                <input id={`bk-${k}`} value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} required={k === "title"} />
              </div>
            ))}
          </div>
          {add.error && <p className="form-error">{add.error.message}</p>}
          {add.data && <p className="small">Added “{add.data.title}”: barcodes {add.data.copy_list?.map((c) => c.barcode).join(", ")}.</p>}
          <button type="submit" className="btn btn-primary" disabled={add.isPending}>
            Add book
          </button>
        </form>
      )}
      <input className="campus-search" aria-label="Search the catalogue" placeholder="Title, author or ISBN" value={q} onChange={(e) => setQ(e.target.value)} />
      <ul className="campus-list">
        {books.data?.map((b) => (
          <li key={b.id}>
            <div>
              <b>{b.title}</b>
              <div className="muted small">
                {b.authors.join(", ")}
                {b.isbn && ` · ISBN ${b.isbn}`} · {b.available}/{b.copies} on the shelf{b.waiting ? ` · ${b.waiting} waiting` : ""}
              </div>
              <div className="muted small">{b.copy_list?.map((c) => `${c.barcode} (${c.status})`).join(", ")}</div>
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}

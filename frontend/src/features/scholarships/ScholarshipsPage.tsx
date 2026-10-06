import { useState } from "react";
import { Link } from "react-router";
import LanguageToggle from "../../app/LanguageToggle";
import { EmptyState } from "../../components/EmptyState";
import { StatusBadge, type Tone } from "../../components/StatusBadge";
import { SCHOLARSHIP_STRINGS } from "../../i18n/scholarships";
import { STUDENT_STRINGS } from "../../i18n/student";
import { hasPermission, useMe } from "../../lib/auth";
import { useLanguage } from "../../lib/language";
import { useCandidates, useDeclareIncome, useMyScholarshipCheck, useSaveScheme, useSchemes, type Scheme, type SchemeResult } from "../../lib/scholarshipCheck";
import "../campus/campus.css";

const TONE: Record<SchemeResult["status"], Tone> = {
  likely: "success",
  missing_documents: "warning",
  check: "info",
  applied: "neutral",
  not_eligible: "neutral",
};

export default function ScholarshipsPage() {
  const { data: me } = useMe();
  if (me?.kind === "student" || me?.kind === "parent") return <MyScholarships canDeclare={me.kind === "student"} />;
  return <SchemesDesk canManage={hasPermission(me, "fees.manage")} />;
}

function MyScholarships({ canDeclare }: { canDeclare: boolean }) {
  const [language, setLanguage] = useLanguage();
  const t = SCHOLARSHIP_STRINGS[language];
  const docs = STUDENT_STRINGS[language].docTypes;
  const check = useMyScholarshipCheck();
  const declare = useDeclareIncome();
  const [income, setIncome] = useState("");
  const locale = language === "en" ? "en-IN" : `${language}-IN`;
  const d = check.data;
  if (check.error) return <p className="form-error">{check.error.message}</p>;
  if (!d) return null;
  return (
    <div lang={language}>
      <div className="page-head">
        <h1>{t.title}</h1>
        <LanguageToggle value={language} onChange={setLanguage} />
      </div>
      <p className="muted">{t.intro}</p>
      {canDeclare && (
        <form
          className="card campus-form"
          onSubmit={(e) => {
            e.preventDefault();
            declare.mutate(Number(income), { onSuccess: () => setIncome("") });
          }}
        >
          <div className="field">
            <label htmlFor="sch-income">{t.income}</label>
            <input id="sch-income" type="number" min={0} value={income} onChange={(e) => setIncome(e.target.value)} required />
            <span className="small muted">{t.incomeHint}</span>
          </div>
          <div>
            <button type="submit" className="btn btn-primary" disabled={declare.isPending}>
              {t.save}
            </button>
          </div>
          {d.family_income !== null && <p className="small">{t.declared(`₹${d.family_income.toLocaleString(locale)}`)}</p>}
        </form>
      )}
      {d.schemes.map((s) => (
        <section key={s.code} className="card scheme-card">
          <div className="staff-head" style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
            <div>
              <b>{s.name}</b>
              <div className="small muted">{s.portal}</div>
            </div>
            <StatusBadge tone={TONE[s.status]}>{t.statuses[s.status]}</StatusBadge>
          </div>
          {s.status === "applied" && s.application_status && (
            <p className="small">
              {t.applied} {s.application_status}
            </p>
          )}
          {s.failed.length > 0 && (
            <ul className="small">
              {s.failed.map((f) => (
                <li key={f.rule}>{t.notMet[f.rule]?.(f) ?? f.rule}</li>
              ))}
            </ul>
          )}
          {s.status !== "not_eligible" && s.unknown.length > 0 && (
            <ul className="small">
              {s.unknown.map((u) => (
                <li key={u}>{t.unknown[u] ?? u}</li>
              ))}
            </ul>
          )}
          {s.status !== "not_eligible" && s.status !== "applied" && s.missing_documents.length > 0 && (
            <p className="small">
              {t.upload} {s.missing_documents.map((x) => docs[x] ?? x).join(", ")} · <Link to="/app/profile">{t.uploadLink}</Link>
            </p>
          )}
          {s.status === "likely" && s.link && (
            <a className="btn btn-primary btn-sm" href={s.link} target="_blank" rel="noreferrer">
              {t.apply(s.portal)}
            </a>
          )}
        </section>
      ))}
      <p className="small muted">{t.disclaimer}</p>
    </div>
  );
}

const STATUS_EN = SCHOLARSHIP_STRINGS.en.statuses;
const DOCS_EN = STUDENT_STRINGS.en.docTypes;

function SchemesDesk({ canManage }: { canManage: boolean }) {
  const schemes = useSchemes();
  const [code, setCode] = useState("");
  const [editing, setEditing] = useState<Scheme | null>(null);
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Accounts</div>
          <h1>Scholarship schemes</h1>
        </div>
      </div>
      <p className="small muted">
        Students see which of these they may qualify for. Limits change every year: check them against the portal and update them here.
      </p>
      <ul className="campus-list">
        {schemes.data?.map((s) => (
          <li key={s.code}>
            <div>
              <b>{s.name}</b>
              <div className="small muted">
                {s.portal} · {s.categories.length ? s.categories.join(", ") : "any category"}
                {s.income_limit !== null && ` · income up to ₹${s.income_limit.toLocaleString("en-IN")}`}
                {s.min_previous_percentage !== null && ` · ${s.min_previous_percentage}% in the previous exam`}
                {!s.active && " · switched off"}
              </div>
            </div>
            <span className="row-actions">
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setCode(s.code)}>
                Who may qualify
              </button>
              {canManage && (
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditing(s)}>
                  Edit
                </button>
              )}
            </span>
          </li>
        ))}
      </ul>
      {editing && <SchemeForm scheme={editing} onDone={() => setEditing(null)} />}
      {code && <Candidates code={code} name={schemes.data?.find((s) => s.code === code)?.name ?? code} />}
    </>
  );
}

function SchemeForm({ scheme, onDone }: { scheme: Scheme; onDone: () => void }) {
  const save = useSaveScheme();
  const [s, setS] = useState(scheme);
  const num = (v: string) => (v === "" ? null : Number(v));
  return (
    <form
      className="card campus-form"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate(s, { onSuccess: onDone });
      }}
    >
      <h2 className="card-title" style={{ gridColumn: "1 / -1" }}>
        {scheme.name}
      </h2>
      <div className="field">
        <label htmlFor="sc-cats">Categories (comma-separated codes, empty for any)</label>
        <input
          id="sc-cats"
          value={s.categories.join(", ")}
          onChange={(e) =>
            setS({
              ...s,
              categories: e.target.value
                .split(",")
                .map((x) => x.trim())
                .filter(Boolean),
            })
          }
        />
      </div>
      <div className="field">
        <label htmlFor="sc-income">Family income limit (₹ a year)</label>
        <input id="sc-income" type="number" value={s.income_limit ?? ""} onChange={(e) => setS({ ...s, income_limit: num(e.target.value) })} />
      </div>
      <div className="field">
        <label htmlFor="sc-pct">Minimum % in the previous exam</label>
        <input
          id="sc-pct"
          type="number"
          value={s.min_previous_percentage ?? ""}
          onChange={(e) => setS({ ...s, min_previous_percentage: num(e.target.value) })}
        />
      </div>
      <div className="field">
        <label htmlFor="sc-att">Minimum attendance %</label>
        <input id="sc-att" type="number" value={s.min_attendance ?? ""} onChange={(e) => setS({ ...s, min_attendance: num(e.target.value) })} />
      </div>
      <div className="field">
        <label htmlFor="sc-link">Portal link</label>
        <input id="sc-link" value={s.link ?? ""} onChange={(e) => setS({ ...s, link: e.target.value || null })} />
      </div>
      <label className="check-label">
        <input type="checkbox" checked={s.active} onChange={(e) => setS({ ...s, active: e.target.checked })} /> Shown to students
      </label>
      {save.error && <p className="form-error">{save.error.message}</p>}
      <div className="row-actions" style={{ justifyContent: "flex-start" }}>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onDone}>
          Cancel
        </button>
        <button type="submit" className="btn btn-primary btn-sm" disabled={save.isPending}>
          Save
        </button>
      </div>
    </form>
  );
}

function Candidates({ code, name }: { code: string; name: string }) {
  const list = useCandidates(code);
  return (
    <section className="card">
      <h2 className="card-title">Who may qualify and hasn't applied: {name}</h2>
      {list.data?.students.length === 0 && <EmptyState title="Nobody yet" />}
      <ul className="campus-list">
        {list.data?.students.map((c) => (
          <li key={c.student_id}>
            <div>
              <Link to={`/app/students/${c.student_id}`}>
                {c.name} ({c.prn})
              </Link>
              <div className="small muted">
                {c.missing_documents.length > 0 && `Missing: ${c.missing_documents.map((d) => DOCS_EN[d] ?? d).join(", ")}`}
                {c.unknown.length > 0 && ` Not known: ${c.unknown.join(", ")}`}
              </div>
            </div>
            <StatusBadge tone={TONE[c.status]}>{STATUS_EN[c.status]}</StatusBadge>
          </li>
        ))}
      </ul>
    </section>
  );
}

import { useState } from "react";
import { AmountInput } from "../../components/AmountInput";
import { DataTable } from "../../components/DataTable";
import { MoneyText } from "../../components/MoneyText";
import { Modal } from "../../components/Modal";
import { StatusBadge } from "../../components/StatusBadge";
import { ApiError } from "../../lib/api";
import { hasPermission, useMe } from "../../lib/auth";
import { useCreateHead, useFeeHeads, useGenerateDemands, useSaveStructure, useStarterHeads, useStructures, type DemandPlan, type FeeHead, type FeeStructure } from "../../lib/fees";
import { formatPaise, paiseToInput, parseRupees } from "../../lib/money";
import { useSetup, type SetupOverview } from "../../lib/setup";
import "./fees.css";

/** Accounts screen (English): fee heads, fee structures per class and category, and charging the year's fees. */
export default function FeeSetupPage() {
  const { data: me } = useMe();
  const setup = useSetup();
  const heads = useFeeHeads();
  const canManage = hasPermission(me, "fees.manage");
  const [yearId, setYearId] = useState<string>("");
  const year = yearId || setup.data?.current_year?.id || "";
  const structures = useStructures(year || undefined);
  const [editing, setEditing] = useState<FeeStructure | "new" | null>(null);
  const [tab, setTab] = useState<"structures" | "heads" | "charge">("structures");

  if (!setup.data) return <p className="muted">Loading…</p>;
  const s = setup.data;
  const headName = (id: string) => heads.data?.find((h) => h.id === id)?.code ?? "?";
  const className = (st: FeeStructure) => {
    const p = s.programmes.find((x) => x.id === st.programme_id);
    return `${p?.code ?? "?"} ${p?.year_labels[st.year_of_study - 1] ?? st.year_of_study}`;
  };
  const category = (id: string | null) => (id ? (s.categories.find((c) => c.id === id)?.code ?? "?") : "All other categories");

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Accounts</div>
          <h1>Fee setup</h1>
        </div>
        <select aria-label="Academic year" value={year} onChange={(e) => setYearId(e.target.value)} className="year-select">
          {s.academic_years.map((y) => (
            <option key={y.id} value={y.id}>
              {y.name}
              {y.is_current ? " (current)" : ""}
            </option>
          ))}
        </select>
      </div>
      {!year && <p className="form-error">Add an academic year in College setup first.</p>}

      <div className="tabs" role="tablist">
        {(
          [
            ["structures", "Fee structures"],
            ["charge", "Charge the year's fees"],
            ["heads", "Fee heads"],
          ] as const
        ).map(([k, label]) => (
          <button key={k} type="button" role="tab" aria-selected={tab === k} className={tab === k ? "active" : ""} onClick={() => setTab(k)}>
            {label}
          </button>
        ))}
      </div>

      {tab === "heads" && <HeadsTab heads={heads.data ?? []} canManage={canManage} />}

      {tab === "structures" && (
        <>
          <div className="section-head">
            <p className="muted">One structure per class (programme + year) and category for the year. "All other categories" covers students without their own.</p>
            {canManage && (
              <button type="button" className="btn btn-primary btn-sm" onClick={() => setEditing("new")} disabled={!heads.data?.length}>
                Add structure
              </button>
            )}
          </div>
          {!heads.data?.length && <p className="muted">Add fee heads first (Fee heads tab).</p>}
          <div className="structure-grid">
            {(structures.data ?? []).map((st) => (
              <div className="card structure-card" key={st.id}>
                <div className="structure-head">
                  <div>
                    <b>{className(st)}</b> · {category(st.category_id)}
                    <div className="muted">{st.name}</div>
                  </div>
                  {st.locked ? <StatusBadge tone="info">In use</StatusBadge> : canManage && (
                    <button type="button" className="link-btn" onClick={() => setEditing(st)}>
                      Edit
                    </button>
                  )}
                </div>
                <table className="mini-table">
                  <tbody>
                    {st.items.map((i) => (
                      <tr key={i.head_id}>
                        <td>{headName(i.head_id)}</td>
                        <td className="num">
                          <MoneyText paise={i.amount} />
                        </td>
                      </tr>
                    ))}
                    <tr className="total-row">
                      <td>Total</td>
                      <td className="num">
                        <MoneyText paise={st.total} />
                      </td>
                    </tr>
                  </tbody>
                </table>
                <div className="muted small">
                  {st.installments.map((i) => `${i.label}: ${formatPaise(i.amount)} by ${new Date(i.due_date).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}`).join(" · ")}
                  {st.late_fee ? ` · Late fee ${formatPaise(st.late_fee)} per installment` : ""}
                </div>
              </div>
            ))}
          </div>
          {structures.data?.length === 0 && <p className="muted">No fee structures for this year yet.</p>}
        </>
      )}

      {tab === "charge" && year && <ChargeTab setup={s} yearId={year} canManage={canManage} />}

      {editing && <StructureModal setup={s} heads={(heads.data ?? []).filter((h) => h.status === "active")} yearId={year} structure={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </>
  );
}

function HeadsTab({ heads, canManage }: { heads: FeeHead[]; canManage: boolean }) {
  const create = useCreateHead();
  const starter = useStarterHeads();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  return (
    <>
      {canManage && (
        <form
          className="card inline-form"
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate({ code, name }, { onSuccess: () => (setCode(""), setName("")) });
          }}
        >
          <div className="field">
            <label htmlFor="h-code">Code</label>
            <input id="h-code" value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="TUITION" required />
          </div>
          <div className="field">
            <label htmlFor="h-name">Name</label>
            <input id="h-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Tuition fee" required />
          </div>
          <button type="submit" className="btn btn-primary" disabled={create.isPending}>
            Add fee head
          </button>
          {heads.length === 0 && (
            <button type="button" className="btn btn-ghost" onClick={() => starter.mutate()} disabled={starter.isPending}>
              Load common heads
            </button>
          )}
          {create.error && <div className="form-error">{create.error.message}</div>}
        </form>
      )}
      <DataTable
        columns={[
          { key: "code", header: "Code", render: (h: FeeHead) => <b>{h.code}</b>, searchText: (h) => h.code },
          { key: "name", header: "Name", render: (h) => h.name, searchText: (h) => h.name },
        ]}
        rows={heads}
        rowKey={(h) => h.id}
        emptyTitle="No fee heads yet"
      />
    </>
  );
}

interface Row {
  head_id: string;
  amount: string;
}
interface InstRow {
  label: string;
  due_date: string;
  amount: string;
}

function StructureModal({ setup, heads, yearId, structure, onClose }: { setup: SetupOverview; heads: FeeHead[]; yearId: string; structure: FeeStructure | null; onClose: () => void }) {
  const save = useSaveStructure();
  const [programmeId, setProgrammeId] = useState(structure?.programme_id ?? setup.programmes[0]?.id ?? "");
  const [year, setYear] = useState(String(structure?.year_of_study ?? 1));
  const [categoryId, setCategoryId] = useState(structure?.category_id ?? "");
  const [name, setName] = useState(structure?.name ?? "");
  const [rows, setRows] = useState<Row[]>(structure?.items.map((i) => ({ head_id: i.head_id, amount: paiseToInput(i.amount) })) ?? heads.slice(0, 3).map((h) => ({ head_id: h.id, amount: "" })));
  const [insts, setInsts] = useState<InstRow[]>(structure?.installments.map((i) => ({ ...i, amount: paiseToInput(i.amount) })) ?? [{ label: "Full fee", due_date: "", amount: "" }]);
  const [lateFee, setLateFee] = useState(structure ? paiseToInput(structure.late_fee) : "0");
  const programme = setup.programmes.find((p) => p.id === programmeId);
  const total = rows.reduce((t, r) => t + (parseRupees(r.amount) ?? 0), 0);
  const instTotal = insts.reduce((t, r) => t + (parseRupees(r.amount) ?? 0), 0);
  const err = save.error instanceof ApiError ? save.error : null;

  const split = () => {
    const n = insts.length;
    const each = Math.floor(total / n);
    setInsts(insts.map((i, k) => ({ ...i, amount: paiseToInput(k === 0 ? total - each * (n - 1) : each) })));
  };

  return (
    <Modal open title={structure ? "Edit fee structure" : "Add fee structure"} onClose={onClose} wide>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const common = {
            name,
            items: rows.filter((r) => r.head_id).map((r) => ({ head_id: r.head_id, amount: parseRupees(r.amount) ?? 0 })),
            installments: insts.map((i) => ({ label: i.label, due_date: i.due_date, amount: parseRupees(i.amount) ?? 0 })),
            late_fee: parseRupees(lateFee) ?? 0,
          };
          const body = structure ? common : { ...common, academic_year_id: yearId, programme_id: programmeId, year_of_study: Number(year), category_id: categoryId || null };
          save.mutate({ id: structure?.id, body }, { onSuccess: onClose });
        }}
      >
        {err && <div className="form-error">{err.message}</div>}
        {!structure && (
          <div className="field-row">
            <div className="field">
              <label htmlFor="st-prog">Programme</label>
              <select id="st-prog" value={programmeId} onChange={(e) => setProgrammeId(e.target.value)}>
                {setup.programmes.filter((p) => p.status === "active").map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.code}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="st-year">Year</label>
              <select id="st-year" value={year} onChange={(e) => setYear(e.target.value)}>
                {programme?.year_labels.map((l, i) => (
                  <option key={l} value={i + 1}>
                    {l}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="st-cat">Category</label>
              <select id="st-cat" value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
                <option value="">All other categories</option>
                {setup.categories.filter((c) => c.status === "active").map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.code}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}
        <div className="field">
          <label htmlFor="st-name">Name</label>
          <input id="st-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="BCA FY 2026-27 (Open)" required />
        </div>

        <h3 className="form-section">Fee heads</h3>
        {rows.map((r, i) => (
          <div className="line-row" key={i}>
            <select aria-label={`Fee head ${i + 1}`} value={r.head_id} onChange={(e) => setRows(rows.map((x, k) => (k === i ? { ...x, head_id: e.target.value } : x)))}>
              <option value="">Choose…</option>
              {heads.map((h) => (
                <option key={h.id} value={h.id}>
                  {h.code} · {h.name}
                </option>
              ))}
            </select>
            <AmountInput id={`amt-${i}`} label={`Amount ${i + 1}`} value={r.amount} onChange={(v) => setRows(rows.map((x, k) => (k === i ? { ...x, amount: v } : x)))} required />
            <button type="button" className="link-btn" aria-label="Remove" onClick={() => setRows(rows.filter((_, k) => k !== i))}>
              ✕
            </button>
          </div>
        ))}
        <div className="line-foot">
          <button type="button" className="link-btn" onClick={() => setRows([...rows, { head_id: "", amount: "" }])}>
            + Add fee head
          </button>
          <b>Total {formatPaise(total)}</b>
        </div>

        <h3 className="form-section">Installments</h3>
        {insts.map((r, i) => (
          <div className="line-row" key={i}>
            <input aria-label={`Installment ${i + 1} name`} value={r.label} onChange={(e) => setInsts(insts.map((x, k) => (k === i ? { ...x, label: e.target.value } : x)))} required />
            <input aria-label={`Installment ${i + 1} due date`} type="date" value={r.due_date} onChange={(e) => setInsts(insts.map((x, k) => (k === i ? { ...x, due_date: e.target.value } : x)))} required />
            <AmountInput id={`inst-${i}`} label={`Installment ${i + 1} amount`} value={r.amount} onChange={(v) => setInsts(insts.map((x, k) => (k === i ? { ...x, amount: v } : x)))} required />
            <button type="button" className="link-btn" aria-label="Remove installment" onClick={() => setInsts(insts.filter((_, k) => k !== i))} disabled={insts.length === 1}>
              ✕
            </button>
          </div>
        ))}
        <div className="line-foot">
          <span>
            <button type="button" className="link-btn" onClick={() => setInsts([...insts, { label: `Installment ${insts.length + 1}`, due_date: "", amount: "" }])}>
              + Add installment
            </button>{" "}
            <button type="button" className="link-btn" onClick={split}>
              Split equally
            </button>
          </span>
          <span className={instTotal === total ? "muted" : "field-error"}>Installments {formatPaise(instTotal)}</span>
        </div>
        <div className="field narrow-field">
          <label htmlFor="st-late">Late fee per overdue installment</label>
          <AmountInput id="st-late" value={lateFee} onChange={setLateFee} />
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={save.isPending || total <= 0 || instTotal !== total}>
            Save structure
          </button>
        </div>
      </form>
    </Modal>
  );
}

function ChargeTab({ setup, yearId, canManage }: { setup: SetupOverview; yearId: string; canManage: boolean }) {
  const generate = useGenerateDemands();
  const [programmeId, setProgrammeId] = useState(setup.programmes[0]?.id ?? "");
  const [year, setYear] = useState("1");
  const [plan, setPlan] = useState<DemandPlan | null>(null);
  const programme = setup.programmes.find((p) => p.id === programmeId);
  const body = { academic_year_id: yearId, programme_id: programmeId, year_of_study: Number(year) };
  const OUT = { charge: ["Will be charged", "success"], already_charged: ["Already charged", "neutral"], no_structure: ["No fee structure", "danger"] } as const;
  return (
    <>
      <p className="muted">Charges each active student of a class the year's fee from their category's structure. Students already charged are skipped, so it is safe to run again after adding students.</p>
      <div className="filters">
        <select aria-label="Programme" value={programmeId} onChange={(e) => (setProgrammeId(e.target.value), setPlan(null))}>
          {setup.programmes.map((p) => (
            <option key={p.id} value={p.id}>
              {p.code}
            </option>
          ))}
        </select>
        <select aria-label="Year" value={year} onChange={(e) => (setYear(e.target.value), setPlan(null))}>
          {programme?.year_labels.map((l, i) => (
            <option key={l} value={i + 1}>
              {l}
            </option>
          ))}
        </select>
        <button type="button" className="btn btn-primary btn-sm" disabled={generate.isPending} onClick={() => generate.mutate({ ...body, dry_run: true }, { onSuccess: setPlan })}>
          Preview
        </button>
      </div>
      {generate.error && <div className="form-error">{generate.error.message}</div>}
      {plan && (
        <div className="card">
          <div className="section-head">
            <h2>
              {plan.class} · {plan.academic_year}
            </h2>
            <span>
              {plan.dry_run ? `${plan.counts.charge} to charge, ` : `${plan.counts.charge} charged, `}total <MoneyText paise={plan.total} />
            </span>
          </div>
          <ul className="promote-list">
            {plan.students.map((st) => (
              <li key={st.id}>
                <span>
                  {st.name} <span className="muted">· {st.prn}{st.structure ? ` · ${st.structure}` : ""}</span>
                </span>
                <span className="row-actions">
                  {st.amount ? <MoneyText paise={st.amount} /> : null}
                  <StatusBadge tone={OUT[st.outcome][1]}>{OUT[st.outcome][0]}</StatusBadge>
                </span>
              </li>
            ))}
          </ul>
          {plan.dry_run && canManage && plan.counts.charge > 0 && (
            <div className="modal-actions">
              <button type="button" className="btn btn-primary" disabled={generate.isPending} onClick={() => generate.mutate({ ...body, dry_run: false }, { onSuccess: setPlan })}>
                Charge {plan.counts.charge} students
              </button>
            </div>
          )}
        </div>
      )}
    </>
  );
}

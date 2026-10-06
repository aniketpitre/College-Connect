import { useState } from "react";
import { Link } from "react-router";
import { EmptyState } from "../../components/EmptyState";
import { StatusBadge } from "../../components/StatusBadge";
import { hasPermission, useMe } from "../../lib/auth";
import { STATUS_TONE, useApplications, useCycles, useEnquiries, useReport, useRound, useSaveCycle, useSeatInfo, useUpdateEnquiry, type Cycle } from "../../lib/admissions";
import { formatPaise, parseRupees } from "../../lib/money";
import { useSetup } from "../../lib/setup";
import "./admissions.css";

type Tab = "applications" | "merit" | "enquiries" | "report" | "setup";


/** Admission Cell (spec R5): applications and scrutiny, merit rounds, enquiries, the cycle setup and the report. */
export default function AdmissionsPage() {
  const { data: me } = useMe();
  const cycles = useCycles();
  const [cycleId, setCycleId] = useState("");
  const [tab, setTab] = useState<Tab>("applications");
  const canManage = hasPermission(me, "admissions.manage");
  const cycle = cycles.data?.find((c) => c.id === cycleId) ?? cycles.data?.[0];
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Admissions</div>
          <h1>{cycle?.name ?? "Admissions"}</h1>
        </div>
        {cycles.data && cycles.data.length > 1 && (
          <select aria-label="Admission cycle" value={cycle?.id ?? ""} onChange={(e) => setCycleId(e.target.value)}>
            {cycles.data.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        )}
      </div>
      {cycle && (
        <p className="muted">
          <StatusBadge tone={cycle.open_now ? "success" : "neutral"}>{cycle.open_now ? "Open" : cycle.status === "draft" ? "Draft" : "Closed"}</StatusBadge> Last date{" "}
          {cycle.apply_until} · course starts {cycle.course_start} · application fee {formatPaise(cycle.application_fee)} · public page: /apply
        </p>
      )}
      <div className="tabs" role="tablist">
        {(
          [
            ["applications", "Applications"],
            ["merit", "Merit lists"],
            ["enquiries", "Enquiries"],
            ["report", "Report"],
            ["setup", "Setup"],
          ] as const
        ).map(([key, label]) => (
          <button key={key} type="button" role="tab" aria-selected={tab === key} className={tab === key ? "active" : ""} onClick={() => setTab(key)}>
            {label}
          </button>
        ))}
      </div>
      {!cycle && tab !== "setup" && tab !== "enquiries" && <EmptyState title="No admission cycle yet" />}
      {cycle && tab === "applications" && <Applications cycle={cycle} />}
      {cycle && tab === "merit" && <Merit cycle={cycle} canManage={canManage} />}
      {tab === "enquiries" && <Enquiries canManage={canManage} />}
      {cycle && tab === "report" && <ReportTab cycleId={cycle.id} />}
      {tab === "setup" && <SetupTab cycle={cycle} canManage={canManage} />}
    </>
  );
}

function Applications({ cycle }: { cycle: Cycle }) {
  const [f, setF] = useState({ programme_id: "", status: "", q: "" });
  const rows = useApplications({ cycle_id: cycle.id, ...f });
  return (
    <>
      <div className="adm-filters">
        <select aria-label="Programme" value={f.programme_id} onChange={(e) => setF({ ...f, programme_id: e.target.value })}>
          <option value="">All programmes</option>
          {cycle.programmes.map((p) => (
            <option key={p.programme_id} value={p.programme_id}>
              {p.code}
            </option>
          ))}
        </select>
        <select aria-label="Status" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}>
          <option value="">All (submitted)</option>
          {Object.keys(STATUS_TONE).map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <input aria-label="Search" placeholder="Name, number or mobile" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} />
      </div>
      {rows.data?.length === 0 && <EmptyState title="No applications" />}
      {rows.data && rows.data.length > 0 && (
        <div className="data-table data-table-scroll">
          <table>
            <thead>
              <tr>
                <th>No.</th>
                <th>Name</th>
                <th>Programme</th>
                <th>Category</th>
                <th className="num">%</th>
                <th>Fee</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.data.map((r) => (
                <tr key={r.id}>
                  <td>
                    <Link to={`/app/admissions/applications/${r.id}`}>{r.number ?? "—"}</Link>
                  </td>
                  <td>
                    <Link to={`/app/admissions/applications/${r.id}`}>{r.name}</Link>
                    {r.documents_pending > 0 && <div className="muted small">{r.documents_pending} document(s) to check</div>}
                  </td>
                  <td>{r.programme}</td>
                  <td>{r.category}</td>
                  <td className="num">{r.merit_score ?? "–"}</td>
                  <td>{r.fee}</td>
                  <td>
                    <StatusBadge tone={STATUS_TONE[r.status] ?? "neutral"}>{r.status_label}</StatusBadge>
                    {r.rank ? <span className="muted small"> · rank {r.rank}</span> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function Merit({ cycle, canManage }: { cycle: Cycle; canManage: boolean }) {
  const [programmeId, setProgrammeId] = useState(cycle.programmes[0]?.programme_id ?? "");
  const [acceptBy, setAcceptBy] = useState(() => new Date(Date.now() + 5 * 86400_000).toISOString().slice(0, 10));
  const info = useSeatInfo(cycle.id, programmeId);
  const round = useRound(cycle.id);
  const prog = cycle.programmes.find((p) => p.programme_id === programmeId);
  const label = (k: string) => (k === "open" ? "Open" : `${prog?.reserved.find((r) => r.category_id === k)?.code ?? "?"} reserved`);
  const r = round.data;
  return (
    <>
      <div className="adm-filters">
        <select aria-label="Programme" value={programmeId} onChange={(e) => (setProgrammeId(e.target.value), round.reset())}>
          {cycle.programmes.map((p) => (
            <option key={p.programme_id} value={p.programme_id}>
              {p.code} · {p.seats} seats
            </option>
          ))}
        </select>
        <label>
          Confirm by <input type="date" value={acceptBy} onChange={(e) => setAcceptBy(e.target.value)} />
        </label>
        {canManage && (
          <button type="button" className="btn btn-ghost btn-sm" disabled={round.isPending} onClick={() => round.mutate({ programme_id: programmeId, accept_by: acceptBy, dry_run: true })}>
            Preview next round
          </button>
        )}
      </div>
      {info.data && (
        <div className="tiles fee-tiles">
          {Object.entries(info.data.seats.total).map(([k, n]) => (
            <div className="tile" key={k}>
              <div className="tile-label">{label(k)}</div>
              <div className="tile-value">
                {info.data.seats.left[k]} <span className="muted small">of {n} free</span>
              </div>
            </div>
          ))}
        </div>
      )}
      {info.data && info.data.rounds.length > 0 && (
        <p className="muted small">
          Rounds so far: {info.data.rounds.map((x) => `Round ${x.number}: ${x.offers} offers (confirm by ${x.accept_by})`).join(" · ")}
        </p>
      )}
      {round.error && <p className="form-error">{round.error.message}</p>}
      {r && (
        <section className="card">
          <h2 className="card-title">{r.dry_run ? "Preview: nothing is sent yet" : `Round ${r.round} published`}</h2>
          {r.lapsed > 0 && <p className="small">{r.lapsed} earlier offer(s) lapsed.</p>}
          <div className="data-table data-table-scroll">
            <table>
              <thead>
                <tr>
                  <th className="num">Rank</th>
                  <th>Name</th>
                  <th>Category</th>
                  <th className="num">%</th>
                  <th>Seat</th>
                </tr>
              </thead>
              <tbody>
                {r.offers.map((o) => (
                  <tr key={o.application_id}>
                    <td className="num">{o.rank}</td>
                    <td>{o.name}</td>
                    <td>{o.category}</td>
                    <td className="num">{o.merit_score}</td>
                    <td>{o.seat_label}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {r.waiting.length > 0 && <p className="muted small">Waiting list: {r.waiting.map((w) => `${w.rank}. ${w.name} (${w.category})`).join(", ")}</p>}
          {r.dry_run && canManage && r.offers.length > 0 && (
            <button type="button" className="btn btn-primary" disabled={round.isPending} onClick={() => round.mutate({ programme_id: programmeId, accept_by: acceptBy, dry_run: false })}>
              Publish and tell the applicants
            </button>
          )}
        </section>
      )}
    </>
  );
}

function Enquiries({ canManage }: { canManage: boolean }) {
  const [status, setStatus] = useState("new");
  const list = useEnquiries(status);
  const update = useUpdateEnquiry();
  return (
    <>
      <div className="day-pick" role="group" aria-label="Status">
        {["new", "contacted", "applied", "closed", ""].map((s) => (
          <button key={s || "all"} type="button" className={`btn btn-sm ${status === s ? "btn-primary" : "btn-ghost"}`} onClick={() => setStatus(s)}>
            {s ? s[0].toUpperCase() + s.slice(1) : "All"}
          </button>
        ))}
      </div>
      {list.data?.length === 0 && <EmptyState title="No enquiries" />}
      <div className="request-list">
        {list.data?.map((e) => (
          <section key={e.id} className="card request-card">
            <div className="request-head">
              <b>
                {e.name} · {e.phone}
              </b>
              <StatusBadge tone={e.status === "new" ? "warning" : "neutral"}>{e.status}</StatusBadge>
            </div>
            <p className="small">
              {e.programme ?? "Any programme"} · {e.source.replace("_", " ")} · {new Date(e.created_at).toLocaleDateString("en-IN")}
              {e.message && ` · “${e.message}”`}
            </p>
            {e.notes.map((n, i) => (
              <p key={i} className="muted small">
                {n.by}: {n.text}
              </p>
            ))}
            {canManage && (
              <div className="row-actions">
                {e.status === "new" && (
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => update.mutate({ id: e.id, body: { status: "contacted", note: "Called" } })}>
                    Mark called
                  </button>
                )}
                {e.status !== "closed" && (
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => update.mutate({ id: e.id, body: { status: "closed" } })}>
                    Close
                  </button>
                )}
              </div>
            )}
          </section>
        ))}
      </div>
    </>
  );
}

function ReportTab({ cycleId }: { cycleId: string }) {
  const report = useReport(cycleId);
  if (!report.data) return null;
  return (
    <div className="data-table data-table-scroll">
      <table>
        <thead>
          <tr>
            <th>Programme</th>
            <th className="num">Seats</th>
            <th className="num">Applied</th>
            <th className="num">Verified</th>
            <th className="num">Offered</th>
            <th className="num">Admitted</th>
            <th className="num">Waiting</th>
            <th className="num">Cancelled</th>
            <th>Admitted by category</th>
          </tr>
        </thead>
        <tbody>
          {report.data.programmes.map((p) => (
            <tr key={p.programme_id}>
              <td>{p.programme}</td>
              <td className="num">{p.seats}</td>
              <td className="num">{p.applied}</td>
              <td className="num">{p.verified}</td>
              <td className="num">{p.offered}</td>
              <td className="num">{p.admitted}</td>
              <td className="num">{p.waiting}</td>
              <td className="num">{p.cancelled}</td>
              <td className="small">
                {Object.entries(p.by_category)
                  .map(([c, v]) => `${c} ${v.admitted}/${v.applied}${p.reserved[c] ? ` (${p.reserved[c]} reserved)` : ""}`)
                  .join(" · ")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SetupTab({ cycle, canManage }: { cycle: Cycle | undefined; canManage: boolean }) {
  const setup = useSetup();
  const save = useSaveCycle();
  const year = setup.data?.academic_years.find((y) => y.is_current) ?? setup.data?.academic_years[0];
  const [form, setForm] = useState(() => ({
    name: cycle?.name ?? "",
    apply_until: cycle?.apply_until ?? "",
    course_start: cycle?.course_start ?? "",
    fee: cycle ? String(cycle.application_fee / 100) : "500",
    programme_id: cycle?.programmes[0]?.programme_id ?? "",
    seats: String(cycle?.programmes[0]?.seats ?? 60),
    reserved: Object.fromEntries((cycle?.programmes[0]?.reserved ?? []).map((r) => [r.category_id, String(r.seats)])) as Record<string, string>,
    status: cycle?.status ?? "draft",
  }));
  if (!canManage) return <p className="muted">Only the Admission Cell changes the setup.</p>;
  const programmes = (setup.data?.programmes ?? []).filter((p) => p.status === "active");
  return (
    <form
      className="card"
      onSubmit={(e) => {
        e.preventDefault();
        const others = (cycle?.programmes ?? []).filter((p) => p.programme_id !== form.programme_id).map((p) => ({ programme_id: p.programme_id, year_of_study: p.year_of_study, seats: p.seats, reserved: Object.fromEntries(p.reserved.map((r) => [r.category_id, r.seats])) }));
        const body = {
          name: form.name,
          academic_year_id: cycle?.academic_year_id ?? year?.id,
          apply_until: form.apply_until,
          course_start: form.course_start,
          application_fee: parseRupees(form.fee) ?? 0,
          programmes: [
            ...others,
            { programme_id: form.programme_id, year_of_study: 1, seats: Number(form.seats), reserved: Object.fromEntries(Object.entries(form.reserved).filter(([, v]) => Number(v) > 0).map(([k, v]) => [k, Number(v)])) },
          ],
          ...(cycle ? { status: form.status, refund_rules: cycle.refund_rules, processing_fee: cycle.processing_fee, documents: cycle.documents } : {}),
        };
        save.mutate({ id: cycle?.id, body });
      }}
    >
      <h2 className="card-title">{cycle ? "Admission cycle" : "Start an admission cycle"}</h2>
      <div className="app-grid">
        <div className="field">
          <label htmlFor="cy-name">Name</label>
          <input id="cy-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
        </div>
        <div className="field">
          <label htmlFor="cy-until">Last date to apply</label>
          <input id="cy-until" type="date" value={form.apply_until} onChange={(e) => setForm({ ...form, apply_until: e.target.value })} required />
        </div>
        <div className="field">
          <label htmlFor="cy-start">Course starts</label>
          <input id="cy-start" type="date" value={form.course_start} onChange={(e) => setForm({ ...form, course_start: e.target.value })} required />
        </div>
        <div className="field">
          <label htmlFor="cy-fee">Application fee (₹)</label>
          <input id="cy-fee" inputMode="decimal" value={form.fee} onChange={(e) => setForm({ ...form, fee: e.target.value })} />
        </div>
        {cycle && (
          <div className="field">
            <label htmlFor="cy-status">Status</label>
            <select id="cy-status" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as Cycle["status"] })}>
              <option value="draft">Draft (not public)</option>
              <option value="open">Open for applications</option>
              <option value="closed">Closed</option>
            </select>
          </div>
        )}
      </div>
      <h2 className="card-title">Seats</h2>
      <div className="app-grid">
        <div className="field">
          <label htmlFor="cy-prog">Programme (first year)</label>
          <select id="cy-prog" value={form.programme_id} onChange={(e) => setForm({ ...form, programme_id: e.target.value })} required>
            <option value="">Choose…</option>
            {programmes.map((p) => (
              <option key={p.id} value={p.id}>
                {p.code} · {p.name}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="cy-seats">Total seats</label>
          <input id="cy-seats" type="number" min={1} value={form.seats} onChange={(e) => setForm({ ...form, seats: e.target.value })} />
        </div>
        {(setup.data?.categories ?? [])
          .filter((c) => c.code !== "OPEN")
          .map((c) => (
            <div className="field" key={c.id}>
              <label htmlFor={`cy-r-${c.id}`}>{c.code} reserved</label>
              <input id={`cy-r-${c.id}`} type="number" min={0} value={form.reserved[c.id] ?? ""} onChange={(e) => setForm({ ...form, reserved: { ...form.reserved, [c.id]: e.target.value } })} />
            </div>
          ))}
      </div>
      {save.error && <p className="form-error">{save.error.message}</p>}
      {save.isSuccess && <p className="muted small">Saved.</p>}
      <button type="submit" className="btn btn-primary" disabled={save.isPending}>
        {cycle ? "Save" : "Create"}
      </button>
    </form>
  );
}

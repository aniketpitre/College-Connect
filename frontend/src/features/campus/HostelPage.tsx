import { useState } from "react";
import LanguageToggle from "../../app/LanguageToggle";
import { EmptyState } from "../../components/EmptyState";
import { StatusBadge } from "../../components/StatusBadge";
import { CAMPUS_STRINGS } from "../../i18n/campus";
import { hasPermission, useMe } from "../../lib/auth";
import { useAskOutpass, useComplain, useComplaints, useHostel, useHostelAdmin, useMyHostel, useOutpassAction, useOutpasses, useUpdateComplaint } from "../../lib/campus";
import { useLanguage } from "../../lib/language";
import { formatPaise, parseRupees } from "../../lib/money";
import "./campus.css";

const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

export default function HostelPage() {
  const { data: me } = useMe();
  return me?.kind === "student" ? <MyHostel /> : <WardenDesk canManage={hasPermission(me, "hostel.manage")} />;
}

function MyHostel() {
  const [language, setLanguage] = useLanguage();
  const t = CAMPUS_STRINGS[language].hostel;
  const mine = useMyHostel();
  const ask = useAskOutpass();
  const complain = useComplain();
  const [op, setOp] = useState({ leave_at: "", return_by: "", destination: "", reason: "" });
  const [c, setC] = useState({ category: "room", text: "" });
  const locale = language === "en" ? "en-IN" : `${language}-IN`;
  const when = (iso: string) => new Date(iso).toLocaleString(locale, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
  const m = mine.data;
  if (!m) return null;
  return (
    <div lang={language}>
      <div className="page-head">
        <h1>{t.title}</h1>
        <LanguageToggle value={language} onChange={setLanguage} />
      </div>
      {!m.resident || !m.allotment ? (
        <p className="muted">{t.notResident}</p>
      ) : (
        <>
          <p>
            <b>{t.room(m.allotment.block, m.allotment.room, m.allotment.bed)}</b> <span className="muted">· {t.since(m.allotment.since)}</span>
          </p>
          <h2 className="subhead">{t.outpass}</h2>
          <form
            className="card campus-form"
            onSubmit={(e) => {
              e.preventDefault();
              ask.mutate({ ...op, leave_at: `${op.leave_at}:00+05:30`, return_by: `${op.return_by}:00+05:30` }, { onSuccess: () => setOp({ leave_at: "", return_by: "", destination: "", reason: "" }) });
            }}
          >
            <div className="field">
              <label htmlFor="op-from">{t.leaveAt}</label>
              <input id="op-from" type="datetime-local" value={op.leave_at} onChange={(e) => setOp({ ...op, leave_at: e.target.value })} required />
            </div>
            <div className="field">
              <label htmlFor="op-to">{t.returnBy}</label>
              <input id="op-to" type="datetime-local" value={op.return_by} onChange={(e) => setOp({ ...op, return_by: e.target.value })} required />
            </div>
            <div className="field">
              <label htmlFor="op-dest">{t.destination}</label>
              <input id="op-dest" value={op.destination} onChange={(e) => setOp({ ...op, destination: e.target.value })} required />
            </div>
            <div className="field">
              <label htmlFor="op-why">{t.reason}</label>
              <input id="op-why" value={op.reason} onChange={(e) => setOp({ ...op, reason: e.target.value })} required />
            </div>
            {ask.error && <p className="form-error">{ask.error.message}</p>}
            <div>
              <button type="submit" className="btn btn-primary" disabled={ask.isPending}>
                {t.ask}
              </button>
            </div>
          </form>
          <ul className="campus-list">
            {m.outpasses.map((o) => (
              <li key={o.id}>
                <div>
                  <b>{o.destination}</b>
                  <div className="muted small">
                    {when(o.leave_at)} → {when(o.return_by)}
                    {o.decision_reason && ` · ${o.decision_reason}`}
                  </div>
                </div>
                <StatusBadge tone={o.status === "approved" || o.status === "returned" ? "success" : o.status === "rejected" ? "danger" : "warning"}>
                  {o.late ? t.late : t.statuses[o.status]}
                </StatusBadge>
              </li>
            ))}
          </ul>
          <h2 className="subhead">{t.complaints}</h2>
          <form
            className="card campus-form"
            onSubmit={(e) => {
              e.preventDefault();
              complain.mutate(c, { onSuccess: () => setC({ ...c, text: "" }) });
            }}
          >
            <div className="field">
              <label htmlFor="cp-cat">{t.category}</label>
              <select id="cp-cat" value={c.category} onChange={(e) => setC({ ...c, category: e.target.value })}>
                {Object.entries(t.categories).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="cp-text">{t.describe}</label>
              <input id="cp-text" value={c.text} onChange={(e) => setC({ ...c, text: e.target.value })} required minLength={5} />
            </div>
            {complain.error && <p className="form-error">{complain.error.message}</p>}
            <div>
              <button type="submit" className="btn btn-primary" disabled={complain.isPending}>
                {t.send}
              </button>
            </div>
          </form>
          <ul className="campus-list">
            {m.complaints.map((x) => (
              <li key={x.id}>
                <div>
                  <b>{t.categories[x.category]}</b>: {x.text}
                  {x.notes.length > 0 && <div className="muted small">{x.notes.map((n) => n.text).join(" · ")}</div>}
                </div>
                <StatusBadge tone={x.status === "resolved" ? "success" : "warning"}>{t.complaintStatus[x.status]}</StatusBadge>
              </li>
            ))}
          </ul>
          {m.mess_menu && Object.values(m.mess_menu).some(Boolean) && (
            <>
              <h2 className="subhead">{t.mess}</h2>
              <ul className="campus-list">
                {DAYS.filter((d) => m.mess_menu?.[d]).map((d) => (
                  <li key={d}>
                    <b>{t.days[d]}</b>
                    <span>{m.mess_menu?.[d]}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </div>
  );
}

function WardenDesk({ canManage }: { canManage: boolean }) {
  const hostel = useHostel();
  const [tab, setTab] = useState<"rooms" | "outpasses" | "complaints" | "setup">("rooms");
  const h = hostel.data;
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Hostel</div>
          <h1>Warden's desk</h1>
        </div>
      </div>
      {h && (
        <div className="tiles fee-tiles">
          <div className="tile">
            <div className="tile-label">Beds occupied</div>
            <div className="tile-value">
              {h.blocks.reduce((n, b) => n + b.occupied, 0)}/{h.blocks.reduce((n, b) => n + b.beds, 0)}
            </div>
          </div>
          <div className={`tile${h.pending_outpasses ? " tile-warn" : ""}`}>
            <div className="tile-label">Out-passes to decide</div>
            <div className="tile-value">{h.pending_outpasses}</div>
          </div>
          <div className={`tile${h.overdue_returns ? " tile-warn" : ""}`}>
            <div className="tile-label">Out now (late)</div>
            <div className="tile-value">
              {h.out_now} ({h.overdue_returns})
            </div>
          </div>
          <div className="tile">
            <div className="tile-label">Open complaints</div>
            <div className="tile-value">{h.open_complaints}</div>
          </div>
        </div>
      )}
      <div className="tabs" role="tablist">
        {(
          [
            ["rooms", "Rooms"],
            ["outpasses", "Out-passes"],
            ["complaints", "Complaints"],
            ["setup", "Blocks & mess"],
          ] as const
        ).map(([k, label]) => (
          <button key={k} type="button" role="tab" aria-selected={tab === k} className={tab === k ? "active" : ""} onClick={() => setTab(k)}>
            {label}
          </button>
        ))}
      </div>
      {tab === "rooms" && <Rooms canManage={canManage} />}
      {tab === "outpasses" && <Outpasses canManage={canManage} />}
      {tab === "complaints" && <Complaints canManage={canManage} />}
      {tab === "setup" && canManage && <Setup />}
    </>
  );
}

function Rooms({ canManage }: { canManage: boolean }) {
  const hostel = useHostel();
  const admin = useHostelAdmin();
  const [prn, setPrn] = useState("");
  if (!hostel.data) return null;
  if (hostel.data.blocks.length === 0) return <EmptyState title="No hostel blocks yet: add one under Blocks & mess" />;
  return (
    <>
      {canManage && (
        <div className="row-actions" style={{ justifyContent: "flex-start", marginBottom: 12 }}>
          <label>
            Allot to PRN <input value={prn} onChange={(e) => setPrn(e.target.value)} aria-label="PRN to allot" />
          </label>
          <span className="muted small">then press “Allot” on a room with a free bed</span>
        </div>
      )}
      {admin.error && <p className="form-error">{admin.error.message}</p>}
      {hostel.data.blocks.map((b) => (
        <section key={b.id} className="card">
          <h2 className="card-title">
            {b.name} · {b.gender} · {b.occupied}/{b.beds} beds · fee {formatPaise(b.annual_fee)} a year
          </h2>
          <ul className="campus-list">
            {b.rooms.map((r) => (
              <li key={r.id}>
                <div>
                  <b>Room {r.number}</b> <span className="muted small">({r.occupants.length}/{r.beds})</span>
                  <div className="small">
                    {r.occupants.map((o) => (
                      <span key={o.allotment_id} className="occupant">
                        Bed {o.bed}: {o.name} ({o.prn})
                        {canManage && (
                          <button
                            type="button"
                            className="link-button"
                            onClick={() => {
                              const reason = window.prompt(`Vacate ${o.name}? Reason:`);
                              if (reason) admin.mutate({ path: `/allotments/${o.allotment_id}/vacate`, body: { reason } });
                            }}
                          >
                            vacate
                          </button>
                        )}
                      </span>
                    ))}
                  </div>
                </div>
                {canManage && r.occupants.length < r.beds && (
                  <button type="button" className="btn btn-ghost btn-sm" disabled={!prn.trim() || admin.isPending} onClick={() => admin.mutate({ path: "/allotments", body: { prn, room_id: r.id } })}>
                    Allot
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </>
  );
}

function Outpasses({ canManage }: { canManage: boolean }) {
  const [status, setStatus] = useState("requested");
  const list = useOutpasses(status);
  const act = useOutpassAction();
  return (
    <>
      <div className="day-pick" role="group" aria-label="Status">
        {(
          [
            ["requested", "To decide"],
            ["active", "Approved / out"],
            ["returned", "Returned"],
            ["rejected", "Rejected"],
          ] as const
        ).map(([k, label]) => (
          <button key={k} type="button" className={`btn btn-sm ${status === k ? "btn-primary" : "btn-ghost"}`} onClick={() => setStatus(k)}>
            {label}
          </button>
        ))}
      </div>
      {act.error && <p className="form-error">{act.error.message}</p>}
      {list.data?.length === 0 && <EmptyState title="Nothing here" />}
      <div className="request-list">
        {list.data?.map((o) => (
          <section key={o.id} className="card request-card">
            <div className="request-head">
              <b>
                {o.student?.name} ({o.student?.prn}) → {o.destination}
              </b>
              <StatusBadge tone={o.late ? "danger" : "neutral"}>{o.late ? "late" : o.status}</StatusBadge>
            </div>
            <p className="small">
              {new Date(o.leave_at).toLocaleString("en-IN")} → {new Date(o.return_by).toLocaleString("en-IN")} · {o.reason}
            </p>
            {canManage && (
              <div className="row-actions">
                {o.status === "requested" && (
                  <>
                    <button type="button" className="btn btn-primary btn-sm" onClick={() => act.mutate({ id: o.id, action: "approve" })}>
                      Approve (tell parents)
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => {
                        const reason = window.prompt("Reason for not approving:");
                        if (reason) act.mutate({ id: o.id, action: "reject", reason });
                      }}
                    >
                      Reject
                    </button>
                  </>
                )}
                {o.status === "approved" && (
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => act.mutate({ id: o.id, action: "out" })}>
                    Left the hostel
                  </button>
                )}
                {o.status === "out" && (
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => act.mutate({ id: o.id, action: "returned" })}>
                    Back
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

function Complaints({ canManage }: { canManage: boolean }) {
  const list = useComplaints();
  const update = useUpdateComplaint();
  if (list.data?.length === 0) return <EmptyState title="No open complaints" />;
  return (
    <div className="request-list">
      {list.data?.map((c) => (
        <section key={c.id} className="card request-card">
          <div className="request-head">
            <b>
              {c.category} · {c.room} · {c.student?.name}
            </b>
            <StatusBadge tone={c.status === "open" ? "warning" : "neutral"}>{c.status.replace("_", " ")}</StatusBadge>
          </div>
          <p className="small">{c.text}</p>
          {c.notes.map((n, i) => (
            <p key={i} className="muted small">
              {n.text}
            </p>
          ))}
          {canManage && (
            <div className="row-actions">
              {c.status === "open" && (
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => update.mutate({ id: c.id, status: "in_progress" })}>
                  Working on it
                </button>
              )}
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() => update.mutate({ id: c.id, status: "resolved", note: window.prompt("What was done?") ?? "" })}
              >
                Resolved
              </button>
            </div>
          )}
        </section>
      ))}
    </div>
  );
}

function Setup() {
  const hostel = useHostel();
  const admin = useHostelAdmin();
  const [block, setBlock] = useState({ name: "", gender: "any", fee: "" });
  const [rooms, setRooms] = useState({ block_id: "", numbers: "", beds: "2" });
  const [menu, setMenu] = useState<Record<string, string>>({});
  return (
    <div className="campus-grid">
      <form
        className="card"
        onSubmit={(e) => {
          e.preventDefault();
          admin.mutate({ path: "/blocks", body: { name: block.name, gender: block.gender, annual_fee: parseRupees(block.fee) ?? 0 } });
        }}
      >
        <h2 className="card-title">Add a block</h2>
        <div className="field">
          <label htmlFor="bl-name">Name</label>
          <input id="bl-name" value={block.name} onChange={(e) => setBlock({ ...block, name: e.target.value })} required />
        </div>
        <div className="field">
          <label htmlFor="bl-g">For</label>
          <select id="bl-g" value={block.gender} onChange={(e) => setBlock({ ...block, gender: e.target.value })}>
            <option value="any">Anyone</option>
            <option value="boys">Boys</option>
            <option value="girls">Girls</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="bl-fee">Hostel fee a year (₹)</label>
          <input id="bl-fee" inputMode="decimal" value={block.fee} onChange={(e) => setBlock({ ...block, fee: e.target.value })} />
        </div>
        <button type="submit" className="btn btn-primary" disabled={admin.isPending}>
          Add block
        </button>
      </form>
      <form
        className="card"
        onSubmit={(e) => {
          e.preventDefault();
          admin.mutate({ path: `/blocks/${rooms.block_id}/rooms`, body: { numbers: rooms.numbers.split(/[,\s]+/).filter(Boolean), beds: Number(rooms.beds) } });
        }}
      >
        <h2 className="card-title">Add rooms</h2>
        <div className="field">
          <label htmlFor="rm-bl">Block</label>
          <select id="rm-bl" value={rooms.block_id} onChange={(e) => setRooms({ ...rooms, block_id: e.target.value })} required>
            <option value="">Choose…</option>
            {hostel.data?.blocks.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="rm-nos">Room numbers (e.g. 101 102 103)</label>
          <input id="rm-nos" value={rooms.numbers} onChange={(e) => setRooms({ ...rooms, numbers: e.target.value })} required />
        </div>
        <div className="field">
          <label htmlFor="rm-beds">Beds per room</label>
          <input id="rm-beds" type="number" min={1} value={rooms.beds} onChange={(e) => setRooms({ ...rooms, beds: e.target.value })} />
        </div>
        <button type="submit" className="btn btn-primary" disabled={admin.isPending}>
          Add rooms
        </button>
      </form>
      <form
        className="card"
        onSubmit={(e) => {
          e.preventDefault();
          admin.mutate({ path: "/mess-menu", method: "PUT", body: { days: menu } });
        }}
      >
        <h2 className="card-title">Mess menu</h2>
        {DAYS.map((d) => (
          <div className="field" key={d}>
            <label htmlFor={`mn-${d}`}>{CAMPUS_STRINGS.en.hostel.days[d]}</label>
            <input id={`mn-${d}`} value={menu[d] ?? ""} onChange={(e) => setMenu({ ...menu, [d]: e.target.value })} />
          </div>
        ))}
        <button type="submit" className="btn btn-primary" disabled={admin.isPending}>
          Save menu
        </button>
      </form>
      {admin.error && <p className="form-error">{admin.error.message}</p>}
    </div>
  );
}

import { useState } from "react";
import { EmptyState } from "../../components/EmptyState";
import { StatusBadge } from "../../components/StatusBadge";
import { useApiKeys, useCreateKey, useRevokeKey } from "../../lib/apikeys";
import "../campus/campus.css";

const day = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });

/** Principal (English): keys for other systems to read the college's data through the open API. */
export default function ApiKeysPage() {
  const keys = useApiKeys();
  const create = useCreateKey();
  const revoke = useRevokeKey();
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<string[]>([]);
  const [days, setDays] = useState(365);
  const [shown, setShown] = useState<string | null>(null);
  const all = keys.data?.scopes ?? {};
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Integrations</div>
          <h1>API keys</h1>
        </div>
        <a className="btn btn-ghost" href="/api/v1/open/docs" target="_blank" rel="noreferrer">
          Open API documentation
        </a>
      </div>
      <p className="small muted">
        Another system (a university portal connector, the library software, the college website) can read the college's data with a key. Give each key only the
        scopes it needs; it can only read, never change anything. Revoke a key when it is no longer used.
      </p>
      <form
        className="card"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate(
            { name, scopes, valid_days: days },
            {
              onSuccess: (k) => {
                setShown(k.key);
                setName("");
                setScopes([]);
              },
            },
          );
        }}
      >
        <h2 className="card-title">New key</h2>
        <div className="campus-form">
          <div className="field">
            <label htmlFor="key-name">What will use it</label>
            <input id="key-name" value={name} onChange={(e) => setName(e.target.value)} required minLength={3} placeholder="e.g. University portal sync" />
          </div>
          <div className="field">
            <label htmlFor="key-days">Valid for (days)</label>
            <input id="key-days" type="number" min={1} max={730} value={days} onChange={(e) => setDays(Number(e.target.value))} />
          </div>
        </div>
        <fieldset className="key-scopes">
          <legend className="small">Scopes</legend>
          {Object.entries(all).map(([k, label]) => (
            <label key={k} className="check-label">
              <input
                type="checkbox"
                checked={scopes.includes(k)}
                onChange={(e) => setScopes(e.target.checked ? [...scopes, k] : scopes.filter((x) => x !== k))}
              />{" "}
              <code>{k}</code> <span className="small muted">{label}</span>
            </label>
          ))}
        </fieldset>
        {create.error && <p className="form-error">{create.error.message}</p>}
        <button type="submit" className="btn btn-primary" disabled={create.isPending || scopes.length === 0}>
          Create key
        </button>
      </form>
      {shown && (
        <div className="card" role="status">
          <b>Copy this key now: it won't be shown again.</b>
          <pre className="key-secret">{shown}</pre>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => void navigator.clipboard?.writeText(shown)}>
            Copy
          </button>{" "}
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShown(null)}>
            Done
          </button>
        </div>
      )}
      {keys.data?.keys.length === 0 && <EmptyState title="No keys yet" />}
      <ul className="campus-list">
        {keys.data?.keys.map((k) => (
          <li key={k.id}>
            <div>
              <b>{k.name}</b> <code className="small">cc_{k.prefix}_…</code>
              <div className="small muted">
                {k.scopes.join(", ")} · made {day(k.created_at)} · expires {day(k.expires_at)} · {k.calls} calls
                {k.last_used_at && ` · last used ${day(k.last_used_at)}`}
              </div>
            </div>
            <span className="row-actions">
              <StatusBadge tone={k.state === "active" ? "success" : "neutral"}>{k.state}</StatusBadge>
              {k.state === "active" && (
                <button type="button" className="btn btn-ghost btn-sm" disabled={revoke.isPending} onClick={() => revoke.mutate(k.id)}>
                  Revoke
                </button>
              )}
            </span>
          </li>
        ))}
      </ul>
    </>
  );
}

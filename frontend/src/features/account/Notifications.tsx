import { useState } from "react";
import { MESSAGE_STRINGS } from "../../i18n/messages";
import { useMyChannels, useSetChannels, type Channel } from "../../lib/messages";
import type { Language } from "../../lib/types";

/** Which channels the college may use to reach this person. */
export function Notifications({ language }: { language: Language }) {
  const t = MESSAGE_STRINGS[language];
  const mine = useMyChannels();
  const save = useSetChannels();
  const [draft, setDraft] = useState<Record<Channel, boolean> | null>(null);
  const d = mine.data;
  if (!d) return null;
  const saved = Object.fromEntries(d.channels.map((c) => [c.channel, c.on])) as Record<Channel, boolean>;
  const value = draft ?? saved;
  const changed = d.channels.some((c) => value[c.channel] !== c.on);
  return (
    <section className="account-card">
      <h2>{t.title}</h2>
      <p className="muted">{t.intro}</p>
      {d.channels.map((c) => (
        <label key={c.channel} className="check-label">
          <input type="checkbox" checked={value[c.channel]} disabled={!c.available} onChange={(e) => setDraft({ ...value, [c.channel]: e.target.checked })} />
          {c.label}
          <span className="muted small">{!c.available ? ` (${t.notSetUp})` : c.to ? ` · ${c.to}` : ` (${t.noAddress})`}</span>
        </label>
      ))}
      <div className="row-actions" style={{ justifyContent: "flex-start" }}>
        <button type="button" className="btn btn-ghost btn-sm" disabled={!changed || save.isPending} onClick={() => save.mutate(value, { onSuccess: () => setDraft(null) })}>
          {t.save}
        </button>
        {save.isSuccess && !changed && (
          <span className="muted small" role="status">
            {t.saved}
          </span>
        )}
      </div>
      {save.error && <p className="form-error">{save.error.message}</p>}
    </section>
  );
}

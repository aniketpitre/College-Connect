import { useState } from "react";
import { Link, useParams } from "react-router";
import LanguageToggle from "../../app/LanguageToggle";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { StatusBadge } from "../../components/StatusBadge";
import { NOTICE_STRINGS } from "../../i18n/notices";
import { hasPermission, useMe } from "../../lib/auth";
import { useLanguage } from "../../lib/language";
import { attachmentUrl, localized, useEmailNotice, useNotice, useUpdateNotice, type EmailProgress, type Notice } from "../../lib/notices";
import "./notices.css";

export default function NoticeDetailPage() {
  const { id = "" } = useParams();
  const { data: me } = useMe();
  const [language, setLanguage] = useLanguage();
  const t = NOTICE_STRINGS[language];
  const notice = useNotice(id);
  const n = notice.data;
  const canPublish = hasPermission(me, "notices.publish");
  const locale = language === "en" ? "en-IN" : `${language}-IN`;

  if (notice.error) return <p className="form-error">{notice.error.message}</p>;
  if (!n) return <p className="muted">…</p>;
  const loc = localized(n, language);
  return (
    <div lang={language} className="notice-detail">
      <div className="section-head">
        <Link to="/app/notices" className="back-link">
          {t.back}
        </Link>
        <LanguageToggle value={language} onChange={setLanguage} />
      </div>
      <article className="card">
        <h1>{loc.title}</h1>
        <p className="muted small">
          {t.postedOn(new Date(n.publish_at).toLocaleDateString(locale, { day: "numeric", month: "long", year: "numeric" }))}
          {n.expires_on ? ` · ${t.validTill(new Date(`${n.expires_on}T00:00:00`).toLocaleDateString(locale, { day: "numeric", month: "long" }))}` : ""}
          {n.author ? ` · ${n.author}` : ""}
        </p>
        {loc.machine && t.machine && <p className="small muted">{t.machine}</p>}
        {loc.body && <div className="notice-body">{loc.body}</div>}
        {n.has_attachment && (
          <a className="btn btn-ghost" href={attachmentUrl(n.id)} target="_blank" rel="noreferrer">
            {t.openPdf}
          </a>
        )}
      </article>
      {canPublish && (
        <Manage
          id={n.id}
          state={n.state}
          pinned={n.pinned}
          audience={n.audience_label}
          emailed={n.emailed}
          isPublic={n.public}
          machine={Boolean(n.hi?.machine || n.mr?.machine)}
        />
      )}
      {canPublish && n.state !== "withdrawn" && <EditTranslations key={`${n.hi?.title}|${n.mr?.title}`} notice={n} />}
    </div>
  );
}

function Manage({
  id,
  state,
  pinned,
  audience,
  emailed,
  isPublic,
  machine,
}: {
  id: string;
  state: string;
  pinned: boolean;
  audience: string;
  emailed: number;
  isPublic: boolean;
  machine: boolean;
}) {
  const update = useUpdateNotice(id);
  const email = useEmailNotice(id);
  const [withdrawing, setWithdrawing] = useState(false);
  const [progress, setProgress] = useState<EmailProgress | null>(null);

  const sendAll = async () => {
    for (;;) {
      const r = await email.mutateAsync().catch(() => null);
      if (!r) return;
      setProgress(r);
      if (r.done) return;
    }
  };

  return (
    <section className="card manage-card">
      <h2 className="card-title">Manage (staff)</h2>
      <p className="muted small">
        Audience: {audience} · <StatusBadge tone={state === "published" ? "success" : "neutral"}>{state}</StatusBadge>
        {isPublic && " · also on the public help desk"}
      </p>
      {machine && <p className="small">The Hindi/Marathi version was translated automatically: read it in हिंदी / मराठी above and correct it if needed.</p>}
      {(update.error || email.error) && <p className="form-error">{(update.error ?? email.error)?.message}</p>}
      {progress && (
        <p className="auth-success" role="status">
          Emailed {progress.emailed} of {progress.audience} people with an email address{progress.failed ? ` (${progress.failed} failed; try again)` : ""}.
        </p>
      )}
      <div className="row-actions action-bar">
        {state === "published" && (
          <button type="button" className="btn btn-primary btn-sm" disabled={email.isPending} onClick={sendAll}>
            {email.isPending ? "Sending…" : emailed ? `Email the rest (sent to ${emailed})` : "Email the audience"}
          </button>
        )}
        {state !== "withdrawn" && (
          <button type="button" className="btn btn-ghost btn-sm" disabled={update.isPending} onClick={() => update.mutate({ pinned: !pinned })}>
            {pinned ? "Unpin" : "Pin to the top"}
          </button>
        )}
        {state !== "withdrawn" && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setWithdrawing(true)}>
            Withdraw
          </button>
        )}
      </div>
      <ConfirmDialog
        open={withdrawing}
        title="Withdraw this notice?"
        message="It disappears for everyone. It stays in the records with your reason."
        confirmLabel="Withdraw"
        requireReason
        danger
        onCancel={() => setWithdrawing(false)}
        onConfirm={(reason) => {
          update.mutate({ status: "withdrawn", reason });
          setWithdrawing(false);
        }}
      />
    </section>
  );
}

/** Staff: check and correct the Hindi/Marathi versions (saving them clears the "translated automatically" mark). */
function EditTranslations({ notice }: { notice: Notice }) {
  const update = useUpdateNotice(notice.id);
  const [open, setOpen] = useState(false);
  const [hi, setHi] = useState({ title: notice.hi?.title ?? "", body: notice.hi?.body ?? "" });
  const [mr, setMr] = useState({ title: notice.mr?.title ?? "", body: notice.mr?.body ?? "" });
  if (!open)
    return (
      <button type="button" className="link-btn" onClick={() => setOpen(true)}>
        Edit the Hindi / Marathi versions
      </button>
    );
  return (
    <form
      className="card"
      onSubmit={(e) => {
        e.preventDefault();
        update.mutate({ hi, mr }, { onSuccess: () => setOpen(false) });
      }}
    >
      <h2 className="card-title">Hindi and Marathi versions</h2>
      {update.error && <p className="form-error">{update.error.message}</p>}
      <div className="field-row translations">
        {(
          [
            ["hi", "Hindi", hi, setHi],
            ["mr", "Marathi", mr, setMr],
          ] as const
        ).map(([code, name, value, set]) => (
          <div key={code}>
            <div className="field">
              <label htmlFor={`t-${code}-title`}>Title in {name}</label>
              <input id={`t-${code}-title`} lang={code} value={value.title} onChange={(e) => set({ ...value, title: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor={`t-${code}-body`}>Text in {name}</label>
              <textarea id={`t-${code}-body`} lang={code} rows={5} value={value.body} onChange={(e) => set({ ...value, body: e.target.value })} />
            </div>
          </div>
        ))}
      </div>
      <div className="row-actions" style={{ justifyContent: "flex-start" }}>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setOpen(false)}>
          Cancel
        </button>
        <button type="submit" className="btn btn-primary btn-sm" disabled={update.isPending}>
          Save translations
        </button>
      </div>
    </form>
  );
}

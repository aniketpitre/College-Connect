import { useState } from "react";
import { Link } from "react-router";
import LanguageToggle from "../../app/LanguageToggle";
import { EmptyState } from "../../components/EmptyState";
import { StatusBadge } from "../../components/StatusBadge";
import { NOTICE_STRINGS } from "../../i18n/notices";
import { hasPermission, useMe } from "../../lib/auth";
import { useLanguage } from "../../lib/language";
import { localized, useNotices } from "../../lib/notices";
import { NoticeForm } from "./NoticeForm";
import "./notices.css";

const STATE_TONE = { published: "success", scheduled: "info", expired: "neutral", withdrawn: "danger" } as const;

/** Everyone's notices; publishers also manage them (all states) and post new ones. */
export default function NoticesPage() {
  const { data: me } = useMe();
  const [language, setLanguage] = useLanguage();
  const t = NOTICE_STRINGS[language];
  const canPublish = hasPermission(me, "notices.publish");
  const [manage, setManage] = useState(canPublish);
  const [q, setQ] = useState("");
  const [creating, setCreating] = useState(false);
  const notices = useNotices(q, manage && canPublish);
  const locale = language === "en" ? "en-IN" : `${language}-IN`;

  return (
    <div lang={language}>
      <div className="page-head">
        <h1>{t.title}</h1>
        <div className="row-actions">
          {canPublish && (
            <button type="button" className="btn btn-primary" onClick={() => setCreating(true)}>
              New notice
            </button>
          )}
          <LanguageToggle value={language} onChange={setLanguage} />
        </div>
      </div>
      <div className="filters">
        <input className="notice-search" type="search" aria-label={t.search} placeholder={t.search} value={q} onChange={(e) => setQ(e.target.value)} />
        {canPublish && (
          <label className="check-label muted small">
            <input type="checkbox" checked={manage} onChange={(e) => setManage(e.target.checked)} /> Show all (scheduled, expired, withdrawn)
          </label>
        )}
      </div>
      {notices.data?.length === 0 && <EmptyState title={t.none} />}
      <ul className="notice-list">
        {notices.data?.map((n) => {
          const loc = localized(n, language);
          return (
            <li key={n.id} className={n.pinned ? "pinned" : ""}>
              <Link to={`/app/notices/${n.id}`} className="notice-row">
                <div>
                  <div className="notice-title">
                    {n.pinned && <StatusBadge tone="warning">{t.pinned}</StatusBadge>} {loc.title}
                  </div>
                  <div className="muted small">
                    {t.postedOn(new Date(n.publish_at).toLocaleDateString(locale, { day: "numeric", month: "short", year: "numeric" }))}
                    {n.has_attachment ? " · PDF" : ""}
                    {canPublish && ` · ${n.audience_label}`}
                  </div>
                </div>
                {canPublish && n.state !== "published" && <StatusBadge tone={STATE_TONE[n.state]}>{n.state}</StatusBadge>}
              </Link>
            </li>
          );
        })}
      </ul>
      {creating && <NoticeForm onClose={() => setCreating(false)} />}
    </div>
  );
}

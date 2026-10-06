import { Link } from "react-router";
import { MoneyText } from "../../components/MoneyText";
import { CERT_STRINGS } from "../../i18n/certificates";
import { PORTAL_STRINGS } from "../../i18n/portal";
import { STUDENT_STRINGS } from "../../i18n/student";
import { useMe } from "../../lib/auth";
import { useLanguage } from "../../lib/language";
import { formatPaise } from "../../lib/money";
import { useStudentHome, type HomeCard } from "../../lib/portal";
import { fileUrl } from "../../lib/students";
import "./portal.css";

/** The student's home (spec R13): what needs attention, their fees at a glance, and the help desk. */
export default function StudentHome() {
  const [language] = useLanguage();
  const t = PORTAL_STRINGS[language];
  const s = STUDENT_STRINGS[language];
  const home = useStudentHome();
  const { data: me } = useMe();
  const h = home.data;
  const locale = language === "en" ? "en-IN" : `${language}-IN`;
  const day = (iso: string) => new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString(locale, { day: "numeric", month: "long" });

  const text = (c: HomeCard): { body: string; to: string } => {
    switch (c.kind) {
      case "fee_overdue":
        return { body: `${t.feeOverdue(formatPaise(c.amount!), day(c.since!))} ${t.payAtOffice}`, to: "/app/my-fees" };
      case "fee_due_soon":
        return { body: t.feeDueSoon(formatPaise(c.amount!), c.label!, day(c.due_date!)), to: "/app/my-fees" };
      case "document_rejected":
        return { body: `${t.documentRejected(s.docTypes[c.type!] ?? c.type!)}${c.reason ? ` (${c.reason})` : ""}`, to: "/app/profile" };
      case "correction_approved":
        return { body: t.correctionApproved, to: "/app/profile" };
      case "correction_rejected":
        return { body: `${t.correctionRejected}${c.reason ? ` ${c.reason}` : ""}`, to: "/app/profile" };
      case "attendance_low":
        return { body: t.attendanceLow(c.code!, c.percent!, c.must_attend!), to: "/app/attendance" };
      case "attendance_warning":
        return { body: t.attendanceWarning(c.code!, c.percent!, c.can_miss!), to: "/app/attendance" };
      case "exam_form":
        return { body: t.examForm(c.title!, day(c.due_date!)), to: "/app/exams" };
      case "hall_ticket":
        return { body: t.hallTicket(c.title!), to: "/app/exams" };
      case "results":
        return { body: t.results(c.title!), to: "/app/exams" };
      case "certificate_ready":
        return { body: t.certificateReady(CERT_STRINGS[language].types[c.type!] ?? c.type!), to: "/app/certificates" };
      case "deadline": {
        const what = (language === "hi" ? c.what_hi : language === "mr" ? c.what_mr : null) || c.title!;
        return { body: t.deadline(what, day(c.due_date!), c.days_left ?? 0), to: `/app/notices/${c.notice_id}` };
      }
      case "notice":
        return { body: `${t.newNotice}: ${(language !== "en" && c[language]?.title) || c.title}`, to: `/app/notices/${c.notice_id}` };
    }
  };

  if (home.error) return <p className="form-error">{home.error.message}</p>;
  if (!h) return <p className="muted">…</p>;
  return (
    <div lang={language} className="student-home">
      <div className="home-hello">
        {h.photo_url ? <img src={fileUrl(h.photo_url)} alt="" className="home-photo" /> : <span className="home-photo photo-empty">{h.name.slice(0, 1)}</span>}
        <div>
          <div className="eyebrow">
            {t.academicYear} {h.academic_year}
          </div>
          <h1>{me?.kind === "parent" ? h.name : `${t.greeting}, ${h.name.split(" ")[0]}`}</h1>
          <div className="muted">
            {h.class} · PRN {h.prn}
          </div>
        </div>
      </div>

      <h2 className="subhead">{t.needsAttention}</h2>
      {h.cards.length === 0 ? (
        <p className="muted">{t.allClear}</p>
      ) : (
        <ul className="attention">
          {h.cards.map((c, i) => {
            const { body, to } = text(c);
            return (
              <li key={i} className={`attention-card ${c.severity}`}>
                <span>{body}</span>
                <Link to={to}>{t.view} →</Link>
              </li>
            );
          })}
        </ul>
      )}

      <div className="home-grid">
        {h.attendance != null && (
          <Link to="/app/attendance" className="card home-tile">
            <div className="tile-label">{t.attendanceTile}</div>
            <div className="tile-value">{h.attendance}%</div>
          </Link>
        )}
        {h.balance !== null && (
          <Link to="/app/my-fees" className="card home-tile">
            <div className="tile-label">{h.balance >= 0 ? t.balanceDue : t.inCredit}</div>
            <div className="tile-value">
              <MoneyText paise={Math.abs(h.balance)} />
            </div>
            <div className="muted small">{t.feesTitle} →</div>
          </Link>
        )}
        <div className="card home-tile ask-tile">
          <div className="tile-label">{t.askTitle}</div>
          <p className="muted small">{t.askBody}</p>
          <Link className="btn btn-primary btn-sm" to="/">
            {t.askButton}
          </Link>
        </div>
      </div>
    </div>
  );
}

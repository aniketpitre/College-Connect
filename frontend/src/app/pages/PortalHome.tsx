import { Link } from "react-router";
import StaffDashboard from "../../features/dashboard/StaffDashboard";
import StudentHome from "../../features/portal/StudentHome";
import { NAV_LABELS } from "../../i18n/nav";
import { hasPermission, isLearner, useMe } from "../../lib/auth";
import { useLanguage } from "../../lib/language";
import "../../features/portal/portal.css";

const STAFF_LINKS: [string, string, string][] = [
  ["/app/fees", "fees", "fees.read"],
  ["/app/approvals", "approvals", "approvals.decide"],
  ["/app/students", "students", "students.read"],
  ["/app/notices", "notices", "notices.read"],
  ["/app/exams", "exams", "marks.read"],
  ["/app/certificates", "certificates", "certificates.manage"],
  ["/app/users", "users", "users.read"],
  ["/app/setup", "setup", "setup.read"],
  ["/app/audit", "audit", "audit.read"],
  ["/app/analytics", "analytics", "analytics.view"],
];

/** "Dr. Sunita Rane" → "Sunita": titles aren't a first name. */
const firstName = (name: string) => name.split(" ").find((w) => !/^(dr|prof|mr|mrs|ms|shri|smt)\.?$/i.test(w)) ?? name;

/** Students get their own home; staff get shortcuts to what their roles allow. */
export default function PortalHome() {
  const { data: me } = useMe();
  const [language] = useLanguage();
  if (isLearner(me)) return <StudentHome />;
  const t = NAV_LABELS[language];
  const links = STAFF_LINKS.filter(([, , perm]) => hasPermission(me, perm));
  return (
    <div lang={language}>
      <div className="eyebrow">CollegeConnect</div>
      <h1>
        {language === "en" ? "Welcome" : language === "hi" ? "स्वागत है" : "स्वागत आहे"}, {firstName(me?.name ?? "")}
      </h1>
      <p className="muted">{me?.role_labels.join(", ")}</p>
      <div className="staff-links">
        {links.map(([to, key]) => (
          <Link key={to} to={to} className="card">
            {t[key] ?? key} →
          </Link>
        ))}
        <Link to="/app/account" className="card">
          {t.account} →
        </Link>
      </div>
      <StaffDashboard />
    </div>
  );
}

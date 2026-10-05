import { useEffect } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router";
import { apiFetch } from "../lib/api";
import { NAV_LABELS } from "../i18n/nav";
import { hasPermission, useLogout, useMe } from "../lib/auth";
import { useLanguage } from "../lib/language";
import "./layout.css";
import "./portal.css";
import "./auth.css";

interface NavItem {
  to: string;
  /** Key in NAV_LABELS. */
  label: string;
  /** Shown only to users with this permission (or any of these). */
  permission?: string | string[];
  /** Shown only to this kind of account. */
  kind?: "student" | "staff";
  /** The plan phase that builds this screen; shown disabled until then. */
  phase?: number;
}

const NAV: NavItem[] = [
  { to: "/app", label: "home" },
  { to: "/app/profile", label: "profile", kind: "student" },
  { to: "/app/my-fees", label: "fees", kind: "student" },
  { to: "/app/students", label: "students", permission: "students.read" },
  { to: "/app/fees", label: "fees", permission: "fees.read", kind: "staff" },
  { to: "/app/approvals", label: "approvals", permission: "approvals.decide" },
  { to: "/app/timetable", label: "timetable", kind: "student" },
  { to: "/app/timetable", label: "timetable", permission: "timetable.read", kind: "staff" },
  { to: "/app/notices", label: "notices" },
  {
    to: "/app/attendance",
    label: "attendance",
    kind: "staff",
    permission: ["attendance.take", "attendance.read", "attendance.read.dept", "attendance.approve", "attendance.exempt"],
  },
  { to: "/app/exams", label: "exams", phase: 2 },
  { to: "/app/certificates", label: "certificates", phase: 2 },
  { to: "/app/account", label: "account" },
  { to: "/app/users", label: "users", permission: "users.read" },
  { to: "/app/setup", label: "setup", permission: "setup.read" },
  { to: "/app/audit", label: "audit", permission: "audit.read" },
  { to: "/app/exports", label: "exports", permission: "export.request" },
  { to: "/app/analytics", label: "analytics", permission: "analytics.view" },
];

export default function AppLayout() {
  const { data: me } = useMe();
  const logout = useLogout();
  const navigate = useNavigate();
  const [language] = useLanguage();
  const t = NAV_LABELS[language];
  // Keep the account's saved language in step with the one chosen on this device.
  useEffect(() => {
    if (me && me.language !== language && me.session_state === "active") {
      apiFetch("/me/preferences", { method: "PATCH", body: JSON.stringify({ language }) }).catch(() => undefined);
    }
  }, [me, language]);
  const items = NAV.filter(
    (item) =>
      (!item.permission || [item.permission].flat().some((p) => hasPermission(me, p))) && (!item.kind || item.kind === me?.kind),
  );

  return (
    <div className="portal">
      <header className="portal-top">
        <Link className="brand" to="/app">
          <span className="seal">CC</span> CollegeConnect
        </Link>
        <div className="portal-user">
          <span className="portal-user-name">
            {me?.name}
            <span className="portal-user-role">{me?.kind === "student" ? me.prn : me?.role_labels.join(", ")}</span>
          </span>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            disabled={logout.isPending}
            onClick={() => logout.mutate(undefined, { onSettled: () => navigate("/login", { replace: true }) })}
          >
            {t.signOut}
          </button>
        </div>
      </header>
      <div className="portal-body">
        <nav className="portal-nav" aria-label="Portal">
          {items.map((item) =>
            item.phase ? (
              <span key={item.to} className="portal-link disabled" aria-disabled="true" title={`${t.soon} ${item.phase}`}>
                {t[item.label]}
                <span className="portal-soon">P{item.phase}</span>
              </span>
            ) : (
              <NavLink key={item.to} to={item.to} end={item.to === "/app"} className="portal-link">
                {t[item.label]}
              </NavLink>
            ),
          )}
        </nav>
        <main className="portal-main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

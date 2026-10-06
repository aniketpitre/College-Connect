import { useEffect } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router";
import { apiFetch } from "../lib/api";
import { OfflineSync } from "../features/attendance/OfflineSync";
import { NAV_LABELS } from "../i18n/nav";
import { PARENT_STRINGS } from "../i18n/parent";
import { hasPermission, useLogout, useMe } from "../lib/auth";
import { useChildId } from "../lib/child";
import { useLanguage } from "../lib/language";
import { useChildren, useSwitchChild, type Area } from "../lib/parent";
import "./layout.css";
import "./portal.css";
import "./auth.css";

type Kind = "student" | "staff" | "parent" | "applicant";
const LEARNER: Kind[] = ["student", "parent"];

interface NavItem {
  to: string;
  /** Key in NAV_LABELS. */
  label: string;
  /** Shown only to users with this permission (or any of these). */
  permission?: string | string[];
  /** Shown only to these kinds of account. */
  kind?: Kind | Kind[];
  /** Parents: shown only if the child shares this. */
  area?: Area;
  /** The plan phase that builds this screen; shown disabled until then. */
  phase?: number;
}

const NAV: NavItem[] = [
  { to: "/app/application", label: "application", kind: "applicant" },
  { to: "/app", label: "home" },
  { to: "/app/profile", label: "profile", kind: "student" },
  { to: "/app/my-fees", label: "fees", kind: LEARNER, area: "fees" },
  { to: "/app/students", label: "students", permission: "students.read" },
  { to: "/app/fees", label: "fees", permission: "fees.read", kind: "staff" },
  { to: "/app/approvals", label: "approvals", permission: "approvals.decide" },
  { to: "/app/timetable", label: "timetable", kind: LEARNER },
  { to: "/app/timetable", label: "timetable", permission: "timetable.read", kind: "staff" },
  { to: "/app/notices", label: "notices" },
  { to: "/app/attendance", label: "attendance", kind: LEARNER, area: "attendance" },
  {
    to: "/app/attendance",
    label: "attendance",
    kind: "staff",
    permission: ["attendance.take", "attendance.read", "attendance.read.dept", "attendance.approve", "attendance.exempt"],
  },
  { to: "/app/exams", label: "exams", kind: LEARNER, area: "results" },
  { to: "/app/exams", label: "exams", kind: "staff", permission: ["marks.enter", "marks.approve", "marks.read", "exams.manage", "marks.scheme.dept", "results.read"] },
  { to: "/app/certificates", label: "certificates", kind: LEARNER },
  { to: "/app/admissions", label: "admissions", permission: "admissions.read" },
  { to: "/app/library", label: "library", kind: "student" },
  { to: "/app/library", label: "library", kind: "staff", permission: "library.read" },
  { to: "/app/hostel", label: "hostel", kind: "student" },
  { to: "/app/hostel", label: "hostel", kind: "staff", permission: "hostel.read" },
  { to: "/app/placement", label: "placement", kind: "student" },
  { to: "/app/placement", label: "placement", kind: "staff", permission: "placement.read" },
  { to: "/app/grievances", label: "grievances", kind: "student" },
  { to: "/app/grievances", label: "grievances", kind: "staff", permission: ["grievance.manage", "grievance.read", "grievance.sensitive"] },
  { to: "/app/leave", label: "leave", kind: "staff", permission: "leave.apply" },
  { to: "/app/staff", label: "staff", kind: "staff", permission: ["staff.read", "staff.read.dept"] },
  { to: "/app/reports", label: "reports", kind: "staff", permission: "reports.read" },
  {
    to: "/app/certificates",
    label: "certificates",
    kind: "staff",
    permission: ["certificates.manage", "certificates.read", "certificates.sign.principal", "certificates.sign.hod"],
  },
  { to: "/app/messages", label: "messages", permission: "messages.read" },
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
  const p = PARENT_STRINGS[language];
  const isParent = me?.kind === "parent";
  const children = useChildren(isParent);
  const childId = useChildId();
  const switchChild = useSwitchChild();
  const child = children.data?.find((c) => c.id === childId);
  // A parent always looks at one child: keep the saved choice if it is still theirs, else the first.
  useEffect(() => {
    if (isParent && children.data?.length && !child) switchChild(children.data[0].id);
  }, [isParent, children.data, child, switchChild]);
  // Keep the account's saved language in step with the one chosen on this device.
  useEffect(() => {
    if (me && me.language !== language && me.session_state === "active") {
      apiFetch("/me/preferences", { method: "PATCH", body: JSON.stringify({ language }) }).catch(() => undefined);
    }
  }, [me, language]);
  const items = NAV.filter(
    (item) =>
      (!item.permission || [item.permission].flat().some((perm) => hasPermission(me, perm))) &&
      (item.kind ? me?.kind !== undefined && [item.kind].flat().includes(me.kind) : me?.kind !== "applicant") &&
      (!isParent || !item.area || Boolean(child?.access[item.area])),
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
          {isParent && children.data && children.data.length > 1 && (
            <label className="child-switch">
              <select value={childId ?? ""} onChange={(e) => switchChild(e.target.value)} aria-label={p.viewing}>
                {children.data.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
          )}
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
          {hasPermission(me, "attendance.take") && <OfflineSync />}
          {!isParent ? (
            <Outlet />
          ) : children.data?.length === 0 ? (
            <p className="muted">{p.noChildren}</p>
          ) : child ? (
            <Outlet key={child.id} />
          ) : (
            <p className="muted">…</p>
          )}
        </main>
      </div>
    </div>
  );
}

import { Link, NavLink, Outlet, useNavigate } from "react-router";
import { hasPermission, useLogout, useMe } from "../lib/auth";
import "./layout.css";

interface NavItem {
  to: string;
  label: string;
  /** Shown only to users with this permission. */
  permission?: string;
  /** The plan phase that builds this screen; shown disabled until then. */
  phase?: number;
}

const NAV: NavItem[] = [
  { to: "/app", label: "Home" },
  { to: "/app/students", label: "Students", phase: 1 },
  { to: "/app/fees", label: "Fees & receipts", phase: 1 },
  { to: "/app/notices", label: "Notices", phase: 1 },
  { to: "/app/attendance", label: "Attendance", phase: 2 },
  { to: "/app/exams", label: "Exams & results", phase: 2 },
  { to: "/app/certificates", label: "Certificates", phase: 2 },
];

export default function AppLayout() {
  const { data: me } = useMe();
  const logout = useLogout();
  const navigate = useNavigate();
  const items = NAV.filter((item) => !item.permission || hasPermission(me, item.permission));

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
            Sign out
          </button>
        </div>
      </header>
      <div className="portal-body">
        <nav className="portal-nav" aria-label="Portal">
          {items.map((item) =>
            item.phase ? (
              <span key={item.to} className="portal-link disabled" aria-disabled="true" title={`Arrives in Phase ${item.phase}`}>
                {item.label}
                <span className="portal-soon">P{item.phase}</span>
              </span>
            ) : (
              <NavLink key={item.to} to={item.to} end className="portal-link">
                {item.label}
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

import { Link, NavLink, Outlet } from "react-router";
import "./layout.css";

interface NavItem {
  to: string;
  label: string;
  /** The plan phase that builds this screen; shown disabled until then. */
  phase?: number;
}

// Portal navigation. Phase 1 replaces this with items filtered by the signed-in user's role.
const NAV: NavItem[] = [
  { to: "/app", label: "Home" },
  { to: "/app/admin", label: "Help desk analytics" },
  { to: "/app/students", label: "Students", phase: 1 },
  { to: "/app/fees", label: "Fees & receipts", phase: 1 },
  { to: "/app/notices", label: "Notices", phase: 1 },
  { to: "/app/attendance", label: "Attendance", phase: 2 },
  { to: "/app/exams", label: "Exams & results", phase: 2 },
  { to: "/app/certificates", label: "Certificates", phase: 2 },
];

export default function AppLayout() {
  return (
    <div className="portal">
      <header className="portal-top">
        <Link className="brand" to="/">
          <span className="seal">CC</span> CollegeConnect
        </Link>
        <Link className="btn btn-ghost btn-sm" to="/">
          Help desk
        </Link>
      </header>
      <div className="portal-body">
        <nav className="portal-nav" aria-label="Portal">
          {NAV.map((item) =>
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

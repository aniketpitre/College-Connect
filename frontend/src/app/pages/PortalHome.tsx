import { Link } from "react-router";
import { EmptyState } from "../../components/EmptyState";

export default function PortalHome() {
  return (
    <>
      <div className="eyebrow">CollegeConnect portal</div>
      <h1>Welcome</h1>
      <EmptyState title="Sign-in and role dashboards arrive in Phase 1">
        Until then, staff can open <Link to="/app/admin">help desk analytics</Link> with the admin token.
      </EmptyState>
    </>
  );
}

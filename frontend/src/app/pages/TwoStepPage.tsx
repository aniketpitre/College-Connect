import { Link } from "react-router";
import "../auth.css";

/** Replaced by the full 2-step verification screen in PR 1.3. */
export default function TwoStepPage() {
  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>2-step verification</h1>
        <p className="auth-intro">2-step verification is required for this account.</p>
        <Link to="/login">Back to sign in</Link>
      </div>
    </div>
  );
}

import { Navigate, useLocation } from "react-router";
import { pendingStep, useMe } from "../lib/auth";

/** Sends signed-out users to sign in, and signed-in users to any step they must finish first. */
export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const { data: me, isLoading, isError } = useMe();
  const location = useLocation();

  if (isLoading) return <div className="auth-loading">Loading…</div>;
  if (isError) return <div className="auth-loading">Could not reach the server. Please refresh.</div>;
  if (!me) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  const step = pendingStep(me);
  if (step && step !== location.pathname) return <Navigate to={step} replace />;
  return <>{children}</>;
}

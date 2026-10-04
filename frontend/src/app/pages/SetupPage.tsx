import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { ApiError, apiFetch } from "../../lib/api";
import "../auth.css";
import PasswordInput from "../PasswordInput";

/** One-time creation of the first System Admin (needs SETUP_TOKEN on the server). Staff-facing: English. */
export default function SetupPage() {
  const status = useQuery({ queryKey: ["auth", "setup"], queryFn: () => apiFetch<{ needs_setup: boolean }>("/auth/setup") });
  const [form, setForm] = useState({ setup_token: "", name: "", email: "", password: "", confirm: "" });
  const setup = useMutation({
    mutationFn: () =>
      apiFetch("/auth/setup", {
        method: "POST",
        body: JSON.stringify({ setup_token: form.setup_token, name: form.name, email: form.email, password: form.password }),
      }),
  });
  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }));
  const err = setup.error instanceof ApiError ? setup.error : null;
  const mismatch = form.confirm.length > 0 && form.password !== form.confirm;

  return (
    <div className="auth-page">
      <form
        className="auth-card"
        onSubmit={(e) => {
          e.preventDefault();
          if (!mismatch) setup.mutate();
        }}
      >
        <div className="auth-card-top">
          <span className="brand">
            <span className="seal">CC</span> CollegeConnect
          </span>
        </div>
        <h1>First-time setup</h1>
        {setup.isSuccess ? (
          <>
            <div className="form-success">The System Admin account is ready.</div>
            <p className="auth-intro">Sign in with your email. You will be asked to set up 2-step verification with an authenticator app.</p>
            <Link className="btn btn-primary auth-submit" to="/login">
              Go to sign in
            </Link>
          </>
        ) : status.data && !status.data.needs_setup ? (
          <>
            <p className="auth-intro">Setup is already complete (or not enabled on this server).</p>
            <Link className="btn btn-primary auth-submit" to="/login">
              Go to sign in
            </Link>
          </>
        ) : (
          <>
            <p className="auth-intro">Create the first System Admin account. You need the setup token from the server configuration.</p>
            {err && (
              <div className="form-error" role="alert">
                {err.message}
              </div>
            )}
            {(
              [
                ["setup_token", "Setup token", "off"],
                ["name", "Your full name", "name"],
                ["email", "Email", "email"],
              ] as const
            ).map(([key, label, autoComplete]) => (
              <div className="field" key={key}>
                <label htmlFor={key}>{label}</label>
                <input id={key} value={form[key]} onChange={(e) => set(key)(e.target.value)} autoComplete={autoComplete} type={key === "email" ? "email" : "text"} required />
              </div>
            ))}
            <div className="field">
              <label htmlFor="password">Password</label>
              <PasswordInput id="password" value={form.password} onChange={set("password")} autoComplete="new-password" showLabel="Show" hideLabel="Hide" />
              <span className="field-hint">At least 10 characters; not your name or email.</span>
            </div>
            <div className="field">
              <label htmlFor="confirm">Type the password again</label>
              <PasswordInput id="confirm" value={form.confirm} onChange={set("confirm")} autoComplete="new-password" showLabel="Show" hideLabel="Hide" invalid={mismatch} />
              {mismatch && <span className="field-error">The two passwords don't match.</span>}
            </div>
            <button type="submit" className="btn btn-primary auth-submit" disabled={setup.isPending || mismatch}>
              {setup.isPending ? "Creating…" : "Create admin account"}
            </button>
          </>
        )}
      </form>
    </div>
  );
}

import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const now = new Date().toISOString();
const SESSIONS = [
  { id: "a", current: true, created_at: now, last_seen_at: now, ip: "10.0.0.1", user_agent: "Mozilla/5.0 (Linux; Android 14) Chrome/130.0 Mobile Safari/537.36" },
  { id: "b", current: false, created_at: now, last_seen_at: now, ip: "10.0.0.2", user_agent: "Mozilla/5.0 (Windows NT 10.0) Firefox/131.0" },
];

function api(mfa: object, extra: (m: string, p: string, b: unknown) => { status: number; body?: unknown } | null = () => null) {
  return mockApi((method, path, body) => {
    const r = extra(method, path, body);
    if (r) return r;
    if (path === "/auth/me") return { status: 200, body: makeMe({ kind: "student", prn: "2026BCA001", roles: ["student"], role_labels: ["Student"] }) };
    if (path === "/auth/mfa") return { status: 200, body: mfa };
    if (path === "/auth/sessions") return { status: 200, body: SESSIONS };
    if (path === "/auth/login-history")
      return {
        status: 200,
        body: [
          { at: now, action: "auth.login.succeeded", ip: "10.0.0.1", reason: null },
          { at: now, action: "auth.login.failed", ip: "10.0.0.9", reason: "wrong_password" },
        ],
      };
    return { status: 404 };
  });
}

describe("my account", () => {
  it("lists devices and recent activity, and signs out another device", async () => {
    const calls = api({ enabled: false, required: false, recovery_codes_left: 0, enabled_at: null }, (m, p) =>
      m === "DELETE" && p === "/auth/sessions/b" ? { status: 204 } : null,
    );
    renderApp("/app/account");
    expect(await screen.findByText("Chrome · Android")).toBeTruthy();
    expect(screen.getByText("This device")).toBeTruthy();
    expect(screen.getByText("Failed sign-in attempt")).toBeTruthy();
    const other = screen.getByText("Firefox · Windows").closest("li")!;
    fireEvent.click(within(other).getByRole("button", { name: "Sign out" }));
    await vi.waitFor(() => expect(calls.some((c) => c.method === "DELETE" && c.path === "/auth/sessions/b")).toBe(true));
  });

  it("turns off optional 2-step after the password is confirmed", async () => {
    const calls = api({ enabled: true, required: false, recovery_codes_left: 6, enabled_at: now }, (m, p) =>
      m === "POST" && p === "/auth/mfa/disable" ? { status: 200, body: makeMe() } : null,
    );
    renderApp("/app/account");
    expect(await screen.findByText("6 recovery codes left")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Turn off" }));
    fireEvent.change(screen.getByLabelText("Enter your password to confirm"), { target: { value: "my-password-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
    await vi.waitFor(() => expect(calls.find((c) => c.path === "/auth/mfa/disable")?.body).toEqual({ password: "my-password-1" }));
  });

  it("does not offer turning off 2-step when the role requires it", async () => {
    api({ enabled: true, required: true, recovery_codes_left: 8, enabled_at: now });
    renderApp("/app/account");
    expect(await screen.findByText("Required for your role")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Turn off" })).toBeNull();
    expect(screen.getByRole("button", { name: "Get new recovery codes" })).toBeTruthy();
  });
});

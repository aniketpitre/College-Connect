import { cleanup, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeMe, mockApi, renderApp, signedOut } from "../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("public routes", () => {
  it("serves the help desk at /", () => {
    mockApi(() => signedOut);
    renderApp("/");
    expect(screen.getByRole("heading", { name: "How can I help you today?" })).toBeTruthy();
  });

  it("redirects the old /#/admin link to the admin portal", () => {
    mockApi(() => signedOut);
    renderApp("/#/admin");
    expect(screen.getByRole("heading", { name: "Admin portal" })).toBeTruthy();
  });

  it("shows the verification code on the verify page", () => {
    renderApp("/verify/ABC123");
    expect(screen.getByText("ABC123")).toBeTruthy();
  });

  it("shows not found for unknown paths", () => {
    renderApp("/no/such/page");
    expect(screen.getByRole("heading", { name: "Page not found" })).toBeTruthy();
  });
});

describe("portal access", () => {
  it("sends signed-out visitors to sign in", async () => {
    mockApi(() => signedOut);
    renderApp("/app");
    expect(await screen.findByRole("heading", { name: "Sign in to CollegeConnect" })).toBeTruthy();
  });

  it("shows the portal to signed-in users", async () => {
    mockApi((_m, path) => (path === "/auth/me" ? { status: 200, body: makeMe() } : { status: 404 }));
    renderApp("/app");
    expect(await screen.findByRole("heading", { name: "Welcome, Asha" })).toBeTruthy();
    expect(screen.getByText("Faculty")).toBeTruthy();
    expect(screen.getByText("Students").closest("[aria-disabled]")).toBeTruthy();
  });

  it("forces a password change before anything else", async () => {
    mockApi(() => ({ status: 200, body: makeMe({ kind: "student", prn: "2026BCA001", must_change_password: true }) }));
    renderApp("/app");
    expect(await screen.findByRole("heading", { name: "Set a new password" })).toBeTruthy();
  });

  it("sends accounts that still need 2-step verification to that step", async () => {
    mockApi(() => ({ status: 200, body: makeMe({ session_state: "mfa_setup" }) }));
    renderApp("/app");
    expect(await screen.findByRole("heading", { name: "2-step verification" })).toBeTruthy();
  });
});

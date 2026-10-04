import { cleanup, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

const receipt = {
  type: "receipt", valid: true, status: "valid", number: "R/2026-27/000042", date: "2026-10-04T08:30:00Z", amount: 1_300_000,
  academic_year: "2026-27", student_name: "Rohan P.", prn: "2026BCA***", college: "Shivaji College", cancelled_at: null,
};

describe("verify page", () => {
  it("confirms a genuine receipt without signing in", async () => {
    const calls = mockApi((_m, path) => (path === "/verify/ABCD2345EFGH" ? { status: 200, body: receipt } : { status: 404 }));
    renderApp("/verify/ABCD2345EFGH");
    expect(await screen.findByText("✓ Genuine receipt")).toBeTruthy();
    expect(screen.getByText("R/2026-27/000042")).toBeTruthy();
    expect(screen.getByText("₹13,000.00")).toBeTruthy();
    expect(screen.getByText("Rohan P. · 2026BCA***")).toBeTruthy();
    expect(calls.some((c) => c.path === "/auth/me")).toBe(false); // public: no sign-in check
  });

  it("warns about a cancelled receipt, in Marathi", async () => {
    localStorage.setItem("cc-lang", "mr");
    mockApi(() => ({ status: 200, body: { ...receipt, valid: false, status: "cancelled", cancelled_at: "2026-10-05T08:30:00Z" } }));
    renderApp("/verify/ABCD2345EFGH");
    expect(await screen.findByText("✕ ही पावती रद्द केली आहे")).toBeTruthy();
    expect(screen.getByText("रद्द केल्याचा दिनांक")).toBeTruthy();
  });

  it("says when no receipt matches", async () => {
    mockApi(() => ({ status: 404, body: { error: { code: "not_found", message: "No receipt" } } }));
    renderApp("/verify/NOPE");
    expect(await screen.findByText(/No receipt matches this code/)).toBeTruthy();
  });
});

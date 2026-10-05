import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

const student = makeMe({ kind: "student", name: "Rohan Patil", prn: "2026BCA001", roles: ["student"], role_labels: ["Student"] });
const home = {
  name: "Rohan Patil", prn: "2026BCA001", class: "BCA · FY · A", academic_year: "2026-27", photo_url: null, balance: 1_300_000,
  cards: [
    { kind: "fee_overdue", severity: "danger", amount: 1_300_000, since: "2026-07-15" },
    { kind: "document_rejected", severity: "warning", type: "hsc_marksheet", reason: "Blurred" },
  ],
};
const fees = {
  years: [{ id: "y1", name: "2026-27", is_current: true }, { id: "y0", name: "2025-26", is_current: false }],
  academic_year_id: "y1",
  balance: 1_300_000, demand: 2_600_000, charges: 0, paid: 1_300_000, concessions: 0, scholarships: 0, refunds: 0, overdue: 1_300_000,
  installments: [{ label: "First", due_date: "2026-07-15", amount: 1_300_000, paid: 1_300_000, due: 0, overdue: false }, { label: "Second", due_date: "2026-09-15", amount: 1_300_000, paid: 0, due: 1_300_000, overdue: true }],
  by_head: [], has_demand: true,
  entries: [
    { id: "e1", at: "2026-06-10T10:00:00Z", type: "demand", label: "Fee for the year", amount: 2_600_000, lines: [], reason: null, receipt_number: null, receipt_id: null, reverses: null, reversed: false },
    { id: "e2", at: "2026-07-01T10:00:00Z", type: "payment", label: "Payment", amount: -1_300_000, lines: [], reason: null, receipt_number: "R/2026-27/000001", receipt_id: "r1", reverses: null, reversed: false },
  ],
  receipts: [{ id: "r1", number: "R/2026-27/000001", amount: 1_300_000, mode_label: "UPI", reference: "", collected_at: "2026-07-01T10:00:00Z", status: "valid" }],
};

describe("student portal", () => {
  it("home shows what needs attention, in Hindi when chosen", async () => {
    localStorage.setItem("cc-lang", "hi");
    mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: student };
      if (path === "/me/home") return { status: 200, body: home };
      return { status: 404 };
    });
    renderApp("/app");
    expect(await screen.findByRole("heading", { name: "नमस्ते, Rohan" })).toBeTruthy();
    expect(screen.getByText(/आपकी ₹13,000.00 फ़ीस बकाया है/)).toBeTruthy();
    expect(screen.getByText(/HSC \(12वीं\) अंकपत्र स्वीकार नहीं हुआ/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "प्रश्न पूछें" }).getAttribute("href")).toBe("/");
    expect(screen.getByRole("link", { name: "फ़ीस और रसीदें" }).getAttribute("href")).toBe("/app/my-fees"); // student menu
  });

  it("my fees: balance, installments, receipt download, statement and year switch", async () => {
    const calls = mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: student };
      if (path.startsWith("/me/fees")) return { status: 200, body: fees };
      return { status: 404 };
    });
    renderApp("/app/my-fees");
    expect((await screen.findAllByText("₹13,000.00 overdue")).length).toBe(2); // tile and installment
    expect(screen.getByRole("link", { name: "Download" }).getAttribute("href")).toBe("/api/v1/me/receipts/r1/pdf");
    expect(screen.getByRole("link", { name: "Download fee statement (PDF)" }).getAttribute("href")).toBe("/api/v1/me/fees/statement.pdf?academic_year_id=y1");
    expect(screen.getByText("Payment · R/2026-27/000001")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Year"), { target: { value: "y0" } });
    await waitFor(() => expect(calls.some((c) => c.path === "/me/fees?academic_year_id=y0")).toBe(true));
  });

  it("staff home shows shortcuts for their roles only", async () => {
    mockApi((_m, path) => (path === "/auth/me" ? { status: 200, body: makeMe({ permissions: ["fees.read", "students.read"] }) } : { status: 404 }));
    renderApp("/app");
    expect(await screen.findByRole("link", { name: "Fees & receipts →" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Students →" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Users →" })).toBeNull();
  });
});

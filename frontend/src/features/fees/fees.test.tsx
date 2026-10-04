import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { FeeAccount } from "../../lib/fees";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const year = { id: "y1", status: "active", name: "2026-27", start_date: "2026-06-01", end_date: "2027-05-31", is_current: true };
const setup = {
  institution: {}, current_year: year, academic_years: [year], departments: [], divisions: [],
  programmes: [{ id: "p1", status: "active", code: "BCA", name: "BCA", department_id: "d1", level: "UG", duration_years: 3, semesters_per_year: 2, year_labels: ["FY", "SY", "TY"] }],
  categories: [{ id: "c1", status: "active", code: "OBC", name: "OBC", reserved_percent: null }],
};
const heads = [
  { id: "h1", code: "TUITION", name: "Tuition fee", status: "active" },
  { id: "h2", code: "DEV", name: "Development fee", status: "active" },
];
const accounts = makeMe({ roles: ["accounts"], permissions: ["setup.read", "students.read", "fees.read", "fees.manage", "fees.collect"] });

const account: FeeAccount = {
  student_id: "s1", academic_year_id: "y1",
  student: { id: "s1", prn: "2026BCA001", name: "Rohan Patil", phone: null, email: null, programme_id: "p1", programme_code: "BCA", year_of_study: 1, year_label: "FY", division_id: null, division: "A", roll_no: null, category_code: "OBC", status: "active", has_photo: false },
  balance: 2_100_000, demand: 2_600_000, charges: 0, paid: 0, concessions: 500_000, scholarships: 0, refunds: 0, overdue: 1_300_000, late_fee: 10_000,
  installments: [
    { label: "First", due_date: "2026-07-15", amount: 1_300_000, paid: 0, due: 1_300_000, overdue: true },
    { label: "Second", due_date: "2026-11-15", amount: 1_300_000, paid: 500_000, due: 800_000, overdue: false },
  ],
  by_head: [{ head_id: "h1", code: "TUITION", name: "Tuition fee", outstanding: 1_500_000 }, { head_id: "h2", code: "DEV", name: "Development fee", outstanding: 600_000 }],
  entries: [
    { id: "e1", at: "2026-06-10T10:00:00Z", type: "demand", label: "Fee for the year", amount: 2_600_000, lines: [], reason: null, receipt_number: null, receipt_id: null, reverses: null, reversed: false },
    { id: "e2", at: "2026-06-12T10:00:00Z", type: "concession", label: "Concession", amount: -500_000, lines: [], reason: "Staff ward", receipt_number: null, receipt_id: null, reverses: null, reversed: false },
  ],
  has_demand: true,
};

describe("fee setup", () => {
  it("builds a structure in rupees and sends paise, with installments that add up", async () => {
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: accounts };
      if (path === "/setup") return { status: 200, body: setup };
      if (path === "/fees/heads") return { status: 200, body: heads };
      if (path.startsWith("/fees/structures") && method === "GET") return { status: 200, body: [] };
      if (path === "/fees/structures") return { status: 201, body: {} };
      return { status: 404 };
    });
    renderApp("/app/fees/setup");
    fireEvent.click(await screen.findByRole("button", { name: "Add structure" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Name"), { target: { value: "BCA FY" } });
    fireEvent.change(within(dialog).getByLabelText("Amount 1"), { target: { value: "20,000" } });
    fireEvent.change(within(dialog).getByLabelText("Amount 2"), { target: { value: "5000.50" } });
    expect(within(dialog).getByText("Total ₹25,000.50")).toBeTruthy();
    const save = within(dialog).getByRole("button", { name: "Save structure" }) as HTMLButtonElement;
    expect(save.disabled).toBe(true); // installments don't add up yet
    fireEvent.click(within(dialog).getByRole("button", { name: "+ Add installment" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Split equally" }));
    fireEvent.change(within(dialog).getByLabelText("Installment 1 due date"), { target: { value: "2026-07-15" } });
    fireEvent.change(within(dialog).getByLabelText("Installment 2 due date"), { target: { value: "2026-11-15" } });
    await waitFor(() => expect(save.disabled).toBe(false));
    fireEvent.click(save);
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/fees/structures")).toBe(true));
    const body = calls.find((c) => c.method === "POST")!.body as { items: { amount: number }[]; installments: { amount: number }[]; category_id: null; year_of_study: number };
    expect(body.items.map((i) => i.amount)).toEqual([2_000_000, 500_050]);
    expect(body.installments.map((i) => i.amount)).toEqual([1_250_025, 1_250_025]);
    expect(body.category_id).toBeNull();
    expect(body.year_of_study).toBe(1);
  });
});

describe("student fee account", () => {
  it("shows the balance, overdue installment and statement, and requests a concession", async () => {
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: accounts };
      if (path === "/setup") return { status: 200, body: setup };
      if (path === "/fees/heads") return { status: 200, body: heads };
      if (path.startsWith("/fees/students/s1")) return { status: 200, body: account };
      if (path.startsWith("/fees/scholarships")) return { status: 200, body: [] };
      if (path.startsWith("/approvals")) return { status: 200, body: [] };
      if (path === "/fees/concessions" && method === "POST") return { status: 201, body: {} };
      return { status: 404 };
    });
    renderApp("/app/fees/students/s1");
    expect(await screen.findByRole("heading", { name: "Rohan Patil" })).toBeTruthy();
    expect(screen.getByText("₹13,000.00 overdue")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Collect fee" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Apply late fee/ })).toBeTruthy();
    expect(screen.getByText("Staff ward")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Request concession" }));
    fireEvent.change(screen.getByLabelText(/^Amount/), { target: { value: "1000" } });
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Sibling studies here" } });
    fireEvent.change(screen.getByLabelText("Type"), { target: { value: "sibling" } });
    fireEvent.click(screen.getByRole("button", { name: "Send for approval" }));
    await waitFor(() =>
      expect(calls.find((c) => c.path === "/fees/concessions")?.body).toEqual({ student_id: "s1", academic_year_id: "y1", head_id: "h1", amount: 100_000, kind: "sibling", reason: "Sibling studies here" }),
    );
  });
});

describe("approvals", () => {
  const request = (by: string) => ({
    id: "a1", kind: "concession", kind_label: "Concession", status: "pending", student_id: "s1", student_name: "Rohan Patil", prn: "2026BCA001",
    academic_year_id: "y1", amount: 500_000, reason: "Child of a teacher", details: { head: "TUITION", concession_label: "Staff ward" },
    requested_by: "Kavita", requested_by_id: by, requested_at: "2026-10-01T10:00:00Z", decided_by: null, decided_at: null, decision_reason: null,
  });
  const principal = makeMe({ id: "pr1", roles: ["principal"], permissions: ["fees.read", "approvals.decide"] });

  it("the principal approves a concession", async () => {
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: principal };
      if (path.startsWith("/approvals?")) return { status: 200, body: [request("acc1")] };
      if (method === "POST") return { status: 200, body: {} };
      return { status: 404 };
    });
    renderApp("/app/approvals");
    expect(await screen.findByText(/Staff ward concession on TUITION/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(calls.find((c) => c.path === "/approvals/a1/decide")?.body).toEqual({ approve: true }));
  });

  it("hides the buttons on your own request", async () => {
    mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: principal };
      if (path.startsWith("/approvals?")) return { status: 200, body: [request("pr1")] };
      return { status: 404 };
    });
    renderApp("/app/approvals");
    expect(await screen.findByText(/another approver must decide/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
  });
});

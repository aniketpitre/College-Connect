import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const year = { id: "y1", status: "active", name: "2026-27", start_date: "2026-06-01", end_date: "2027-05-31", is_current: true };
const setup = { institution: {}, current_year: year, academic_years: [year], departments: [], divisions: [], programmes: [], categories: [] };
const accounts = makeMe({ roles: ["accounts"], permissions: ["fees.read", "fees.collect", "students.read"] });
const account = {
  student_id: "s1", academic_year_id: "y1",
  student: { id: "s1", prn: "2026BCA001", name: "Rohan Patil", programme_code: "BCA", year_label: "FY", division: "A" },
  balance: 2_600_000, demand: 2_600_000, charges: 0, paid: 0, concessions: 0, scholarships: 0, refunds: 0, overdue: 1_300_000, late_fee: 0,
  installments: [
    { label: "First", due_date: "2026-07-15", amount: 1_300_000, paid: 0, due: 1_300_000, overdue: true },
    { label: "Second", due_date: "2026-11-15", amount: 1_300_000, paid: 0, due: 1_300_000, overdue: false },
  ],
  by_head: [], entries: [], has_demand: true,
};

describe("collect fee", () => {
  it("takes a UPI payment and shows the receipt with print and email", async () => {
    const calls = mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: accounts };
      if (path === "/setup") return { status: 200, body: setup };
      if (path.startsWith("/fees/students/s1")) return { status: 200, body: account };
      if (path === "/fees/collect")
        return {
          status: 201,
          body: { id: "r1", number: "R/2026-27/000042", amount: 1_300_000, student: { name: "Rohan Patil", prn: "2026BCA001", class: "BCA FY A" }, mode_label: "UPI", reference: "UPI98765", lines: [{ code: "TUITION", name: "Tuition fee", amount: 1_300_000 }] },
        };
      if (path === "/fees/receipts/r1/email") return { status: 200, body: { sent_to: "rohan@example.in" } };
      return { status: 404 };
    });
    renderApp("/app/fees/collect/s1");
    fireEvent.click(await screen.findByRole("button", { name: "Overdue now: ₹13,000.00" }));
    expect((screen.getByLabelText("Amount received") as HTMLInputElement).value).toBe("13000");
    fireEvent.click(screen.getByLabelText("UPI"));
    fireEvent.change(screen.getByLabelText("UPI transaction ID"), { target: { value: "UPI98765" } });
    fireEvent.click(screen.getByRole("button", { name: "Receive ₹13,000.00 and issue receipt" }));

    expect(await screen.findByRole("heading", { name: "R/2026-27/000042" })).toBeTruthy();
    expect((screen.getByRole("link", { name: "Print receipt" }) as HTMLAnchorElement).getAttribute("href")).toBe("/api/v1/fees/receipts/r1/pdf");
    expect(calls.find((c) => c.path === "/fees/collect")?.body).toMatchObject({ student_id: "s1", academic_year_id: "y1", amount: 1_300_000, mode: "upi", reference: "UPI98765" });
    fireEvent.click(screen.getByRole("button", { name: "Email to student" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Emailed to rohan@example.in" })).toBeTruthy());
  });

  it("asks for the bank for a cheque and shows server errors", async () => {
    mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: accounts };
      if (path === "/setup") return { status: 200, body: setup };
      if (path.startsWith("/fees/students/s1")) return { status: 200, body: account };
      if (path === "/fees/collect") return { status: 422, body: { error: { code: "validation_error", message: "Only ₹26,000.00 is due.", field: "amount" } } };
      return { status: 404 };
    });
    renderApp("/app/fees/collect/s1");
    fireEvent.change(await screen.findByLabelText("Amount received"), { target: { value: "30000" } });
    fireEvent.click(screen.getByLabelText("Cheque"));
    expect(screen.getByLabelText("Bank")).toBeTruthy();
    expect(screen.getByLabelText("Cheque date")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Cheque number"), { target: { value: "004512" } });
    fireEvent.change(screen.getByLabelText("Bank"), { target: { value: "SBI" } });
    fireEvent.click(screen.getByRole("button", { name: /issue receipt/ }));
    expect(await screen.findByText("Only ₹26,000.00 is due.")).toBeTruthy();
  });
});

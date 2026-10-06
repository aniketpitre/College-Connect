import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
  delete window.Razorpay;
});

const student = makeMe({ kind: "student", name: "Rohan Patil", prn: "2026BCA001", roles: ["student"], role_labels: ["Student"] });
const fees = {
  years: [{ id: "y1", name: "2026-27", is_current: true }],
  academic_year_id: "y1",
  online_payment: true,
  balance: 1_300_000, demand: 2_600_000, charges: 0, paid: 1_300_000, concessions: 0, scholarships: 0, refunds: 0, overdue: 500_000,
  installments: [], by_head: [], has_demand: true, entries: [], receipts: [],
};

describe("online payment", () => {
  it("a student pays the overdue amount and gets the receipt number", async () => {
    let opened: Record<string, unknown> = {};
    window.Razorpay = class {
      constructor(options: Record<string, unknown>) {
        opened = options;
      }
      open() {
        (opened.handler as (r: unknown) => void)({ razorpay_payment_id: "pay_1", razorpay_order_id: "order_1", razorpay_signature: "sig" });
      }
    };
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: student };
      if (path.startsWith("/me/fees")) return { status: 200, body: fees };
      if (path === "/me/payments")
        return { status: 201, body: { id: "p1", order_id: "order_1", key_id: "rzp_test_1", amount: 500_000, currency: "INR", name: "Demo College", description: "Fees", prefill: { name: "Rohan Patil", email: "", contact: "" } } };
      if (path === "/me/payments/p1/confirm") return { status: 200, body: { id: "p1", status: "paid", receipt_number: "R/2026-27/000042" } };
      return { status: method === "GET" ? 404 : 200 };
    });
    renderApp("/app/my-fees");
    fireEvent.click(await screen.findByRole("button", { name: "Pay online" }));
    expect((screen.getByLabelText("Amount") as HTMLInputElement).value).toBe("5000"); // the overdue part first
    fireEvent.click(screen.getByRole("button", { name: "Continue to payment" }));
    expect(await screen.findByText("Payment received. Receipt R/2026-27/000042 is ready to download.")).toBeTruthy();
    expect(opened.key).toBe("rzp_test_1");
    expect(opened.order_id).toBe("order_1");
    expect(calls.find((c) => c.path === "/me/payments")?.body).toEqual({ academic_year_id: "y1", amount: 500_000 });
    expect(calls.find((c) => c.path === "/me/payments/p1/confirm")?.body).toEqual({ razorpay_payment_id: "pay_1", razorpay_signature: "sig" });
  });

  it("no button when the college hasn't set up online payment", async () => {
    mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: student };
      if (path.startsWith("/me/fees")) return { status: 200, body: { ...fees, online_payment: false } };
      return { status: 404 };
    });
    renderApp("/app/my-fees");
    expect(await screen.findByText("Total fee")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Pay online" })).toBeNull();
  });

  it("accounts see the day's payments, check a stuck one and match the gateway file", async () => {
    const accounts = makeMe({ roles: ["accounts"], role_labels: ["Accounts"], permissions: ["fees.read", "fees.collect"] });
    const pay = (id: string, status: string, extra = {}) => ({
      id, student_id: "s1", student: { name: "Rohan Patil", prn: "2026BCA001" }, academic_year: "2026-27", amount: 500_000, status, status_label: status,
      order_id: `order_${id}`, gateway_payment_id: null, method: null, receipt_id: null, receipt_number: null, credit: 0, paid_by: "student",
      created_at: "2026-10-05T05:00:00Z", paid_at: null, settled_by: null, last_error: null, ...extra,
    });
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: accounts };
      if (path.startsWith("/fees/online-payments?"))
        return { status: 200, body: { day: "2026-10-05", enabled: true, payments: [pay("a", "paid", { receipt_number: "R/1" }), pay("b", "created")], paid_count: 1, paid_amount: 500_000, waiting: 1, problems: 0 } };
      if (path === "/fees/online-payments/b/check") return { status: 200, body: pay("b", "paid") };
      if (path === "/fees/online-payments/reconcile")
        return { status: 200, body: { rows: 2, matched: 1, matched_amount: 500_000, amount_differs: [], missing_in_collegeconnect: [{ gateway_payment_id: "pay_x", amount: 25_000, payment: null }], missing_in_gateway_file: [] } };
      return { status: method === "GET" ? 404 : 200 };
    });
    renderApp("/app/fees/online");
    fireEvent.click(await screen.findByRole("button", { name: "Check with gateway" }));
    await waitFor(() => expect(calls.some((c) => c.path === "/fees/online-payments/b/check")).toBe(true));
    fireEvent.change(screen.getByLabelText("Gateway report (CSV)"), { target: { files: [new File(["id,amount"], "p.csv", { type: "text/csv" })] } });
    expect(await screen.findByText(/pay_x ₹250.00/)).toBeTruthy();
  });
});

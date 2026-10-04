import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const year = { id: "y1", status: "active", name: "2026-27", start_date: "2026-06-01", end_date: "2027-05-31", is_current: true };
const setup = { institution: {}, current_year: year, academic_years: [year], departments: [], divisions: [], programmes: [], categories: [] };
const accounts = makeMe({ roles: ["accounts"], permissions: ["fees.read", "fees.manage", "fees.collect"] });

describe("reports", () => {
  it("shows the day book with totals and an Excel link, then switches report", async () => {
    const calls = mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: accounts };
      if (path === "/setup") return { status: 200, body: setup };
      if (path.startsWith("/fees/reports/day-book"))
        return {
          status: 200,
          body: {
            title: "Day book",
            columns: [{ key: "number", header: "Receipt", kind: "text" }, { key: "status", header: "Status", kind: "text" }, { key: "amount", header: "Amount", kind: "money" }],
            rows: [{ number: "R/2026-27/000001", status: "", amount: 2_150_000 }, { number: "R/2026-27/000002", status: "Cancelled", amount: 0 }],
            totals: { Collected: 2_150_000, Cash: 2_150_000, "Cancelled receipts": 1 },
          },
        };
      if (path.startsWith("/fees/reports/defaulters"))
        return { status: 200, body: { title: "Defaulters", columns: [{ key: "prn", header: "PRN", kind: "text" }], rows: [], totals: { Students: 0, Overdue: 0 } } };
      return { status: 404 };
    });
    renderApp("/app/fees/reports");
    expect(await screen.findByText("R/2026-27/000001")).toBeTruthy();
    expect(screen.getAllByText("₹21,500.00").length).toBeGreaterThan(1);
    expect(screen.getByText("Cancelled receipts").nextElementSibling?.textContent).toBe("1"); // a count, not money
    expect(screen.getByRole("link", { name: "Download Excel" }).getAttribute("href")).toMatch(/\/api\/v1\/fees\/reports\/day-book\?.*format=xlsx/);

    fireEvent.click(screen.getByRole("tab", { name: "Defaulters" }));
    expect(await screen.findByText("Nothing for this period.")).toBeTruthy();
    await waitFor(() => expect(calls.some((c) => c.path.startsWith("/fees/reports/defaulters"))).toBe(true));
  });
});

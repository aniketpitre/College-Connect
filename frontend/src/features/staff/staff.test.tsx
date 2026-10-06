import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

const balances = [
  { code: "CL", name: "Casual leave", half_day: true, allowance: 8, taken: 1, pending: 0, available: 7 },
  { code: "OD", name: "On duty", half_day: true, allowance: null, taken: 0, pending: 0, available: null },
];
const request = {
  id: "r1",
  user_id: "u2",
  name: "Amit Deshmukh",
  code: "CL",
  type_name: "Casual leave",
  from_date: "2026-10-21",
  to_date: "2026-10-21",
  half_day: false,
  days: 1,
  reason: "Family function",
  status: "pending",
  approver: "hod",
  decided_by: null,
  decided_at: null,
  note: null,
  applied_at: "2026-10-05T05:00:00Z",
  balance: balances[0],
  lectures: [{ date: "2026-10-21", start: "09:00", end: "10:00", subject: "BCA101", division: "FY BCA A", slot_id: "s1" }],
};

describe("staff and leave", () => {
  it("a teacher applies for casual leave", async () => {
    const teacher = makeMe({ roles: ["faculty"], role_labels: ["Faculty"], permissions: ["leave.apply"] });
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: teacher };
      if (path === "/me/leave" && method === "GET") return { status: 200, body: { year: "2026-27", today: "2026-10-05", balances, requests: [], approver: "hod", can_approve: false } };
      if (path === "/me/leave") return { status: 201, body: request };
      return { status: 404 };
    });
    renderApp("/app/leave");
    expect(await screen.findByText("7 left")).toBeTruthy();
    expect(screen.getByText(/goes to your HOD/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2026-10-21" } });
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Family function" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() =>
      expect(calls.find((c) => c.path === "/me/leave" && c.method === "POST")?.body).toEqual({
        code: "CL",
        from_date: "2026-10-21",
        to_date: "2026-10-21",
        half_day: false,
        reason: "Family function",
      }),
    );
  });

  it("the HOD sees the lectures to cover and approves", async () => {
    const hod = makeMe({ roles: ["hod"], role_labels: ["HOD"], permissions: ["leave.apply", "leave.approve", "staff.read.dept"] });
    const calls = mockApi((_method, path) => {
      if (path === "/auth/me") return { status: 200, body: hod };
      if (path === "/me/leave") return { status: 200, body: { year: "2026-27", today: "2026-10-05", balances, requests: [], approver: "principal", can_approve: true } };
      if (path.startsWith("/leave/requests?")) return { status: 200, body: [request] };
      if (path === "/leave/requests/r1/decide") return { status: 200, body: { ...request, status: "approved" } };
      return { status: 404 };
    });
    renderApp("/app/leave");
    expect(await screen.findByText(/Lectures to cover \(1\)/)).toBeTruthy();
    expect(screen.getByText(/BCA101 \(FY BCA A\)/)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Reject" }) as HTMLButtonElement).disabled).toBe(true); // needs a note
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(calls.find((c) => c.path === "/leave/requests/r1/decide")?.body).toEqual({ approve: true, note: null }));
  });

  it("the office sees the NAAC staff summary", async () => {
    const office = makeMe({ roles: ["office"], role_labels: ["Office"], permissions: ["staff.read", "staff.manage", "leave.apply"] });
    mockApi((_method, path) => {
      if (path === "/auth/me") return { status: 200, body: office };
      if (path === "/staff") return { status: 200, body: [] };
      if (path === "/staff/summary")
        return {
          status: 200,
          body: { staff: 5, teaching: 4, non_teaching: 1, phd: 2, net_set: 3, by_employment: { permanent: 3, contract: 1, visiting: 0, ad_hoc: 0 }, missing_records: 1, by_department: [{ department: "Computer Science", teachers: 4, phd: 2 }] },
        };
      return { status: 404 };
    });
    renderApp("/app/staff");
    fireEvent.click(await screen.findByRole("tab", { name: "NAAC summary" }));
    expect(await screen.findByText("Teachers with Ph.D.")).toBeTruthy();
    expect(screen.getByText(/4 teachers · 2 with Ph.D./)).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Leave types" })).toBeTruthy();
  });
});

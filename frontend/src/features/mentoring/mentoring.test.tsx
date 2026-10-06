import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

const rohan = {
  student_id: "s1",
  name: "Rohan Patil",
  prn: "2026BCA001",
  class: "BCA FY A",
  level: "high",
  reasons: ["Attendance 62.5% (minimum 75%)", "Attendance fell from 100% to 0% in the last 4 weeks"],
  signals: { attendance: 62.5 },
  mentor: "Amit Deshmukh",
  notes: 0,
  last_note_at: null,
  follow_up_on: null,
  computed_at: "2026-10-05T03:30:00Z",
};

describe("mentoring", () => {
  it("a mentor sees a mentee's reasons and writes a counselling note", async () => {
    const mentor = makeMe({ roles: ["mentor"], role_labels: ["Mentor"], permissions: ["mentoring.mentees", "setup.read"] });
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: mentor };
      if (path === "/mentoring/mentees") return { status: 200, body: { students: [rohan], high: 1, medium: 0 } };
      if (path === "/risk/students/s1" && method === "GET") return { status: 200, body: { ...rohan, history: [] } };
      if (path === "/risk/students/s1/notes")
        return { status: 201, body: { ...rohan, notes: 1, history: [{ id: "n1", at: "2026-10-05T05:00:00Z", by: "Amit Deshmukh", text: "Talked to Rohan", follow_up_on: null }] } };
      return { status: 404 };
    });
    renderApp("/app/mentoring");
    expect(await screen.findByText("Attendance fell from 100% to 0% in the last 4 weeks")).toBeTruthy();
    expect(screen.queryByRole("tab", { name: "Rules" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Rohan Patil/ }));
    fireEvent.change(await screen.findByLabelText("What you discussed and agreed"), { target: { value: "Talked to Rohan" } });
    fireEvent.click(screen.getByRole("button", { name: "Save note" }));
    await waitFor(() => expect(calls.find((c) => c.path === "/risk/students/s1/notes")?.body).toEqual({ text: "Talked to Rohan", follow_up_on: null }));
  });

  it("the Principal sees the college at a glance on the home page", async () => {
    const principal = makeMe({ roles: ["principal"], role_labels: ["Principal"], permissions: ["risk.read", "risk.manage", "approvals.decide", "setup.read"] });
    mockApi((_method, path) => {
      if (path === "/auth/me") return { status: 200, body: principal };
      if (path === "/dashboard")
        return {
          status: 200,
          body: {
            overview: {
              year: "2026-27",
              admissions: { seats: 60, applied: 75, admitted: 52 },
              fees: { demand: 100_00000, waived: 0, collected: 62_00000, outstanding: 38_00000, percent: 62 },
              marks: { sheets: 15, done: 10, percent: 66.7 },
              attendance: { average: 81.2, below_minimum: 7, minimum: 75, as_of: null },
              certificates: { issued_90_days: 4, average_days: 1.5, overdue: 1 },
              risk: { high: 3, medium: 9 },
              pending: { approvals: 1, leave: 2, grievances_overdue: 0 },
            },
            risk: { high: 3, medium: 9 },
          },
        };
      return { status: 404 };
    });
    renderApp("/app");
    expect(await screen.findByText("College at a glance · 2026-27")).toBeTruthy();
    expect(screen.getByText("52/60")).toBeTruthy();
    expect(screen.getByText("7 below 75%")).toBeTruthy();
    expect(screen.getByText("Students at high risk")).toBeTruthy();
    expect(screen.queryByText("Students who may need help")).toBeNull(); // shown once, in the overview
  });
});

import { cleanup, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

const hod = makeMe({ name: "Dr. Mehta", roles: ["hod"], role_labels: ["HOD"], permissions: ["attendance.take", "attendance.approve", "marks.approve"] });
const dashboard = {
  teaching: {
    holiday: null,
    lectures: [
      { slot_id: "s1", date: "2026-10-05", start: "09:00", end: "10:00", code: "BCA101", class: "BCA · FY · A", status: "scheduled", takeable: true, taken: false },
      { slot_id: "s2", date: "2026-10-05", start: "11:00", end: "12:00", code: "BCA102", class: "BCA · FY · A", status: "scheduled", takeable: true, taken: true },
    ],
    marks_tasks: [{ division_id: "d1", subject_id: "sub1", label: "BCA · FY · A · BCA101", status: "Draft", complete: 1, students: 3, deadline: "2026-10-20" }],
  },
  hod: {
    classes: [{ division_id: "d1", class: "BCA · FY · A", students: 3, attendance: 72.5, defaulters: 1 }],
    attendance_requests: 2,
    marks_to_approve: 0,
    workload: [{ name: "Anita Rao", hours: 6 }],
  },
};

describe("home dashboards", () => {
  it("staff see only the sections their roles allow, with links to act", async () => {
    mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: hod };
      if (path === "/dashboard") return { status: 200, body: dashboard };
      return { status: 404 };
    });
    renderApp("/app");
    expect(await screen.findByRole("heading", { name: "Today's lectures" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Take attendance" }).getAttribute("href")).toBe("/app/attendance/take/s1/2026-10-05");
    expect(screen.getByText("Taken ✓")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Open →" }).getAttribute("href")).toBe("/app/exams/marks/d1/sub1");
    expect(screen.getByRole("link", { name: /Attendance edits to approve/ }).textContent).toContain("2");
    expect(screen.getByText("72.5%")).toBeTruthy();
    expect(screen.getByText("6 h")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Office" })).toBeNull();
  });

  it("students see exam and certificate cards in their language", async () => {
    localStorage.setItem("cc-lang", "mr");
    const student = makeMe({ kind: "student", name: "Rohan Patil", prn: "2026BCA001", roles: ["student"], role_labels: ["Student"] });
    const home = {
      name: "Rohan Patil", prn: "2026BCA001", class: "BCA · FY · A", academic_year: "2026-27", photo_url: null, balance: null,
      cards: [
        { kind: "exam_form", severity: "warning", title: "Oct 2026 exams", due_date: "2026-10-10" },
        { kind: "certificate_ready", severity: "info", type: "bonafide" },
      ],
    };
    mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: student };
      if (path === "/me/home") return { status: 200, body: home };
      return { status: 404 };
    });
    renderApp("/app");
    expect(await screen.findByText(/Oct 2026 exams चा परीक्षा अर्ज/)).toBeTruthy();
    expect(screen.getByText(/तुमचे बोनाफाईड प्रमाणपत्र तयार आहे/)).toBeTruthy();
  });
});

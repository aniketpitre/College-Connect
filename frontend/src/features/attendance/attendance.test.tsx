import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const lecture = {
  id: "s1", slot_id: "s1", timetable_id: "t1", division_id: "v1", day: 1, day_name: "Monday", start: "09:00", end: "10:00",
  subject_id: "sub1", subject_code: "BCA101", subject_name: "Programming in C", subject_type: "theory", faculty_ids: ["u1"],
  faculty: ["Asha Kulkarni"], room: "101", batch: null, date: "2026-07-06", status: "scheduled", division: "BCA FY A",
  substitute: [], change_reason: null,
};
const students = [
  { id: "a", name: "Om Shinde", prn: "2026BCA003", roll_no: "1", photo_url: null, exempt: null },
  { id: "b", name: "Neha Joshi", prn: "2026BCA002", roll_no: "2", photo_url: null, exempt: "medical" },
  { id: "c", name: "Rohan Patil", prn: "2026BCA001", roll_no: "3", photo_url: null, exempt: null },
];
const faculty = makeMe({ roles: ["faculty"], permissions: ["attendance.take", "timetable.read"] });

describe("attendance", () => {
  it("a teacher takes attendance: everyone present, tap the absentee, save", async () => {
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: faculty };
      if (path.startsWith("/attendance/today")) return { status: 200, body: { date: "2026-07-06", holiday: null, lectures: [{ ...lecture, takeable: true, editable_until: "", window_open: true, session: null }] } };
      if (path.startsWith("/attendance/sheet") && method === "GET") return { status: 200, body: { lecture, students, session: null, can_save: true, can_request_edit: false, editable_until: "" } };
      if (path === "/attendance/sheet" && method === "PUT") return { status: 200, body: { id: "x", absent: ["c"], present: 2, total: 3, version: 1, saved_by: "Asha", saved_at: "2026-07-06T04:00:00Z" } };
      return { status: 404 };
    });
    renderApp("/app/attendance");
    fireEvent.click(await screen.findByRole("link", { name: "Take attendance" }));
    expect(await screen.findByText("Medical")).toBeTruthy();
    expect(document.querySelector(".take-bar")?.textContent).toContain("3 present · 0 absent");
    fireEvent.click(screen.getByRole("button", { name: /Rohan Patil/ }));
    expect(screen.getByRole("button", { name: /Rohan Patil/ }).getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "Save attendance" }));
    expect(await screen.findByText("BCA101: 2 of 3 present")).toBeTruthy();
    const put = calls.find((c) => c.method === "PUT");
    expect(put?.body).toMatchObject({ slot_id: "s1", date: "2026-07-06", absent: ["c"], base_version: null });
  });

  it("after 48 hours the teacher asks the HOD", async () => {
    const session = { id: "x", absent: [], present: 3, total: 3, version: 1, saved_by: "Asha", saved_at: "2026-07-06T04:00:00Z" };
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: faculty };
      if (path.startsWith("/attendance/sheet")) return { status: 200, body: { lecture, students, session, can_save: false, can_request_edit: true, editable_until: "" } };
      if (path === "/attendance/edit-requests" && method === "POST") return { status: 201, body: {} };
      if (path.startsWith("/attendance/today")) return { status: 200, body: { date: "2026-07-06", holiday: null, lectures: [] } };
      if (path.startsWith("/attendance/edit-requests")) return { status: 200, body: [] };
      return { status: 404 };
    });
    renderApp("/app/attendance/take/s1/2026-07-06");
    expect(await screen.findByText(/48 hours for changes are over/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Save attendance" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Om Shinde/ }));
    fireEvent.click(screen.getByRole("button", { name: "Ask HOD to change" }));
    fireEvent.change(screen.getByLabelText("Why does it need changing?"), { target: { value: "Om left early" } });
    fireEvent.click(screen.getByRole("button", { name: "Send to HOD" }));
    expect(await screen.findByText("Sent to your HOD for approval.")).toBeTruthy();
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ slot_id: "s1", date: "2026-07-06", absent: ["a"], reason: "Om left early" });
  });

  it("a save conflict offers to load the other version", async () => {
    mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: faculty };
      if (path.startsWith("/attendance/sheet") && method === "GET") return { status: 200, body: { lecture, students, session: null, can_save: true, can_request_edit: false, editable_until: "" } };
      if (path === "/attendance/sheet") return { status: 409, body: { error: { code: "attendance_conflict", message: "Someone else saved this lecture's attendance in the meantime." } } };
      return { status: 404 };
    });
    renderApp("/app/attendance/take/s1/2026-07-06");
    fireEvent.click(await screen.findByRole("button", { name: "Save attendance" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Load their version" })).toBeTruthy();
  });

  it("HOD approves a change request", async () => {
    const hod = makeMe({ id: "h1", roles: ["hod"], permissions: ["attendance.take", "attendance.approve", "attendance.read.dept"] });
    const request = { id: "r1", slot_id: "s1", date: "2026-07-06", class: "BCA FY A", subject: "BCA101 Programming in C", start: "09:00", absent_now: 1, absent_new: 2, reason: "Om left early", status: "pending", requested_by: "Anita Rao", requested_by_id: "u2", requested_at: "", decided_by: null, decision_reason: null };
    const calls = mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: hod };
      if (path.startsWith("/attendance/today")) return { status: 200, body: { date: "2026-07-06", holiday: null, lectures: [] } };
      if (path === "/attendance/edit-requests?status=pending") return { status: 200, body: [request] };
      if (path === "/attendance/edit-requests/r1/decide") return { status: 200, body: { ...request, status: "approved" } };
      return { status: 404 };
    });
    renderApp("/app/attendance");
    fireEvent.click(await screen.findByRole("tab", { name: "Change requests" }));
    expect(await screen.findByText(/Absent 1 → 2/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    fireEvent.click(document.querySelector("dialog[open] .btn-primary, dialog[open] .btn-danger") as HTMLElement);
    await waitFor(() => expect(calls.find((c) => c.path === "/attendance/edit-requests/r1/decide")?.body).toEqual({ approve: true }));
  });
});

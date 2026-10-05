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

describe("offline attendance", () => {
  it("saves on the phone without a network and sends it when back online", async () => {
    let online = true;
    const delivered: { absent: string[]; client_id: string }[] = [];
    const today = { date: "2026-07-06", holiday: null, lectures: [{ ...lecture, takeable: true, editable_until: "", window_open: true, session: null }] };
    const calls = mockApi((method, path, body) => {
      if (path === "/auth/me") return { status: 200, body: faculty };
      if (!online) return { status: 0 };
      if (path.startsWith("/attendance/today")) return { status: 200, body: today };
      if (path.startsWith("/attendance/sheet") && method === "GET") return { status: 200, body: { lecture, students, session: null, can_save: true, can_request_edit: false, editable_until: "" } };
      if (path === "/attendance/sheet" && method === "PUT") {
        delivered.push(body as { absent: string[]; client_id: string });
        return { status: 200, body: { id: "x", absent: ["a"], present: 2, total: 3, version: 1, saved_by: "Asha", saved_at: "" } };
      }
      return { status: 404 };
    });
    // Online: the day and its class lists are saved on the phone.
    renderApp("/app/attendance");
    await screen.findByRole("link", { name: "Take attendance" });
    await waitFor(() => expect(calls.filter((c) => c.path.startsWith("/attendance/sheet")).length).toBe(1));
    cleanup();

    // The signal drops in the classroom.
    online = false;
    renderApp("/app/attendance/take/s1/2026-07-06");
    expect(await screen.findByText(/No connection. You can still mark attendance/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Om Shinde/ }));
    fireEvent.click(screen.getByRole("button", { name: "Save attendance" }));
    expect(await screen.findByText(/Saved on this phone; it will be sent when you're back online/)).toBeTruthy();
    expect(await screen.findByText(/1 attendance save waiting to be sent/)).toBeTruthy();
    expect(screen.getByText("Waiting to sync")).toBeTruthy();
    expect(delivered).toHaveLength(0);

    // Back online: it is sent once, with the device's id so a retry isn't doubled.
    online = true;
    window.dispatchEvent(new Event("online"));
    await waitFor(() => expect(delivered).toHaveLength(1));
    expect(delivered[0].absent).toEqual(["a"]);
    expect(delivered[0].client_id).toMatch(/[0-9a-f-]{36}/);
    await waitFor(() => expect(screen.queryByText(/waiting to be sent/)).toBeNull());
  });

  it("a conflicting offline save is shown, not lost", async () => {
    const { put } = await import("../../lib/offline");
    await put("outbox", "s1:2026-07-06", {
      key: "s1:2026-07-06", label: "BCA101 · BCA FY A · 2026-07-06 09:00", queued_at: "2026-07-06T04:00:00Z", state: "pending",
      body: { slot_id: "s1", date: "2026-07-06", absent: ["a"], client_id: "c-1", base_version: null },
    });
    mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: faculty };
      if (path.startsWith("/attendance/today")) return { status: 200, body: { date: "2026-07-06", holiday: null, lectures: [] } };
      if (path === "/attendance/sheet" && method === "PUT") return { status: 409, body: { error: { code: "attendance_conflict", message: "Someone else saved this lecture's attendance in the meantime." } } };
      return { status: 404 };
    });
    renderApp("/app/attendance");
    expect(await screen.findByText(/BCA101 · BCA FY A · 2026-07-06 09:00: Someone else saved/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Discard the copy on this phone" }));
    await waitFor(() => expect(screen.queryByText(/Someone else saved/)).toBeNull());
  });
});

describe("attendance percentages", () => {
  it("a student sees what they can miss, in Hindi", async () => {
    localStorage.setItem("cc-lang", "hi");
    const student = makeMe({ kind: "student", prn: "2026BCA001", roles: ["student"], role_labels: ["Student"] });
    mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: student };
      if (path === "/me/attendance")
        return {
          status: 200,
          body: {
            minimum: 75, warning: 80,
            overall: { held: 28, attended: 21, percent: 75, status: "warning" },
            subjects: [
              { subject_id: "1", code: "BCA101", name: "C", held: 8, attended: 5, percent: 62.5, status: "critical", can_miss: 0, must_attend: 4 },
              { subject_id: "2", code: "BCA102", name: "Maths", held: 20, attended: 16, percent: 80, status: "ok", can_miss: 1, must_attend: 0 },
            ],
            days: [{ date: "2026-07-06", lectures: [{ code: "BCA101", start: "09:00", mark: "exempt" }] }],
          },
        };
      return { status: 404 };
    });
    renderApp("/app/attendance");
    expect(await screen.findByRole("heading", { name: "मेरी उपस्थिति" })).toBeTruthy();
    expect(await screen.findByText("न्यूनतम तक पहुँचने के लिए लगातार अगले 4 लेक्चर में आएँ।")).toBeTruthy();
    expect(screen.getByText("आप 1 और लेक्चर छोड़ सकते हैं।")).toBeTruthy();
    expect(screen.getByText(/BCA101 09:00 · छूट/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "उपस्थिति" })).toBeTruthy();
  });

  it("HOD sees a class report and filters defaulters", async () => {
    const hod = makeMe({ roles: ["hod"], permissions: ["attendance.take", "attendance.approve", "attendance.read.dept"] });
    const cell = (percent: number, status: string) => ({ held: 8, attended: Math.round((percent * 8) / 100), percent, status });
    mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: hod };
      if (path.startsWith("/attendance/today")) return { status: 200, body: { date: "2026-07-06", holiday: null, lectures: [] } };
      if (path === "/attendance/classes") return { status: 200, body: [{ id: "v1", label: "BCA FY A" }] };
      if (path.startsWith("/attendance/report"))
        return {
          status: 200,
          body: {
            class: "BCA FY A", minimum: 75, warning: 80,
            subjects: [{ id: "s1", code: "BCA101", name: "C", held: 8 }],
            students: [
              { student_id: "a", name: "Rohan Patil", prn: "2026BCA001", roll_no: "1", subjects: { s1: cell(62.5, "critical") }, overall: 62.5, status: "critical", defaulter: true },
              { student_id: "b", name: "Om Shinde", prn: "2026BCA003", roll_no: "2", subjects: { s1: cell(100, "ok") }, overall: 100, status: "ok", defaulter: false },
            ],
          },
        };
      return { status: 404 };
    });
    renderApp("/app/attendance");
    fireEvent.click(await screen.findByRole("tab", { name: "Reports" }));
    await screen.findByRole("option", { name: "BCA FY A" });
    fireEvent.change(screen.getByLabelText("Class"), { target: { value: "v1" } });
    expect(await screen.findByText("Om Shinde")).toBeTruthy();
    fireEvent.click(screen.getByLabelText(/Only defaulters/));
    expect(screen.queryByText("Om Shinde")).toBeNull();
    expect(screen.getByText("Rohan Patil")).toBeTruthy();
  });
});

import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

const lecture = (extra = {}) => ({
  id: "s1", slot_id: "s1", timetable_id: "t1", division_id: "v1", day: 1, day_name: "Monday", start: "09:00", end: "10:00",
  subject_id: "sub1", subject_code: "BCA101", subject_name: "Programming in C", subject_type: "theory", faculty_ids: ["f1"],
  faculty: ["Anita Rao"], room: "101", batch: null, date: "2026-07-06", status: "scheduled", division: "BCA FY A",
  substitute: [], change_reason: null, ...extra,
});
const week = (lectures: unknown[]) => ({
  week_of: "2026-07-06",
  days: ["2026-07-06", "2026-07-07", "2026-07-08", "2026-07-09", "2026-07-10", "2026-07-11"].map((d, i) => ({
    date: d, day_name: "", holiday: i === 1 ? "Ashadhi Ekadashi" : null, lectures: i === 0 ? lectures : [],
  })),
});
const setup = {
  institution: {}, current_year: { id: "y1", name: "2026-27", start_date: "2026-06-15", end_date: "2027-04-30", is_current: true, status: "active" },
  academic_years: [], departments: [], categories: [],
  programmes: [{ id: "p1", status: "active", code: "BCA", name: "BCA", department_id: "d1", level: "UG", duration_years: 3, semesters_per_year: 2, year_labels: ["FY", "SY", "TY"] }],
  divisions: [{ id: "v1", status: "active", programme_id: "p1", year_of_study: 1, name: "A", capacity: 60 }],
};

describe("timetable", () => {
  it("a student sees their week in Marathi with a cancelled lecture and a holiday", async () => {
    localStorage.setItem("cc-lang", "mr");
    const student = makeMe({ kind: "student", prn: "2026BCA001", roles: ["student"], role_labels: ["Student"] });
    mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: student };
      if (path.startsWith("/me/timetable")) return { status: 200, body: week([lecture({ status: "cancelled", change_reason: "Exam duty" })]) };
      return { status: 404 };
    });
    renderApp("/app/timetable");
    expect(await screen.findByRole("heading", { name: "माझे वेळापत्रक" })).toBeTruthy();
    expect(await screen.findByText("रद्द")).toBeTruthy();
    expect(screen.getByText(/सुट्टी: Ashadhi Ekadashi/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "वेळापत्रक" })).toBeTruthy();
  });

  it("office gives a lecture to a substitute", async () => {
    const office = makeMe({ roles: ["office"], permissions: ["timetable.read", "timetable.manage", "setup.read"] });
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: office };
      if (path === "/setup") return { status: 200, body: setup };
      if (path.startsWith("/timetable/week")) return { status: 200, body: week([lecture()]) };
      if (path === "/timetables/t1/options") return { status: 200, body: { subjects: [], faculty: [{ id: "f1", name: "Anita Rao", department_id: null }, { id: "f2", name: "Imran Khan", department_id: null }], rooms: [] } };
      if (path === "/timetable-slots/s1/changes" && method === "POST") return { status: 201, body: {} };
      return { status: 404 };
    });
    renderApp("/app/timetable");
    expect(await screen.findByRole("tab", { name: "Set up timetables" })).toBeTruthy();
    expect(screen.queryByRole("tab", { name: "My week" })).toBeNull();
    await screen.findByRole("option", { name: "BCA · FY · A" });
    fireEvent.change(screen.getByLabelText("Class"), { target: { value: "v1" } });
    fireEvent.click(await screen.findByRole("button", { name: /BCA101/ }));
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Change"), { target: { value: "substitute" } });
    await within(dialog).findByRole("option", { name: "Imran Khan" });
    expect(within(dialog).queryByRole("option", { name: "Anita Rao" })).toBeNull(); // not the usual teacher
    fireEvent.change(within(dialog).getByLabelText("Substitute"), { target: { value: "f2" } });
    fireEvent.change(within(dialog).getByLabelText("Reason (students see it)"), { target: { value: "On leave" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(calls.find((c) => c.method === "POST")?.body).toEqual({ date: "2026-07-06", kind: "substitute", faculty_ids: ["f2"], room: "", reason: "On leave" }),
    );
  });

  it("HOD adds a lecture and sees a clash message", async () => {
    const hod = makeMe({ roles: ["hod"], permissions: ["timetable.read", "timetable.manage.dept", "attendance.take"] });
    const tt = { id: "t1", division_id: "v1", division: "BCA FY A", academic_year_id: "y1", academic_year: "2026-27", term: 1, semester: 1, valid_from: "2026-06-15", valid_to: "2026-11-15", can_manage: true, slots: [] };
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: hod };
      if (path === "/timetables/t1") return { status: 200, body: tt };
      if (path === "/timetables/t1/options") return { status: 200, body: { subjects: [{ id: "sub1", code: "BCA101", name: "Programming in C", type: "theory" }], faculty: [{ id: "f1", name: "Anita Rao", department_id: "d1" }], rooms: ["101"] } };
      if (path === "/timetables/t1/slots" && method === "POST") return { status: 409, body: { error: { code: "clash", message: "Anita Rao already teaches another class on Monday 09:00–10:00.", field: "faculty_ids" } } };
      return { status: 404 };
    });
    renderApp("/app/timetable/t1");
    fireEvent.click(await screen.findByRole("button", { name: "Add lecture" }));
    const dialog = screen.getByRole("dialog");
    await within(dialog).findByRole("option", { name: "BCA101 · Programming in C" });
    fireEvent.change(within(dialog).getByLabelText("Subject"), { target: { value: "sub1" } });
    fireEvent.click(within(dialog).getByLabelText("Anita Rao"));
    fireEvent.change(within(dialog).getByLabelText("Room"), { target: { value: "101" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    expect((await within(dialog).findAllByText(/already teaches another class/)).length).toBeGreaterThan(0);
    expect(calls.find((c) => c.method === "POST")?.body).toMatchObject({ day: 1, start: "09:00", end: "10:00", subject_id: "sub1", faculty_ids: ["f1"], room: "101", batch: null });
  });
});

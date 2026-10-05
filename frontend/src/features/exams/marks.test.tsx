import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

const scheme = {
  id: "sc1", subject_id: "sub1", academic_year_id: "y1", total: 40, deadline: "2026-09-30", locked_in: false,
  components: [
    { key: "c1", name: "Unit test 1", max: 15, held_on: null },
    { key: "c2", name: "Unit test 2", max: 15, held_on: null },
    { key: "c3", name: "Assignment", max: 10, held_on: null },
  ],
};
const sheet = (extra = {}) => ({
  class: "BCA FY A", division_id: "v1", subject: { id: "sub1", code: "BCA101", name: "Programming in C", max_internal: 40 }, scheme,
  status: "draft", status_label: "Draft", version: 1, returned_reason: null, saved_by: "Anita Rao", approved_by: null, locked_by: null, deadline_passed: false,
  students: [
    { id: "a", name: "Om Shinde", prn: "2026BCA003", roll_no: "1", marks: { c1: 12, c2: "AB", c3: 9 }, total: 21 },
    { id: "b", name: "Neha Joshi", prn: "2026BCA002", roll_no: "2", marks: {}, total: null },
  ],
  can_edit: true, can_publish: true, can_approve: false, can_return: false, can_lock: false, can_unlock: false, ...extra,
});

describe("internal marks", () => {
  it("a teacher enters marks in the grid", async () => {
    const teacher = makeMe({ roles: ["faculty"], permissions: ["marks.enter", "attendance.take", "timetable.read"] });
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: teacher };
      if (path === "/marks/my-classes") return { status: 200, body: [{ division_id: "v1", class: "BCA FY A", subject_id: "sub1", code: "BCA101", name: "Programming in C", has_scheme: true, deadline: "2026-09-30", status: "draft", status_label: "Draft", complete: 1, students: 2 }] };
      if (path.startsWith("/marks/sheet") && method === "GET") return { status: 200, body: sheet() };
      if (path === "/marks/sheet" && method === "PUT") return { status: 200, body: sheet({ version: 2 }) };
      return { status: 404 };
    });
    renderApp("/app/exams");
    fireEvent.click(await screen.findByText(/1 of 2 students complete/));
    const cell = await screen.findByLabelText("Neha Joshi Unit test 1");
    fireEvent.change(cell, { target: { value: "16" } });
    expect(cell.className).toContain("bad");
    expect((screen.getByRole("button", { name: "Save marks" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(cell, { target: { value: "14.5" } });
    fireEvent.change(screen.getByLabelText("Neha Joshi Unit test 2"), { target: { value: "ab" } });
    fireEvent.change(screen.getByLabelText("Neha Joshi Assignment"), { target: { value: "8" } });
    expect(screen.getByText("22.5")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Publish to students" })).toBeNull(); // save first
    fireEvent.click(screen.getByRole("button", { name: "Save marks" }));
    await waitFor(() =>
      expect(calls.find((c) => c.method === "PUT")?.body).toEqual({
        division_id: "v1", subject_id: "sub1", base_version: 1, marks: { b: { c1: 14.5, c2: "AB", c3: 8 } },
      }),
    );
  });

  it("the HOD approves published marks", async () => {
    const hod = makeMe({ roles: ["hod"], permissions: ["marks.approve", "marks.enter", "marks.scheme.dept"] });
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: hod };
      if (path.startsWith("/marks/sheet") && method === "GET") return { status: 200, body: sheet({ status: "published", status_label: "Published to students", can_edit: false, can_publish: false, can_approve: true, can_return: true }) };
      if (path === "/marks/sheet/action") return { status: 200, body: sheet({ status: "approved" }) };
      return { status: 404 };
    });
    renderApp("/app/exams/marks/v1/sub1");
    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    fireEvent.click(document.querySelector("dialog[open] .btn-primary, dialog[open] .btn-danger") as HTMLElement);
    await waitFor(() => expect(calls.find((c) => c.path === "/marks/sheet/action")?.body).toEqual({ division_id: "v1", subject_id: "sub1", action: "approve" }));
    expect((screen.getByLabelText("Om Shinde Unit test 1") as HTMLInputElement).disabled).toBe(true);
  });

  it("the Exam Cell sets a scheme that must add up", async () => {
    const exam = makeMe({ roles: ["exam_cell"], permissions: ["exams.manage", "marks.read", "setup.read"] });
    const setup = {
      institution: {}, current_year: null, academic_years: [], departments: [], categories: [], divisions: [],
      programmes: [{ id: "p1", status: "active", code: "BCA", name: "BCA", department_id: "d1", level: "UG", duration_years: 3, semesters_per_year: 2, year_labels: ["FY", "SY", "TY"] }],
    };
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: exam };
      if (path === "/setup") return { status: 200, body: setup };
      if (path === "/marks/overview") return { status: 200, body: [] };
      if (path.startsWith("/marks/schemes") && method === "GET") return { status: 200, body: [{ subject_id: "sub1", code: "BCA101", name: "Programming in C", semester: 1, max_internal: 40, scheme: null, can_manage: true }] };
      if (path === "/marks/schemes" && method === "PUT") return { status: 200, body: scheme };
      return { status: 404 };
    });
    renderApp("/app/exams");
    fireEvent.click(await screen.findByRole("tab", { name: "Assessment schemes" }));
    await screen.findByRole("option", { name: "BCA · BCA" });
    fireEvent.change(screen.getByLabelText("Programme"), { target: { value: "p1" } });
    fireEvent.click(await screen.findByRole("button", { name: "Set scheme" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Out of"), { target: { value: "30" } });
    expect(within(dialog).getByText("Total 30 of 40")).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: "+ Add a part" }));
    fireEvent.change(within(dialog).getByLabelText("Part 2"), { target: { value: "Assignment" } });
    fireEvent.change(within(dialog).getAllByLabelText("Out of")[1], { target: { value: "10" } });
    fireEvent.change(within(dialog).getByLabelText("Last day for marks entry"), { target: { value: "2026-09-30" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save scheme" }));
    await waitFor(() =>
      expect(calls.find((c) => c.method === "PUT")?.body).toEqual({
        subject_id: "sub1",
        components: [{ name: "Unit test 1", max: 30, held_on: null }, { name: "Assignment", max: 10, held_on: null }],
        deadline: "2026-09-30",
      }),
    );
  });

  it("a student sees published marks in Marathi", async () => {
    localStorage.setItem("cc-lang", "mr");
    const student = makeMe({ kind: "student", prn: "2026BCA003", roles: ["student"], role_labels: ["Student"] });
    mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: student };
      if (path === "/me/marks") return { status: 200, body: [{ subject_id: "sub1", code: "BCA101", name: "Programming in C", out_of: 40, status: "published", total: 21, components: [{ name: "Unit test 1", max: 15, mark: 12 }, { name: "Unit test 2", max: 15, mark: "AB" }, { name: "Assignment", max: 10, mark: 9 }] }] };
      return { status: 404 };
    });
    renderApp("/app/exams");
    expect(await screen.findByText("गैरहजर")).toBeTruthy();
    expect(screen.getByText("12 / 15")).toBeTruthy();
    expect(screen.getByText("शिक्षकांनी प्रसिद्ध केले")).toBeTruthy();
    expect(screen.getByRole("link", { name: "परीक्षा आणि निकाल" })).toBeTruthy();
  });
});

describe("University Upload Guard", () => {
  it("the Exam Cell sees what blocks each subject and checks a file", async () => {
    const exam = makeMe({ roles: ["exam_cell"], permissions: ["exams.manage", "marks.read"] });
    const row = {
      class: "BCA FY A", division_id: "v1", subject_id: "sub1", code: "BCA101", name: "Programming in C", department: "Computer Science",
      has_scheme: true, status: "published", status_label: "Published to students", deadline: "2026-10-07", days_left: 2, students: 3,
      counts: { missing: 1, above_max: 0, absent_marked: 1, ineligible: 1 }, ready: false,
    };
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: exam };
      if (path === "/marks/overview") return { status: 200, body: [] };
      if (path === "/marks/guard") return { status: 200, body: { rows: [row], departments: [{ name: "Computer Science", subjects: 1, ready: 0, locked: 0 }] } };
      if (path.startsWith("/marks/guard/detail"))
        return { status: 200, body: { ...row, issues: [{ kind: "missing", label: "Marks missing", student_id: "c", name: "Om Shinde", prn: "2026BCA003", detail: "Assignment" }] } };
      if (path.startsWith("/marks/guard/check-file") && method === "POST") return { status: 200, body: { ok: false, rows: 2, problems: ["2026BCA003 (Om Shinde) is missing."] } };
      return { status: 404 };
    });
    renderApp("/app/exams");
    fireEvent.click(await screen.findByRole("tab", { name: "Upload Guard" }));
    expect(await screen.findByText("0/1 ready")).toBeTruthy();
    expect(screen.getByText("2 days left")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Check" }));
    expect(await screen.findByText(/Om Shinde \(2026BCA003\)\. Assignment/)).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Download university file" })).toBeNull(); // not ready
    const input = screen.getByLabelText(/Check a file before uploading/) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["PRN"], "u.csv", { type: "text/csv" })] } });
    expect(await screen.findByText("2026BCA003 (Om Shinde) is missing.")).toBeTruthy();
    expect(calls.some((c) => c.path.startsWith("/marks/guard/check-file"))).toBe(true);
  });
});

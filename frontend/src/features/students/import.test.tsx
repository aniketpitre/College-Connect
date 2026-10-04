import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const office = makeMe({ roles: ["office"], permissions: ["setup.read", "students.read", "students.manage", "students.import"] });
const file = new File(["prn,name,programme,year\n"], "students.csv", { type: "text/csv" });

describe("student import", () => {
  it("shows the problems row by row", async () => {
    mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: office };
      if (path === "/students/imports")
        return {
          status: 200,
          body: { id: "i1", filename: "s.csv", status: "has_errors", total: 3, valid: 2, committed: 0, error_count: 1, errors: [{ row: 3, field: "phone", message: "Enter a 10-digit mobile number.", prn: "2026BCA002" }] },
        };
      return { status: 404 };
    });
    renderApp("/app/students/import");
    fireEvent.change(await screen.findByLabelText("Spreadsheet"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Check file" }));
    expect(await screen.findByText("1 problem in 3 rows")).toBeTruthy();
    expect(screen.getByText("Enter a 10-digit mobile number.")).toBeTruthy();
    expect(screen.getByText("Nothing was saved")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Create/ })).toBeNull();
  });

  it("creates students in chunks and shows printable login slips", async () => {
    let committed = 0;
    const calls = mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: office };
      if (path === "/students/imports")
        return { status: 200, body: { id: "i1", filename: "s.csv", status: "validated", total: 3, valid: 3, committed: 0, error_count: 0, errors: [], preview: [] } };
      if (path === "/students/imports/i1/commit") {
        committed += committed === 0 ? 2 : 1;
        const credentials = committed === 2
          ? [{ prn: "2026BCA001", name: "A One", temporary_password: "aaaa-bbbb-cccc" }, { prn: "2026BCA002", name: "B Two", temporary_password: "dddd-eeee-ffff" }]
          : [{ prn: "2026BCA003", name: "C Three", temporary_password: "gggg-hhhh-jjjj" }];
        return { status: 200, body: { id: "i1", status: committed === 3 ? "done" : "committing", total: 3, valid: 3, committed, error_count: 0, errors: [], done: committed === 3, credentials } };
      }
      return { status: 404 };
    });
    renderApp("/app/students/import");
    fireEvent.change(await screen.findByLabelText("Spreadsheet"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Check file" }));
    fireEvent.click(await screen.findByRole("button", { name: "Create 3 students and logins" }));
    expect(await screen.findByRole("heading", { name: "3 students created" })).toBeTruthy();
    expect(screen.getByText("gggg-hhhh-jjjj")).toBeTruthy();
    await waitFor(() => expect(calls.filter((c) => c.path === "/students/imports/i1/commit")).toHaveLength(2));
  });
});

describe("promotion", () => {
  it("previews, holds a student back and promotes with a reason", async () => {
    const setup = {
      institution: {}, current_year: null, academic_years: [], departments: [], divisions: [], categories: [],
      programmes: [{ id: "p1", status: "active", code: "BCA", name: "BCA", department_id: "d1", level: "UG", duration_years: 3, semesters_per_year: 2, year_labels: ["FY", "SY", "TY"] }],
    };
    const plan = (held: string[], dry: boolean) => ({
      programme: "BCA", from_year: "FY", to_year: "SY", academic_year: "2026-27", dry_run: dry,
      students: ["s1", "s2"].map((id) => ({ id, prn: id.toUpperCase(), name: `Student ${id}`, outcome: held.includes(id) ? "held_back" : "promoted" })),
      counts: { promoted: 2 - held.length, graduates: 0, held_back: held.length, already_promoted: 0 },
    });
    const calls = mockApi((_m, path, body) => {
      if (path === "/auth/me") return { status: 200, body: office };
      if (path === "/setup") return { status: 200, body: setup };
      if (path === "/students/promote") {
        const b = body as { hold_back: string[]; dry_run: boolean };
        return { status: 200, body: plan(b.hold_back, b.dry_run) };
      }
      return { status: 404 };
    });
    renderApp("/app/students/promote");
    await waitFor(() => expect(screen.getByRole("option", { name: "BCA" })).toBeTruthy());
    fireEvent.change(screen.getByLabelText("Programme"), { target: { value: "p1" } });
    fireEvent.change(screen.getByLabelText("Year"), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "Show students" }));
    fireEvent.click(await screen.findByLabelText(/Student s2/));
    expect(await screen.findByRole("button", { name: "Move 1 students to SY" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Move 1 students to SY" }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Results declared" } });
    fireEvent.click(screen.getByRole("button", { name: "Promote" }));
    expect(await screen.findByRole("status")).toBeTruthy();
    expect(calls.at(-1)?.body).toEqual({ programme_id: "p1", from_year: 1, hold_back: ["s2"], dry_run: false, reason: "Results declared" });
  });
});

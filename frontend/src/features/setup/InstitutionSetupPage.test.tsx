import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SetupOverview } from "../../lib/setup";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const year = { id: "y1", status: "active" as const, name: "2026-27", start_date: "2026-06-01", end_date: "2027-05-31", is_current: true };
const overview: SetupOverview = {
  institution: { name: "Shivaji College", short_name: "", address: "", phone: "", email: null, website: "", university: "SPPU", college_code: "", receipt_prefix: "R", certificate_prefix: "C" },
  current_year: year,
  academic_years: [year],
  departments: [{ id: "d1", status: "active", code: "CS", name: "Computer Science" }],
  programmes: [{ id: "p1", status: "active", code: "BCA", name: "Bachelor of Computer Applications", department_id: "d1", level: "UG", duration_years: 3, semesters_per_year: 2, year_labels: ["FY", "SY", "TY"] }],
  divisions: [{ id: "v1", status: "active", programme_id: "p1", year_of_study: 2, name: "A", capacity: 60 }],
  categories: [
    { id: "c1", status: "active", code: "OPEN", name: "Open", reserved_percent: null },
    { id: "c2", status: "archived", code: "OLD", name: "Old category", reserved_percent: null },
  ],
};

const admin = makeMe({ roles: ["system_admin"], permissions: ["setup.read", "setup.manage"] });

describe("college setup", () => {
  it("shows the structure and adds a category", async () => {
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: admin };
      if (path === "/setup" && method === "GET") return { status: 200, body: overview };
      if (path === "/setup/categories" && method === "POST") return { status: 201, body: { id: "c3", status: "active" } };
      return { status: 404 };
    });
    renderApp("/app/setup");
    expect(await screen.findByText("Current year 2026-27")).toBeTruthy();
    expect((screen.getByLabelText("College name") as HTMLInputElement).value).toBe("Shivaji College");

    fireEvent.click(screen.getByRole("tab", { name: "Programmes" }));
    expect(screen.getByText("BCA · SY")).toBeTruthy();

    fireEvent.click(screen.getByRole("tab", { name: "Categories" }));
    expect(screen.getByText("OPEN")).toBeTruthy();
    expect(screen.queryByText("OLD")).toBeNull(); // archived hidden by default
    fireEvent.click(screen.getByLabelText(/Show archived/));
    expect(screen.getByText("OLD")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Code"), { target: { value: "OBC" } });
    fireEvent.change(within(dialog).getByLabelText("Name"), { target: { value: "Other Backward Class" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(calls.find((c) => c.method === "POST" && c.path === "/setup/categories")?.body).toEqual({ code: "OBC", name: "Other Backward Class", reserved_percent: null }),
    );
  });

  it("is read-only without setup.manage", async () => {
    mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: makeMe({ permissions: ["setup.read"] }) };
      if (path === "/setup") return { status: 200, body: overview };
      return { status: 404 };
    });
    renderApp("/app/setup");
    expect(((await screen.findByLabelText("College name")) as HTMLInputElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("tab", { name: "Categories" }));
    expect(screen.queryByRole("button", { name: "Add" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Archive" })).toBeNull();
  });

  it("offers starter data on an empty setup", async () => {
    const calls = mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: admin };
      if (path === "/setup") return { status: 200, body: { ...overview, current_year: null, academic_years: [], programmes: [], divisions: [] } };
      if (path === "/setup/starter-data") return { status: 200, body: { categories: 8 } };
      return { status: 404 };
    });
    renderApp("/app/setup");
    fireEvent.click(await screen.findByRole("button", { name: "Load starter data" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/setup/starter-data")).toBe(true));
  });
});

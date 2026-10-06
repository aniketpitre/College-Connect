import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

const metric = (extra = {}) => ({
  id: "2.4.2",
  criterion: 2,
  criterion_name: "Teaching-learning and evaluation",
  title: "Full-time teachers with Ph.D. / NET / SET",
  manual: false,
  value: "75.0%",
  columns: [
    { key: "name", label: "Teacher" },
    { key: "phd", label: "Ph.D." },
  ],
  rows: [{ name: "Dr. Sunita Rane", phd: "Yes" }],
  gaps: ["1 teacher(s) have no qualifications recorded: Amit Deshmukh."],
  evidence_needed: ["Copies of Ph.D. / NET / SET certificates"],
  evidence: [],
  ...extra,
});
const aqar = {
  year: { id: "y1", name: "2026-27" },
  generated_at: "2026-10-06T10:00:00Z",
  metrics: [metric(), metric({ id: "1.2.1", criterion: 1, criterion_name: "Curricular aspects", title: "Programmes offered", value: "1", gaps: [] })],
  gaps: 1,
  settings: { sanctioned_posts: 12, intake: {} },
};
const setup = { academic_years: [{ id: "y1", name: "2026-27", start_date: "2026-06-01", end_date: "2027-05-31", is_current: true, status: "active" }], programmes: [] };

describe("reports", () => {
  it("the IQAC sees NAAC metrics with gaps and uploads evidence", async () => {
    const iqac = makeMe({ roles: ["iqac"], role_labels: ["IQAC Coordinator"], permissions: ["reports.read", "naac.manage", "setup.read"] });
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: iqac };
      if (path === "/setup") return { status: 200, body: setup };
      if (path === "/reports/naac") return { status: 200, body: aqar };
      if (path === "/reports/naac/2.4.2/evidence") return { status: 201, body: { id: "e1", title: "NET certificates", filename: "net.pdf", at: "" } };
      return { status: method === "GET" ? 404 : 200, body: {} };
    });
    renderApp("/app/reports");
    expect(await screen.findByText("Full-time teachers with Ph.D. / NET / SET")).toBeTruthy();
    expect(screen.getByText(/no qualifications recorded: Amit Deshmukh/)).toBeTruthy();
    fireEvent.click(screen.getByLabelText("Show only metrics with gaps"));
    expect(screen.queryByText("Programmes offered")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Full-time teachers with Ph.D./ }));
    expect(await screen.findByText("Dr. Sunita Rane")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Evidence title for 2.4.2"), { target: { value: "NET certificates" } });
    const file = new File(["%PDF-1.4"], "net.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText("Upload evidence for 2.4.2"), { target: { files: [file] } });
    await waitFor(() => expect(calls.find((c) => c.path === "/reports/naac/2.4.2/evidence")).toBeTruthy());
  });

  it("the office checks APAAR IDs and downloads ABC credits", async () => {
    const office = makeMe({ roles: ["office"], permissions: ["reports.read", "students.manage", "setup.read"] });
    mockApi((_method, path) => {
      if (path === "/auth/me") return { status: 200, body: office };
      if (path === "/setup") return { status: 200, body: setup };
      if (path === "/reports/naac") return { status: 200, body: aqar };
      if (path === "/reports/apaar")
        return {
          status: 200,
          body: { students: 3, valid: 1, missing: [{ id: "s3", prn: "2026BCA003", name: "Om Shinde", apaar_id: null }], invalid: [], duplicate: [{ id: "s2", prn: "2026BCA002", name: "Neha Joshi", apaar_id: "123456789012" }] },
        };
      if (path === "/reports/apaar/credits") return { status: 200, body: { year: "2026-27", rows: 5, students: 1, credits: 20, skipped_without_apaar: 2, sample: [] } };
      return { status: 404 };
    });
    renderApp("/app/reports");
    fireEvent.click(await screen.findByRole("tab", { name: "APAAR / ABC" }));
    expect(await screen.findByText("1/3")).toBeTruthy();
    expect(screen.getByText("used by another student")).toBeTruthy();
    expect(await screen.findByText(/2 student\(s\) left out: no valid APAAR ID/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Download credits (CSV)" }).getAttribute("href")).toBe("/api/v1/reports/apaar/credits.csv");
  });
});

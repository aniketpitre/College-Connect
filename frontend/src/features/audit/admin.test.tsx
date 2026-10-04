import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const areas = { auth: "Sign-ins and passwords", fees: "Fees and receipts" };
const row = (i: number, extra = {}) => ({
  id: `a${i}`, at: `2026-10-0${(i % 9) + 1}T05:00:00+00:00`, action: "fees.payment.collected", actor: "Meera Joshi", actor_id: "u2",
  target_type: "student", target_id: "s1", target: "Rohan Patil (2026BCA001)", ip: "10.0.0.1", reason: null, details: { amount: 1000 }, ...extra,
});

describe("audit log", () => {
  it("principal filters the log and loads older entries", async () => {
    const principal = makeMe({ roles: ["principal"], permissions: ["audit.read", "approvals.decide"] });
    const calls = mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: principal };
      if (path.startsWith("/audit?") && path.includes("before=")) return { status: 200, body: { rows: [row(3, { action: "auth.logout" })], next_before: null, areas } };
      if (path.startsWith("/audit")) return { status: 200, body: { rows: [row(1, { reason: "Wrong amount" })], next_before: "2026-10-01T00:00:00+00:00", areas } };
      return { status: 404 };
    });
    renderApp("/app/audit");
    expect(await screen.findByText("Rohan Patil (2026BCA001)")).toBeTruthy();
    expect(screen.getByText("Wrong amount")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Audit log" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Data export" })).toBeNull();

    fireEvent.change(screen.getByLabelText("Area"), { target: { value: "fees" } });
    fireEvent.change(screen.getByLabelText("Done by"), { target: { value: "meera" } });
    fireEvent.click(screen.getByRole("button", { name: "Show" }));
    await waitFor(() => expect(calls.some((c) => c.path === "/audit?area=fees&actor=meera")).toBe(true));
    fireEvent.click(await screen.findByRole("button", { name: "Show older entries" }));
    expect(await screen.findByText("auth.logout")).toBeTruthy();
    expect(calls.some((c) => c.path.includes("before=2026-10-01T00%3A00%3A00%2B00%3A00"))).toBe(true);
  });
});

describe("data export", () => {
  const request = {
    id: "x1", dataset: "students", dataset_label: "Students (all records)", reason: "Annual audit", status: "pending",
    requested_by: "Asha Kulkarni", requested_by_id: "u1", requested_at: "2026-10-04T05:00:00Z", decided_by: null, decided_at: null,
    decision_reason: null, expires_at: null, downloadable: false, downloads: 0,
  };
  const datasets = { students: "Students (all records)", fees: "Fee balances (per student, per year)" };

  it("system admin asks for an export and downloads it once approved", async () => {
    const admin = makeMe({ roles: ["system_admin"], permissions: ["export.request", "audit.read"] });
    let approved = false;
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: admin };
      if (path === "/export/requests" && method === "POST") {
        approved = true;
        return { status: 201, body: request };
      }
      if (path === "/export/requests") {
        const requests = approved ? [{ ...request, status: "approved", decided_by: "Dr. Deshmukh", expires_at: "2026-10-05T05:00:00Z", downloadable: true }] : [];
        return { status: 200, body: { datasets, requests } };
      }
      return { status: 404 };
    });
    renderApp("/app/exports");
    expect(await screen.findByText("No export requests yet")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Data"), { target: { value: "fees" } });
    fireEvent.change(screen.getByLabelText("Why is it needed?"), { target: { value: "Annual audit" } });
    fireEvent.click(screen.getByRole("button", { name: "Send for approval" }));
    const link = await screen.findByRole("link", { name: "Download CSV" });
    expect(link.getAttribute("href")).toBe("/api/v1/export/requests/x1/download");
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ dataset: "fees", reason: "Annual audit" });
  });

  it("principal approves a request", async () => {
    const principal = makeMe({ id: "u9", roles: ["principal"], permissions: ["approvals.decide", "audit.read"] });
    const calls = mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: principal };
      if (path === "/export/requests") return { status: 200, body: { datasets, requests: [request] } };
      if (path === "/export/requests/x1/decide") return { status: 200, body: { ...request, status: "approved" } };
      return { status: 404 };
    });
    renderApp("/app/exports");
    expect(await screen.findByText("Annual audit")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Send for approval" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    const dialog = document.querySelector("dialog[open]") as HTMLElement;
    fireEvent.click(dialog.querySelector(".btn-primary, .btn-danger") as HTMLElement);
    await waitFor(() => expect(calls.find((c) => c.path === "/export/requests/x1/decide")?.body).toEqual({ approve: true }));
  });
});

import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

const student = makeMe({ kind: "student", name: "Rohan Patil", prn: "2026BCA001", roles: ["student"], role_labels: ["Student"] });
const CATEGORIES = ["academic", "fees", "harassment", "other"].map((key) => ({ key, label: key, sensitive: key === "harassment" }));
const base = {
  id: "g1",
  number: "GRV/2026/00001",
  category: "fees",
  category_label: "Fees and scholarships",
  subject: "Scholarship not credited",
  text: "My MahaDBT amount is still not adjusted.",
  status: "open",
  status_label: "Open",
  anonymous: true,
  sensitive: false,
  created_at: "2026-10-05T04:30:00Z",
  due_date: "2026-10-10",
  overdue: false,
  escalated: false,
  resolution: null,
  feedback: null,
  reopened: 0,
};

describe("grievances", () => {
  it("a student raises a grievance anonymously in Hindi", async () => {
    localStorage.setItem("cc-lang", "hi");
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: student };
      if (path === "/me/grievances" && method === "GET") return { status: 200, body: { grievances: [], categories: CATEGORIES, sla_days: { fees: 5 } } };
      if (path === "/me/grievances") return { status: 201, body: { ...base, history: [] } };
      if (path === "/me/grievances/g1") return { status: 200, body: { ...base, history: [] } };
      return { status: 404 };
    });
    renderApp("/app/grievances");
    expect(await screen.findByText("आपने कोई शिकायत दर्ज नहीं की है।")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("विषय"), { target: { value: "harassment" } });
    expect(screen.getByText(/केवल आंतरिक शिकायत समिति/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("विषय"), { target: { value: "fees" } });
    fireEvent.change(screen.getByLabelText("शीर्षक"), { target: { value: "Scholarship not credited" } });
    fireEvent.change(screen.getByLabelText("क्या हुआ?"), { target: { value: "My MahaDBT amount is still not adjusted." } });
    fireEvent.click(screen.getByLabelText(/मेरा नाम छिपाएँ/));
    fireEvent.click(screen.getByRole("button", { name: "जमा करें" }));
    await waitFor(() =>
      expect(calls.find((c) => c.path === "/me/grievances" && c.method === "POST")?.body).toEqual({
        category: "fees",
        subject: "Scholarship not credited",
        text: "My MahaDBT amount is still not adjusted.",
        anonymous: true,
      }),
    );
    expect(await screen.findByText("नाम छिपा")).toBeTruthy();
  });

  it("a student who isn't satisfied sends feedback (reopens it)", async () => {
    const resolved = { ...base, status: "resolved", resolution: "Amount adjusted.", history: [{ at: "2026-10-06T05:00:00Z", kind: "reply", by: "staff", text: "We wrote to MahaDBT." }] };
    const calls = mockApi((_method, path) => {
      if (path === "/auth/me") return { status: 200, body: student };
      if (path === "/me/grievances") return { status: 200, body: { grievances: [resolved], categories: CATEGORIES, sla_days: {} } };
      if (path === "/me/grievances/g1") return { status: 200, body: resolved };
      if (path === "/me/grievances/g1/feedback") return { status: 200, body: { ...resolved, status: "open", reopened: 1, escalated: true } };
      return { status: 404 };
    });
    renderApp("/app/grievances");
    fireEvent.click(await screen.findByRole("button", { name: /Scholarship not credited/ }));
    expect(await screen.findByText("We wrote to MahaDBT.")).toBeTruthy();
    fireEvent.click(screen.getByLabelText("No"));
    fireEvent.click(screen.getByRole("button", { name: "Send feedback" }));
    await waitFor(() => expect(calls.find((c) => c.path === "/me/grievances/g1/feedback")?.body).toEqual({ satisfied: false, rating: 4, comment: null }));
  });

  it("the grievance cell sees an anonymous grievance and resolves it", async () => {
    const cell = makeMe({ roles: ["grievance"], role_labels: ["Grievance Cell"], permissions: ["grievance.manage", "grievance.read"] });
    const stats = { received: 1, open: 1, overdue: 0, resolved: 0, resolved_in_time: 0, average_days: null, satisfied: 0, feedback: 0, average_rating: null, by_category: [] };
    const calls = mockApi((_method, path) => {
      if (path === "/auth/me") return { status: 200, body: cell };
      if (path === "/grievances/stats") return { status: 200, body: stats };
      if (path.startsWith("/grievances?")) return { status: 200, body: [{ ...base, student: null, handler: null }] };
      if (path === "/grievances/g1") return { status: 200, body: { ...base, student: null, history: [], can_act: true } };
      if (path === "/grievances/g1/action") return { status: 200, body: { ...base, status: "resolved", student: null, history: [], can_act: true } };
      return { status: 404 };
    });
    renderApp("/app/grievances");
    expect(await screen.findByText(/Anonymous · due/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Scholarship not credited/ }));
    expect(await screen.findByText(/the student's name is hidden/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Reply, internal note or resolution"), { target: { value: "Amount adjusted on 6 Oct." } });
    fireEvent.click(screen.getByRole("button", { name: "Resolve" }));
    await waitFor(() => expect(calls.find((c) => c.path === "/grievances/g1/action")?.body).toEqual({ action: "resolve", text: "Amount adjusted on 6 Oct." }));
  });
});

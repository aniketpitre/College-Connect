import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeMe, mockApi, renderApp, signedOut } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

const cycle = {
  id: "cy1", name: "Admissions 2026-27", status: "open", academic_year_id: "y1", apply_until: "2026-10-30", course_start: "2026-11-15",
  application_fee: 50_000, documents: ["ssc_marksheet", "hsc_marksheet"], open_now: true,
  programmes: [{ programme_id: "p1", code: "BCA", name: "Bachelor of Computer Applications", year_of_study: 1, seats: 60, reserved: [{ category_id: "c2", code: "OBC", seats: 10 }] }],
};
const options = { cycles: [cycle], categories: [{ id: "c1", code: "OPEN", name: "Open" }, { id: "c2", code: "OBC", name: "OBC" }], online_payment: false };
const applicant = makeMe({ kind: "applicant", name: "Asha Pawar", roles: ["applicant"], role_labels: ["Applicant"] });
const app = (extra = {}) => ({
  id: "a1", number: null, cycle_id: "cy1", cycle_name: "Admissions 2026-27", apply_until: "2026-10-30", status: "draft", status_label: "", can_edit: true,
  personal: { name: "Asha Pawar", phone: "9811100001", email: "asha@example.com" }, programme_id: null, programme: null, programme_code: null, category: null,
  merit_score: null, required_documents: ["ssc_marksheet", "hsc_marksheet"], documents: [], fee: { status: "unpaid", amount: 50_000 }, reason: null, offer: null,
  rank: null, prn: null, submitted_at: null, ...extra,
});

describe("admissions", () => {
  it("someone applies: start, sign-in code, then their application", async () => {
    let me: unknown = null;
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return me ? { status: 200, body: me } : signedOut;
      if (path === "/admissions/options") return { status: 200, body: options };
      if (path === "/apply/start") return { status: 200, body: { sent: true } };
      if (path === "/apply/verify") {
        me = applicant;
        return { status: 200, body: applicant };
      }
      if (path === "/me/application") return { status: 200, body: app() };
      return { status: method === "GET" ? 404 : 200, body: {} };
    });
    renderApp("/apply");
    expect((await screen.findAllByText(/BCA · Bachelor of Computer Applications/)).length).toBeGreaterThan(0);
    fireEvent.change(screen.getAllByLabelText("Full name (as on the marksheet)")[0], { target: { value: "Asha Pawar" } });
    fireEvent.change(screen.getAllByLabelText("Mobile number")[0], { target: { value: "9811100001" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "asha@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send sign-in code" }));
    fireEvent.change(await screen.findByLabelText("Sign-in code"), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByRole("heading", { name: "My application" })).toBeTruthy();
    expect(calls.find((c) => c.path === "/apply/start")?.body).toEqual({ cycle_id: "cy1", name: "Asha Pawar", phone: "9811100001", email: "asha@example.com" });
    // Not everything is in yet: the list says what is missing, and submit waits.
    expect(screen.getByText(/Still needed: date of birth, gender, category, programme, previous exam percentage, SSC \(10th\) marksheet, HSC \(12th\) marksheet, application fee/)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Submit application" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText("Pay at the college office; they will mark it paid.")).toBeTruthy();
  });

  it("the applicant sees an offer in Hindi", async () => {
    localStorage.setItem("cc-lang", "hi");
    mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: applicant };
      if (path === "/admissions/options") return { status: 200, body: options };
      if (path === "/me/application")
        return { status: 200, body: app({ status: "offered", can_edit: false, number: "A/2026-27/00001", offer: { round: 1, seat: "open", seat_label: "Open", accept_by: "2026-10-20" }, fee: { status: "paid", amount: 50_000, receipt_number: "APP/2026-27/00001" } }) };
      return { status: 404 };
    });
    renderApp("/app");
    expect(await screen.findByText(/आपको सीट \(Open\) का प्रस्ताव है/)).toBeTruthy();
    expect(screen.getByText("भुगतान हो गया। रसीद APP/2026-27/00001।")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "आवेदन जमा करें" })).toBeNull();
  });

  it("the Admission Cell previews and publishes a round, then confirms an admission", async () => {
    const cell = makeMe({ roles: ["admission"], role_labels: ["Admission Cell"], permissions: ["admissions.read", "admissions.manage"] });
    const preview = (dry: boolean) => ({
      dry_run: dry, round: dry ? undefined : 1, accept_by: "2026-10-20", lapsed: 0, seats_left_after: { open: 0 },
      offers: [{ application_id: "a1", number: "A/2026-27/00001", name: "Asha Pawar", category: "OPEN", merit_score: 90, seat_label: "Open", rank: 1 }],
      waiting: [{ application_id: "a2", number: "A/2026-27/00002", name: "Ravi", category: "OBC", merit_score: 70, rank: 2 }],
    });
    const calls = mockApi((method, path, body) => {
      if (path === "/auth/me") return { status: 200, body: cell };
      if (path === "/admissions/cycles") return { status: 200, body: [cycle] };
      if (path.startsWith("/admissions/cycles/cy1/rounds") && method === "GET")
        return { status: 200, body: { seats: { total: { open: 50, c2: 10 }, taken: {}, left: { open: 50, c2: 10 } }, rounds: [] } };
      if (path === "/admissions/cycles/cy1/rounds") return { status: 200, body: preview((body as { dry_run: boolean }).dry_run) };
      if (path === "/admissions/applications/a1") return { status: 200, body: app({ status: "offered", number: "A/2026-27/00001", programme_id: "p1", programme: "BCA · Bachelor", offer: { round: 1, seat: "open", seat_label: "Open", accept_by: "2026-10-20" } }) };
      if (path === "/admissions/applications/a1/confirm") return { status: 200, body: { prn: "2026BCA061", temporary_password: "kite-river-42", student_id: "s9", fee_demand: 2_500_000, warning: null } };
      if (path.startsWith("/setup")) return { status: 200, body: { academic_years: [], programmes: [], divisions: [], categories: [] } };
      return { status: method === "GET" ? 200 : 404, body: [] };
    });
    renderApp("/app/admissions");
    fireEvent.click(await screen.findByRole("tab", { name: "Merit lists" }));
    fireEvent.click(await screen.findByRole("button", { name: "Preview next round" }));
    expect(await screen.findByText("Preview: nothing is sent yet")).toBeTruthy();
    expect(screen.getByText(/Waiting list: 2. Ravi \(OBC\)/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Publish and tell the applicants" }));
    expect(await screen.findByText("Round 1 published")).toBeTruthy();
    expect(calls.filter((c) => c.path === "/admissions/cycles/cy1/rounds" && c.method === "POST").map((c) => (c.body as { dry_run: boolean }).dry_run)).toEqual([true, false]);

    cleanup();
    renderApp("/app/admissions/applications/a1");
    fireEvent.click(await screen.findByRole("button", { name: "Confirm admission…" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm and create the student" }));
    expect(await screen.findByText("kite-river-42")).toBeTruthy();
    expect(screen.getByText("2026BCA061")).toBeTruthy();
    await waitFor(() => expect(calls.some((c) => c.path === "/admissions/applications/a1/confirm")).toBe(true));
  });
});

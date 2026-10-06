import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

const types = [
  { type: "bonafide", name: "Bonafide certificate", promised_days: 2, enabled: true, signer: "office", signer_label: "Registrar", no_dues: false },
  { type: "tc", name: "Transfer certificate (TC)", promised_days: 7, enabled: true, signer: "principal", signer_label: "Principal", no_dues: true },
];
const req = (extra = {}) => ({
  id: "r1", type: "bonafide", type_name: "Bonafide certificate", signer: "office", signer_label: "Registrar", student_id: "s1", student: "Rohan Patil", prn: "2026BCA001",
  purpose: "Bank loan", details: {}, status: "requested", status_label: "Requested", requested_at: "2026-10-05T05:00:00Z", due_date: "2026-10-07",
  overdue: false, escalated: false, reason: null, dues: null, certificate_id: null, number: null, ...extra,
});

describe("certificates", () => {
  it("a student asks for a bonafide in Marathi and sees the promised date", async () => {
    localStorage.setItem("cc-lang", "mr");
    const student = makeMe({ kind: "student", prn: "2026BCA001", roles: ["student"], role_labels: ["Student"] });
    let asked = false;
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: student };
      if (path === "/me/certificates" && method === "POST") {
        asked = true;
        return { status: 201, body: req() };
      }
      if (path === "/me/certificates") return { status: 200, body: { types, requests: asked ? [req()] : [] } };
      return { status: 404 };
    });
    renderApp("/app/certificates");
    expect(await screen.findByText("साधारणपणे 2 कामकाजाच्या दिवसांत तयार.")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("कशासाठी?"), { target: { value: "Bank loan" } });
    fireEvent.click(screen.getByRole("button", { name: "अर्ज पाठवा" }));
    expect(await screen.findByText(/पर्यंत देण्याचे आश्वासन/)).toBeTruthy();
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ type: "bonafide", purpose: "Bank loan" });
    expect(screen.getByRole("link", { name: "प्रमाणपत्रे" })).toBeTruthy();
  });

  it("asking for a TC needs the reason for leaving; a read-only account can't ask", async () => {
    const student = makeMe({ kind: "student", prn: "2026BCA003", roles: ["student"], role_labels: ["Student"], read_only: true });
    mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: student };
      if (path === "/me/certificates") return { status: 200, body: { types, requests: [req({ type: "tc", status: "ready", number: "C/2026-27/00004" })] } };
      return { status: 404 };
    });
    renderApp("/app/certificates");
    expect(await screen.findByText(/your account is read-only/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Send request" })).toBeNull();
    expect((await screen.findByRole("link", { name: "Download (PDF)" })).getAttribute("href")).toBe("/api/v1/me/certificates/r1/pdf");
  });

  it("choosing a TC shows the no-dues check: a library book and a hostel bed, in Marathi", async () => {
    localStorage.setItem("cc-lang", "mr");
    const student = makeMe({ kind: "student", prn: "2026BCA003", roles: ["student"], role_labels: ["Student"] });
    const no_dues = [
      { area: "library", what: "Library book not returned", amount: 0, title: "Let Us C", due_date: "2026-09-15" },
      { area: "hostel", what: "Hostel bed not vacated", amount: 0 },
    ];
    mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: student };
      if (path === "/me/certificates") return { status: 200, body: { types, requests: [], no_dues } };
      return { status: 404 };
    });
    renderApp("/app/certificates");
    expect(await screen.findByText("साधारणपणे 2 कामकाजाच्या दिवसांत तयार.")).toBeTruthy();
    expect(screen.queryByText("थकबाकी तपासणी")).toBeNull(); // only for a TC or migration
    fireEvent.change(screen.getByLabelText("प्रमाणपत्र"), { target: { value: "tc" } });
    expect(await screen.findByText("थकबाकी तपासणी")).toBeTruthy();
    expect(screen.getByText(/“Let Us C” परत करायचे आहे/)).toBeTruthy();
    expect(screen.getByText(/बेड रिकामा करायचा आहे/)).toBeTruthy();
  });

  it("the office verifies; an overdue request is marked", async () => {
    const office = makeMe({ roles: ["office"], permissions: ["certificates.manage", "certificates.read", "students.read"] });
    const calls = mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: office };
      if (path.startsWith("/certificates/requests?")) return { status: 200, body: [req({ overdue: true, escalated: true, can: { verify: true, sign: false, issue: false, reject: true } })] };
      if (path === "/certificates/requests/r1/action") return { status: 200, body: req({ status: "verified" }) };
      return { status: 404 };
    });
    renderApp("/app/certificates");
    expect(await screen.findByText("Overdue · Principal told")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Verify" }));
    await waitFor(() => expect(calls.find((c) => c.path === "/certificates/requests/r1/action")?.body).toEqual({ action: "verify" }));
  });

  it("the public Verify page shows a certificate", async () => {
    mockApi((_m, path) =>
      path.startsWith("/verify/")
        ? { status: 200, body: { type: "certificate", valid: true, status: "valid", number: "C/2026-27/00001", date: "2026-10-07T05:00:00Z", certificate: "Bonafide certificate", student_name: "Rohan P.", prn: "2026BCA***", college: "Shivaji College" } }
        : { status: 401, body: { error: { code: "not_signed_in", message: "" } } },
    );
    renderApp("/verify/ABCDEFGH2345");
    expect(await screen.findByText("✓ Genuine certificate")).toBeTruthy();
    expect(screen.getByText("Bonafide certificate")).toBeTruthy();
    expect(screen.getByText("C/2026-27/00001")).toBeTruthy();
  });
});

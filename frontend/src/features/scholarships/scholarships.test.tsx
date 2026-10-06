import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { crc32, makeZip } from "../../lib/zip";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

const student = makeMe({ kind: "student", name: "Neha Joshi", prn: "2026BCA002", roles: ["student"], role_labels: ["Student"] });
const result = (extra = {}) => ({
  code: "postmatric-obc",
  name: "Post-Matric Scholarship for OBC students",
  portal: "MahaDBT",
  link: "https://mahadbt.maharashtra.gov.in",
  note: null,
  status: "missing_documents",
  application_status: null,
  failed: [],
  unknown: [],
  missing_documents: ["caste_certificate"],
  ...extra,
});

describe("scholarships", () => {
  it("a student sees why, in Marathi, and declares the family income", async () => {
    localStorage.setItem("cc-lang", "mr");
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: student };
      if (path === "/me/scholarship-check" && method === "GET")
        return {
          status: 200,
          body: {
            family_income: null,
            schemes: [
              result({ status: "check", unknown: ["income"], missing_documents: [] }),
              result({ code: "postmatric-sc", name: "Post-Matric (SC)", status: "not_eligible", failed: [{ rule: "category", allowed: ["SC"] }] }),
            ],
          },
        };
      if (path === "/me/scholarship-check/income") return { status: 200, body: { family_income: 120000, schemes: [result()] } };
      return { status: 404 };
    });
    renderApp("/app/scholarships");
    expect(await screen.findByText("अधिक माहिती हवी")).toBeTruthy();
    expect(screen.getByText("वर तुमचे कौटुंबिक उत्पन्न लिहा")).toBeTruthy();
    expect(screen.getByText("फक्त या प्रवर्गांसाठी: SC")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("कुटुंबाचे वार्षिक उत्पन्न (₹)"), { target: { value: "120000" } });
    fireEvent.click(screen.getByRole("button", { name: "जतन करा" }));
    await waitFor(() => expect(calls.find((c) => c.path === "/me/scholarship-check/income")?.body).toEqual({ family_income: 120000 }));
    expect(await screen.findByText(/जातीचा दाखला/)).toBeTruthy();
  });

  it("builds a valid ZIP for the full export", async () => {
    expect(crc32(new TextEncoder().encode("123456789"))).toBe(0xcbf43926);
    const blob = makeZip([{ name: "a.txt", data: new TextEncoder().encode("hello") }]);
    const bytes = new Uint8Array(await blob.arrayBuffer());
    const view = new DataView(bytes.buffer);
    expect(view.getUint32(0, true)).toBe(0x04034b50);
    expect(view.getUint32(bytes.length - 22, true)).toBe(0x06054b50);
    expect(view.getUint16(bytes.length - 12, true)).toBe(1);
  });

  it("the Principal creates an API key and sees it once", async () => {
    const principal = makeMe({ roles: ["principal"], permissions: ["api_keys.manage"] });
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: principal };
      if (path === "/api-keys" && method === "GET") return { status: 200, body: { keys: [], scopes: { "students:read": "Students", "notices:read": "Notices" } } };
      if (path === "/api-keys")
        return {
          status: 201,
          body: { id: "k1", name: "Website", prefix: "ab12cd34", scopes: ["notices:read"], created_at: "", expires_at: "", last_used_at: null, calls: 0, state: "active", key: "cc_ab12cd34_secret" },
        };
      return { status: 404 };
    });
    renderApp("/app/api-keys");
    fireEvent.change(await screen.findByLabelText("What will use it"), { target: { value: "Website" } });
    fireEvent.click(screen.getByRole("checkbox", { name: /notices:read/ }));
    fireEvent.click(screen.getByRole("button", { name: "Create key" }));
    expect(await screen.findByText("cc_ab12cd34_secret")).toBeTruthy();
    expect(calls.find((c) => c.path === "/api-keys" && c.method === "POST")?.body).toEqual({ name: "Website", scopes: ["notices:read"], valid_days: 365 });
  });
});

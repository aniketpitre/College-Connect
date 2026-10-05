import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SetupOverview } from "../../lib/setup";
import type { Student } from "../../lib/students";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

const setup: SetupOverview = {
  institution: { name: "", short_name: "", address: "", phone: "", email: null, website: "", university: "", college_code: "", receipt_prefix: "R", certificate_prefix: "C" },
  current_year: null,
  academic_years: [],
  departments: [],
  programmes: [{ id: "p1", status: "active", code: "BCA", name: "Bachelor of Computer Applications", department_id: "d1", level: "UG", duration_years: 3, semesters_per_year: 2, year_labels: ["FY", "SY", "TY"] }],
  divisions: [{ id: "v1", status: "active", programme_id: "p1", year_of_study: 1, name: "A", capacity: 60 }],
  categories: [
    { id: "c1", status: "active", code: "OPEN", name: "Open", reserved_percent: null },
    { id: "c2", status: "active", code: "OBC", name: "Other Backward Class", reserved_percent: null },
  ],
};

const student: Student = {
  id: "s1", user_id: "u9", prn: "2026BCA001", name: "Rohan Patil", phone: "9876543210", email: null,
  programme_id: "p1", programme_code: "BCA", programme_name: "Bachelor of Computer Applications", year_of_study: 1, year_label: "FY",
  division_id: "v1", division: "A", roll_no: "12", category_id: "c1", category_code: "OPEN", category_name: "Open",
  status: "active", has_photo: false, mother_name: "Sunita", gender: "male", dob: "2007-04-12", apaar_id: null,
  aadhaar_masked: "XXXX XXXX 0123", address: { line: "12 MG Road", city: "Pune", district: "Pune", state: "Maharashtra", pincode: "411001" },
  guardian: { name: "Suresh Patil", relation: "Father", phone: "9822012345", email: null }, previous_education: null,
  admission_date: null, guardian_consent: false, photo_url: null,
  documents: [{ id: "doc1", type: "hsc_marksheet", filename: "hsc.pdf", status: "pending", reason: null, uploaded_at: "2026-10-01T10:00:00Z", url: "/files/f1" }],
};

const office = makeMe({ roles: ["office"], permissions: ["setup.read", "students.read", "students.manage", "students.import"] });

describe("students (office)", () => {
  it("lists students and adds one, showing the temporary password", async () => {
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: office };
      if (path === "/setup") return { status: 200, body: setup };
      if (path.startsWith("/students/change-requests")) return { status: 200, body: [] };
      if (method === "POST" && path === "/students") return { status: 201, body: { student: { ...student, id: "s2", name: "Neha Joshi", prn: "2026BCA002" }, temporary_password: "abcd-efgh-jkmn" } };
      if (path.startsWith("/students?")) return { status: 200, body: { items: [student], total: 1 } };
      return { status: 404 };
    });
    renderApp("/app/students");
    expect(await screen.findByText("Rohan Patil")).toBeTruthy();
    expect(screen.getByText("BCA · FY · A")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Add student" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("PRN"), { target: { value: "2026BCA002" } });
    fireEvent.change(within(dialog).getByLabelText("Programme"), { target: { value: "p1" } });
    fireEvent.change(within(dialog).getByLabelText("Year"), { target: { value: "1" } });
    fireEvent.change(within(dialog).getByLabelText("Division"), { target: { value: "v1" } });
    fireEvent.change(within(dialog).getByLabelText("Full name"), { target: { value: "Neha Joshi" } });
    fireEvent.change(within(dialog).getByLabelText("Guardian's name"), { target: { value: "Anil Joshi" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Add student and create login" }));
    expect(await screen.findByText("abcd-efgh-jkmn")).toBeTruthy();
    const body = calls.find((c) => c.method === "POST" && c.path === "/students")?.body as Record<string, unknown>;
    expect(body).toMatchObject({ prn: "2026BCA002", programme_id: "p1", year_of_study: 1, division_id: "v1", name: "Neha Joshi", guardian: { name: "Anil Joshi" }, guardian_consent: false });
    expect(body.address).toEqual({ state: "Maharashtra" });
  });

  it("approves a correction and verifies a document on the student's page", async () => {
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: office };
      if (path === "/setup") return { status: 200, body: setup };
      if (path === "/students/s1") return { status: 200, body: student };
      if (path.startsWith("/students/change-requests?status=pending"))
        return {
          status: 200,
          body: [{ id: "r1", student_id: "s1", changes: { category_id: "c2" }, current: { category_id: "c1" }, reason: "As per caste certificate", status: "pending", decision_reason: null, created_at: "2026-10-02T10:00:00Z", decided_at: null }],
        };
      if (path.startsWith("/students/change-requests?")) return { status: 200, body: [] };
      if (method === "POST") return { status: 200, body: student };
      return { status: 404 };
    });
    renderApp("/app/students/s1");
    expect(await screen.findByRole("heading", { name: "Rohan Patil" })).toBeTruthy();
    expect(screen.getByText("XXXX XXXX 0123")).toBeTruthy();
    expect(screen.getByText("1 document(s) to check")).toBeTruthy();

    fireEvent.click(screen.getByRole("tab", { name: "Correction requests" }));
    expect(await screen.findByText("OBC · Other Backward Class")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Approve and update record" }));
    await waitFor(() => expect(calls.some((c) => c.path === "/students/change-requests/r1/decide")).toBe(true));

    fireEvent.click(screen.getByRole("tab", { name: "Documents (1)" }));
    fireEvent.click(screen.getByRole("button", { name: "Verify" }));
    await waitFor(() => expect(calls.find((c) => c.path === "/students/s1/documents/doc1/decide")?.body).toEqual({ verified: true }));
  });
});

describe("my profile (student)", () => {
  const me = makeMe({ kind: "student", prn: "2026BCA001", roles: ["student"], role_labels: ["Student"] });

  it("shows the record in Marathi and asks for an address correction with the full address", async () => {
    localStorage.setItem("cc-lang", "mr");
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: me };
      if (path === "/me/student") return { status: 200, body: student };
      if (path === "/me/student/options") return { status: 200, body: { categories: [{ id: "c1", code: "OPEN", name: "Open" }] } };
      if (path === "/me/student/change-requests" && method === "GET") return { status: 200, body: [] };
      if (path === "/me/student/change-requests") return { status: 201, body: {} };
      return { status: 404 };
    });
    renderApp("/app/profile");
    expect(await screen.findByRole("heading", { name: "माझी प्रोफाइल" })).toBeTruthy();
    expect(screen.getByText("वैयक्तिक माहिती")).toBeTruthy();
    expect(screen.getByText("तपासणी बाकी")).toBeTruthy(); // document waiting for check
    expect(screen.getByRole("link", { name: "माझी प्रोफाइल" })).toBeTruthy(); // nav follows the language
    expect(screen.getByRole("link", { name: "माझा डेटा डाउनलोड करा" }).getAttribute("href")).toBe("/api/v1/me/data-export");

    fireEvent.click(screen.getByRole("button", { name: "दुरुस्तीची विनंती करा" }));
    fireEvent.change(screen.getByLabelText("काय दुरुस्त करायचे?"), { target: { value: "address.city" } });
    fireEvent.change(screen.getByLabelText("बरोबर माहिती"), { target: { value: "Pimpri" } });
    fireEvent.change(screen.getByLabelText("कारण"), { target: { value: "Moved house" } });
    fireEvent.click(screen.getByRole("button", { name: "विनंती पाठवा" }));
    await screen.findByRole("status");
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({
      changes: { address: { line: "12 MG Road", city: "Pimpri", district: "Pune", state: "Maharashtra", pincode: "411001" } },
      reason: "Moved house",
    });
  });

  it("staff don't see My profile in the menu", async () => {
    mockApi((_m, path) => (path === "/auth/me" ? { status: 200, body: makeMe() } : { status: 404 }));
    renderApp("/app");
    await screen.findByRole("heading", { name: "Welcome, Asha" });
    expect(screen.queryByRole("link", { name: "My profile" })).toBeNull();
  });
});

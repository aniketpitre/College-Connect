import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { setChild } from "../../lib/child";
import { makeMe, mockApi, renderApp, signedOut } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
  setChild(null);
});

const parent = makeMe({ kind: "parent", name: "Suresh Patil", roles: ["parent"], role_labels: ["Parent"] });
const kids = [
  { id: "c1", name: "Rohan Patil", prn: "2026BCA001", class: "BCA · FY · A", status: "active", relation: "Father", photo_url: null, access: { fees: true, attendance: true, results: false } },
  { id: "c2", name: "Neha Patil", prn: "2026BCA002", class: "BCA · FY · A", status: "active", relation: "Father", photo_url: null, access: { fees: true, attendance: true, results: true } },
];
const home = (name: string) => ({ name, prn: "x", class: "BCA · FY · A", academic_year: "2026-27", photo_url: null, balance: 500_000, attendance: 82, cards: [] });

describe("parents", () => {
  it("sign in with a mobile number and a code sent by email", async () => {
    let me: unknown = null;
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return me ? { status: 200, body: me } : signedOut;
      if (path === "/auth/otp/request") return { status: 200, body: { sent: true } };
      if (path === "/auth/otp/verify") {
        me = parent;
        return { status: 200, body: parent };
      }
      if (path === "/parent/children") return { status: 200, body: kids.slice(0, 1) };
      if (path === "/me/home") return { status: 200, body: home("Rohan Patil") };
      return { status: method === "GET" ? 404 : 200 };
    });
    renderApp("/login");
    fireEvent.click(await screen.findByRole("tab", { name: "Parent" }));
    fireEvent.change(screen.getByLabelText("Mobile number"), { target: { value: "98765 00001" } });
    fireEvent.click(screen.getByRole("button", { name: "Send sign-in code" }));
    fireEvent.change(await screen.findByLabelText("Sign-in code"), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("heading", { name: "Rohan Patil" })).toBeTruthy();
    expect(calls.find((c) => c.path === "/auth/otp/verify")?.body).toEqual({ phone: "98765 00001", code: "123456" });
    expect(calls.find((c) => c.path === "/me/home")?.headers.get("X-Child")).toBe("c1");
  });

  it("switch between children; the menu follows what each child shares", async () => {
    const calls = mockApi((_m, path, _b, headers) => {
      if (path === "/auth/me") return { status: 200, body: parent };
      if (path === "/parent/children") return { status: 200, body: kids };
      if (path === "/me/home") return { status: 200, body: home(headers.get("X-Child") === "c2" ? "Neha Patil" : "Rohan Patil") };
      return { status: 404 };
    });
    renderApp("/app");
    expect(await screen.findByRole("heading", { name: "Rohan Patil" })).toBeTruthy();
    const nav = screen.getByRole("navigation", { name: "Portal" });
    expect(within(nav).queryByRole("link", { name: "Exams & results" })).toBeNull(); // Rohan doesn't share results
    expect(within(nav).queryByRole("link", { name: "My profile" })).toBeNull();
    fireEvent.change(screen.getByLabelText("Showing"), { target: { value: "c2" } });
    expect(await screen.findByRole("heading", { name: "Neha Patil" })).toBeTruthy();
    expect(within(nav).getByRole("link", { name: "Exams & results" })).toBeTruthy();
    expect(calls.filter((c) => c.path === "/me/home").map((c) => c.headers.get("X-Child"))).toEqual(["c1", "c2"]);
  });

  it("an adult student chooses what parents see", async () => {
    const student = makeMe({ kind: "student", name: "Rohan Patil", prn: "2026BCA001", roles: ["student"], role_labels: ["Student"] });
    const calls = mockApi((method, path, body) => {
      if (path === "/auth/me") return { status: 200, body: student };
      if (path === "/me/student") return { status: 200, body: { id: "s1", name: "Rohan Patil", prn: "2026BCA001", documents: [], status: "active" } };
      if (path === "/me/parent-access" && method === "GET")
        return { status: 200, body: { can_change: true, access: { fees: true, attendance: true, results: true }, parents: [{ name: "Suresh Patil", relation: "Father" }] } };
      if (path === "/me/parent-access") return { status: 200, body: { can_change: true, access: body, parents: [] } };
      return { status: 200, body: [] };
    });
    renderApp("/app/profile");
    expect(await screen.findByText("Linked: Suresh Patil (Father)")).toBeTruthy();
    fireEvent.click(screen.getByLabelText("Marks and results"));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ fees: true, attendance: true, results: false }));
  });

  it("the office links a parent, recording consent for an under-18 student", async () => {
    const office = makeMe({ roles: ["office"], role_labels: ["Office"], permissions: ["students.read", "students.manage"] });
    const student = { id: "s1", name: "Neha Patil", prn: "2026BCA002", status: "active", documents: [], programme_code: "BCA", year_label: "FY", division: "A" };
    const linked = { parents: [], minor: true, consent_recorded: false, access: { fees: true, attendance: true, results: true } };
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: office };
      if (path === "/students/s1") return { status: 200, body: student };
      if (path === "/students/s1/parents" && method === "GET") return { status: 200, body: linked };
      if (path === "/students/s1/parents")
        return { status: 201, body: { ...linked, consent_recorded: true, parents: [{ id: "p1", name: "Suresh Patil", phone: "9876500001", email: null, relation: "Father", status: "active", last_login_at: null, children: 1 }] } };
      return { status: 200, body: {} };
    });
    renderApp("/app/students/s1");
    fireEvent.click(await screen.findByRole("tab", { name: "Parents" }));
    fireEvent.click(await screen.findByRole("button", { name: "Link a parent" }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Suresh Patil" } });
    fireEvent.change(screen.getByLabelText("Mobile number"), { target: { value: "9876500001" } });
    const submit = screen.getByRole("button", { name: "Link parent" }) as HTMLButtonElement;
    expect(submit.disabled).toBe(true); // consent first
    fireEvent.click(screen.getByLabelText(/parent's consent is recorded/));
    fireEvent.click(submit);
    expect(await screen.findByText(/no email/)).toBeTruthy();
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ name: "Suresh Patil", phone: "9876500001", relation: "Father", consent: true });
  });
});

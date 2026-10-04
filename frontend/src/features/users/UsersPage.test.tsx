import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { User } from "../../lib/users";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: "s1",
    kind: "student",
    name: "Rohan Patil",
    email: null,
    prn: "2026BCA001",
    phone: null,
    roles: ["student"],
    role_labels: ["Student"],
    status: "active",
    must_change_password: true,
    mfa_enabled: false,
    mfa_required: false,
    locked: false,
    last_login_at: null,
    created_at: null,
    ...overrides,
  };
}

const ROLES = [
  { id: "faculty", label: "Faculty", mfa_required: false },
  { id: "accounts", label: "Accounts", mfa_required: true },
];

const office = makeMe({
  roles: ["office"],
  role_labels: ["Office"],
  permissions: ["users.read", "users.create.student", "users.update", "users.reset_password.student"],
});

describe("users page", () => {
  it("lists accounts with their status", async () => {
    mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: office };
      if (path === "/users/roles") return { status: 200, body: ROLES };
      if (path.startsWith("/users")) return { status: 200, body: { items: [makeUser({ locked: true })], total: 1 } };
      return { status: 404 };
    });
    renderApp("/app/users");
    expect(await screen.findByText("Rohan Patil")).toBeTruthy();
    expect(screen.getByText("PRN 2026BCA001")).toBeTruthy();
    expect(screen.getByText("Locked")).toBeTruthy();
    expect(screen.getByText("Temporary password")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Unlock" })).toBeTruthy();
  });

  it("office staff can add a student and see the temporary password once", async () => {
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: office };
      if (path === "/users/roles") return { status: 200, body: ROLES };
      if (method === "POST" && path === "/users")
        return { status: 201, body: { user: makeUser({ name: "Neha Joshi", prn: "2026BCA002" }), temporary_password: "abcd-efgh-jkmn" } };
      if (path.startsWith("/users")) return { status: 200, body: { items: [], total: 0 } };
      return { status: 404 };
    });
    renderApp("/app/users");
    fireEvent.click(await screen.findByRole("button", { name: "Add user" }));
    // Office cannot create staff, so there is no staff/student switch and no role list.
    expect(screen.queryByRole("tab", { name: "Staff" })).toBeNull();
    expect(screen.queryByText("Roles")).toBeNull();
    fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Neha Joshi" } });
    fireEvent.change(screen.getByLabelText("PRN (used to sign in)"), { target: { value: "2026bca002" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("abcd-efgh-jkmn")).toBeTruthy();
    expect(screen.getByRole("dialog", { name: "Temporary password" })).toBeTruthy();
    const post = calls.find((c) => c.method === "POST" && c.path === "/users");
    expect(post?.body).toEqual({ kind: "student", name: "Neha Joshi", prn: "2026BCA002", roles: [] });
  });

  it("shows field errors from the server next to the field", async () => {
    mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: office };
      if (path === "/users/roles") return { status: 200, body: ROLES };
      if (method === "POST" && path === "/users")
        return { status: 409, body: { error: { code: "conflict", message: "An account with this PRN already exists.", field: "prn" } } };
      if (path.startsWith("/users")) return { status: 200, body: { items: [], total: 0 } };
      return { status: 404 };
    });
    renderApp("/app/users");
    fireEvent.click(await screen.findByRole("button", { name: "Add user" }));
    fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Neha Joshi" } });
    fireEvent.change(screen.getByLabelText("PRN (used to sign in)"), { target: { value: "2026BCA001" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("An account with this PRN already exists.")).toBeTruthy();
  });

  it("system admins pick roles for new staff", async () => {
    const admin = makeMe({
      roles: ["system_admin"],
      permissions: ["users.read", "users.create.staff", "users.create.student", "users.update", "users.roles.manage"],
    });
    mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: admin };
      if (path === "/users/roles") return { status: 200, body: ROLES };
      if (path.startsWith("/users")) return { status: 200, body: { items: [], total: 0 } };
      return { status: 404 };
    });
    renderApp("/app/users");
    fireEvent.click(await screen.findByRole("button", { name: "Add user" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByRole("tab", { name: "Staff" })).toBeTruthy();
    expect(within(dialog).getByText("2-step required")).toBeTruthy();
    const submit = within(dialog).getByRole("button", { name: "Create account" }) as HTMLButtonElement;
    fireEvent.change(within(dialog).getByLabelText("Full name"), { target: { value: "Meera Rao" } });
    expect(submit.disabled).toBe(true); // a staff account needs at least one role
    fireEvent.click(within(dialog).getByLabelText("Faculty"));
    await waitFor(() => expect(submit.disabled).toBe(false));
  });
});

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
    department_id: null,
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

  it("office staff add students from the Students page, not here", async () => {
    mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: office };
      if (path === "/users/roles") return { status: 200, body: ROLES };
      if (path.startsWith("/users")) return { status: 200, body: { items: [makeUser()], total: 1 } };
      return { status: 404 };
    });
    renderApp("/app/users");
    await screen.findByText("Rohan Patil");
    expect(screen.queryByRole("button", { name: "Add user" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(screen.getByText(/edited in the/)).toBeTruthy();
    expect(screen.queryByLabelText("Full name")).toBeNull();
  });

  it("system admins add staff, pick roles and see the temporary password once", async () => {
    const admin = makeMe({
      roles: ["system_admin"],
      permissions: ["users.read", "users.create.staff", "users.create.student", "users.update", "users.roles.manage"],
    });
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: admin };
      if (path === "/users/roles") return { status: 200, body: ROLES };
      if (method === "POST" && path === "/users")
        return { status: 201, body: { user: makeUser({ kind: "staff", name: "Meera Rao", prn: null, email: "meera@college.edu.in" }), temporary_password: "abcd-efgh-jkmn" } };
      if (path.startsWith("/users")) return { status: 200, body: { items: [], total: 0 } };
      return { status: 404 };
    });
    renderApp("/app/users");
    fireEvent.click(await screen.findByRole("button", { name: "Add user" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).queryByRole("tab", { name: "Student" })).toBeNull();
    expect(within(dialog).getByText("2-step required")).toBeTruthy();
    const submit = within(dialog).getByRole("button", { name: "Create account" }) as HTMLButtonElement;
    fireEvent.change(within(dialog).getByLabelText("Full name"), { target: { value: "Meera Rao" } });
    fireEvent.change(within(dialog).getByLabelText("Email (used to sign in)"), { target: { value: "meera@college.edu.in" } });
    expect(submit.disabled).toBe(true); // a staff account needs at least one role
    fireEvent.click(within(dialog).getByLabelText("Faculty"));
    await waitFor(() => expect(submit.disabled).toBe(false));
    fireEvent.click(submit);
    expect(await screen.findByText("abcd-efgh-jkmn")).toBeTruthy();
    expect(calls.find((c) => c.method === "POST" && c.path === "/users")?.body).toEqual({
      kind: "staff",
      name: "Meera Rao",
      email: "meera@college.edu.in",
      roles: ["faculty"],
    });
  });

  it("shows field errors from the server next to the field", async () => {
    const admin = makeMe({ roles: ["system_admin"], permissions: ["users.read", "users.create.staff", "users.roles.manage"] });
    mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: admin };
      if (path === "/users/roles") return { status: 200, body: ROLES };
      if (method === "POST" && path === "/users")
        return { status: 409, body: { error: { code: "conflict", message: "Another account already uses this email.", field: "email" } } };
      if (path.startsWith("/users")) return { status: 200, body: { items: [], total: 0 } };
      return { status: 404 };
    });
    renderApp("/app/users");
    fireEvent.click(await screen.findByRole("button", { name: "Add user" }));
    fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Meera Rao" } });
    fireEvent.change(screen.getByLabelText("Email (used to sign in)"), { target: { value: "meera@college.edu.in" } });
    fireEvent.click(screen.getByLabelText("Faculty"));
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Another account already uses this email.")).toBeTruthy();
  });
});

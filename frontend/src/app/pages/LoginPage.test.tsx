import { cleanup, fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeMe, mockApi, renderApp, signedOut } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

function fill(label: RegExp | string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

describe("sign in", () => {
  it("signs a student in by PRN and opens the portal", async () => {
    let signedIn = false;
    const calls = mockApi((method, path, body) => {
      if (path === "/auth/login" && method === "POST") {
        signedIn = true;
        expect(body).toEqual({ identifier: "2026BCA001", password: "my secret 42" });
        return { status: 200, body: makeMe({ kind: "student", name: "Ravi Patil", prn: "2026BCA001" }) };
      }
      if (path === "/auth/me") return signedIn ? { status: 200, body: makeMe({ kind: "student", name: "Ravi Patil" }) } : signedOut;
      if (path === "/me/home") return { status: 200, body: { name: "Ravi Patil", prn: "2026BCA001", class: "BCA · FY · A", academic_year: "2026-27", photo_url: null, balance: 0, cards: [] } };
      return { status: 404 };
    });
    renderApp("/login");
    fill("PRN", " 2026BCA001 ");
    fill("Password", "my secret 42");
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("heading", { name: "Hello, Ravi" })).toBeTruthy();
    const login = calls.find((c) => c.path === "/auth/login")!;
    expect(login.headers.get("X-Requested-With")).toBe("XMLHttpRequest");
  });

  it("shows server errors in the chosen language", async () => {
    mockApi((_m, path) =>
      path === "/auth/login" ? { status: 401, body: { error: { code: "invalid_credentials", message: "Wrong email/PRN or password." } } } : signedOut,
    );
    renderApp("/login");
    fireEvent.click(screen.getByRole("button", { name: "मर" }));
    fill("PRN", "2026BCA001");
    fill("पासवर्ड", "nope nope nope");
    fireEvent.click(screen.getByRole("button", { name: "साइन इन" }));
    expect((await screen.findByRole("alert")).textContent).toBe("PRN/ईमेल किंवा पासवर्ड चुकीचा आहे.");
  });

  it("switches to email for staff", () => {
    mockApi(() => signedOut);
    renderApp("/login");
    fireEvent.click(screen.getByRole("tab", { name: "Staff" }));
    expect((screen.getByLabelText("College email") as HTMLInputElement).type).toBe("email");
  });
});

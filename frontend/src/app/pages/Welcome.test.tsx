import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PRIVACY_VERSION } from "../../i18n/privacy";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

const status = { privacy_version: PRIVACY_VERSION, phone: "9876543210", email: null, under_18: true, guardian_consent: false, done: false };

describe("first sign-in wizard", () => {
  it("sends students who haven't finished it there first", async () => {
    mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: makeMe({ kind: "student", prn: "2026BCA001", onboarding_required: true }) };
      if (path === "/me/onboarding") return { status: 200, body: status };
      return { status: 404 };
    });
    renderApp("/app");
    expect(await screen.findByRole("heading", { name: "Welcome to CollegeConnect" })).toBeTruthy();
  });

  it("confirms contact, needs the privacy notice accepted, saves the language", async () => {
    let onboarded = false;
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: makeMe({ kind: "student", prn: "2026BCA001", onboarding_required: !onboarded }) };
      if (path === "/me/onboarding" && method === "GET") return { status: 200, body: status };
      if (path === "/me/onboarding") {
        onboarded = true;
        return { status: 200, body: { ...status, done: true } };
      }
      return { status: 404 };
    });
    renderApp("/app/welcome");
    expect(((await screen.findByLabelText("Your mobile number")) as HTMLInputElement).value).toBe("9876543210");
    fireEvent.change(screen.getByLabelText("Your email (optional)"), { target: { value: "rohan@example.in" } });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(screen.getByRole("heading", { name: "Privacy notice" })).toBeTruthy();
    expect(screen.getByText(/You are under 18/)).toBeTruthy();
    const next = screen.getByRole("button", { name: "Next" }) as HTMLButtonElement;
    expect(next.disabled).toBe(true);
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(next);

    fireEvent.click(screen.getByLabelText(/मराठी/));
    expect(await screen.findByRole("heading", { name: "कॉलेजकनेक्टमध्ये स्वागत आहे" })).toBeTruthy(); // switches at once
    fireEvent.click(screen.getByRole("button", { name: "पूर्ण करा" }));
    await screen.findByRole("heading", { name: /स्वागत आहे, Asha/ });
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({
      phone: "9876543210",
      email: "rohan@example.in",
      accept_privacy: true,
      privacy_version: PRIVACY_VERSION,
      language: "mr",
    });
    await waitFor(() => expect(localStorage.getItem("cc-lang")).toBe("mr"));
  });

  it("goes back to the contact step when the number is rejected", async () => {
    mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: makeMe({ kind: "student", onboarding_required: true }) };
      if (path === "/me/onboarding" && method === "GET") return { status: 200, body: { ...status, under_18: false } };
      if (path === "/me/onboarding") return { status: 422, body: { error: { code: "validation_error", message: "Enter a 10-digit mobile number.", field: "phone" } } };
      return { status: 404 };
    });
    renderApp("/app/welcome");
    fireEvent.change(await screen.findByLabelText("Your mobile number"), { target: { value: "123" } });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Finish" }));
    expect(await screen.findByText("Enter a 10-digit mobile number.")).toBeTruthy();
    expect(screen.getByLabelText("Your mobile number")).toBeTruthy();
  });

  it("applies the language saved on the account at sign-in", async () => {
    mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 401, body: { error: { code: "not_signed_in", message: "Please sign in." } } };
      if (path === "/auth/login") return { status: 200, body: makeMe({ language: "hi" }) };
      return { status: 404 };
    });
    renderApp("/login");
    fireEvent.click(await screen.findByRole("tab", { name: "Staff" }));
    fireEvent.change(screen.getByLabelText("College email"), { target: { value: "asha@college.edu.in" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(localStorage.getItem("cc-lang")).toBe("hi"));
  });
});

import { cleanup, fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeMe, mockApi, renderApp, signedOut } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

const SETUP = { secret: "JBSWY3DPEHPK3PXP", otpauth_uri: "otpauth://totp/x", qr_svg: "data:image/svg+xml,x" };

describe("2-step verification page", () => {
  it("asks for the code, then continues to the portal", async () => {
    let state = "mfa_pending";
    const calls = mockApi((method, path, body) => {
      if (path === "/auth/me") return { status: 200, body: makeMe({ session_state: state as "mfa_pending" }) };
      if (method === "POST" && path === "/auth/mfa/verify") {
        if ((body as { code: string }).code !== "123456")
          return { status: 400, body: { error: { code: "invalid_code", message: "wrong", field: "code" } } };
        state = "active";
        return { status: 200, body: { ...makeMe(), recovery_codes_left: 8 } };
      }
      return { status: 404 };
    });
    renderApp("/login/2-step");
    const input = await screen.findByLabelText("6-digit code");
    fireEvent.change(input, { target: { value: "12 34 5x" } });
    expect((input as HTMLInputElement).value).toBe("12345"); // digits only
    fireEvent.change(input, { target: { value: "654321" } });
    fireEvent.click(screen.getByRole("button", { name: "Verify" }));
    expect(await screen.findByText("That code is not correct. Check the time on your phone and try again.")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("6-digit code"), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Verify" }));
    expect(await screen.findByRole("heading", { name: "Welcome, Asha" })).toBeTruthy();
    expect(calls.filter((c) => c.path === "/auth/mfa/verify")).toHaveLength(2);
  });

  it("accepts a recovery code instead", async () => {
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: makeMe({ session_state: "mfa_pending" }) };
      if (method === "POST" && path === "/auth/mfa/verify") return { status: 200, body: { ...makeMe(), recovery_codes_left: 7 } };
      return { status: 404 };
    });
    renderApp("/login/2-step");
    fireEvent.click(await screen.findByRole("button", { name: "Lost your phone? Use a recovery code" }));
    fireEvent.change(screen.getByLabelText("Recovery code"), { target: { value: "abcde-fghjk" } });
    fireEvent.click(screen.getByRole("button", { name: "Verify" }));
    await screen.findByRole("heading", { name: "Welcome, Asha" });
    expect(calls.find((c) => c.path === "/auth/mfa/verify")?.body).toEqual({ code: "abcde-fghjk" });
  });

  it("sets up 2-step and shows the recovery codes once before continuing", async () => {
    let state = "mfa_setup";
    mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: makeMe({ session_state: state as "mfa_setup", roles: ["accounts"] }) };
      if (method === "POST" && path === "/auth/mfa/setup") return { status: 200, body: SETUP };
      if (method === "POST" && path === "/auth/mfa/enable") {
        state = "active";
        return { status: 200, body: { recovery_codes: ["aaaaa-bbbbb", "ccccc-ddddd"], me: makeMe({ mfa_enabled: true }) } };
      }
      return { status: 404 };
    });
    renderApp("/login/2-step");
    expect(await screen.findByText("JBSW Y3DP EHPK 3PXP")).toBeTruthy();
    expect(screen.getByAltText("QR code")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Enter the 6-digit code the app shows."), { target: { value: "111222" } });
    fireEvent.click(screen.getByRole("button", { name: "Turn on 2-step verification" }));
    expect(await screen.findByText("aaaaa-bbbbb")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "I've saved them, continue" }));
    expect(await screen.findByRole("heading", { name: "Welcome, Asha" })).toBeTruthy();
  });

  it("is shown in Marathi when chosen", async () => {
    localStorage.setItem("cc-lang", "mr");
    mockApi((_m, path) => (path === "/auth/me" ? { status: 200, body: makeMe({ session_state: "mfa_pending" }) } : { status: 404 }));
    renderApp("/login/2-step");
    expect(await screen.findByRole("heading", { name: "2-टप्पी पडताळणी" })).toBeTruthy();
  });

  it("sends signed-out visitors to sign in", async () => {
    mockApi(() => signedOut);
    renderApp("/login/2-step");
    expect(await screen.findByRole("heading", { name: "Sign in to CollegeConnect" })).toBeTruthy();
  });
});

describe("password reset pages", () => {
  it("asks for a link and always gives the same answer", async () => {
    const calls = mockApi((_m, path) => (path === "/auth/password/forgot" ? { status: 200, body: { ok: true } } : signedOut));
    renderApp("/forgot-password");
    fireEvent.change(screen.getByLabelText("College email or PRN"), { target: { value: " 2026BCA001 " } });
    fireEvent.click(screen.getByRole("button", { name: "Send reset link" }));
    expect(await screen.findByRole("status")).toBeTruthy();
    expect(calls.find((c) => c.path === "/auth/password/forgot")?.body).toEqual({ identifier: "2026BCA001" });
  });

  it("sets a new password with the token from the link", async () => {
    const calls = mockApi((_m, path) => (path === "/auth/password/reset" ? { status: 200, body: { ok: true } } : signedOut));
    renderApp("/reset-password#tok_abcdefghijklmnopqrstuvwxyz");
    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "monsoon-chai-at-dawn" } });
    fireEvent.change(screen.getByLabelText("Type the new password again"), { target: { value: "monsoon-chai-at-dawn" } });
    fireEvent.click(screen.getByRole("button", { name: "Save password" }));
    expect(await screen.findByRole("status")).toBeTruthy();
    expect(calls.find((c) => c.path === "/auth/password/reset")?.body).toEqual({
      token: "tok_abcdefghijklmnopqrstuvwxyz",
      new_password: "monsoon-chai-at-dawn",
    });
  });

  it("explains an expired link and offers a new one", async () => {
    mockApi((_m, path) =>
      path === "/auth/password/reset"
        ? { status: 400, body: { error: { code: "invalid_token", message: "expired", field: "token" } } }
        : signedOut,
    );
    renderApp("/reset-password#tok_abcdefghijklmnopqrstuvwxyz");
    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "monsoon-chai-at-dawn" } });
    fireEvent.change(screen.getByLabelText("Type the new password again"), { target: { value: "monsoon-chai-at-dawn" } });
    fireEvent.click(screen.getByRole("button", { name: "Save password" }));
    expect(await screen.findByRole("link", { name: "Ask for a new link" })).toBeTruthy();
  });

  it("shows the bad-link message when the link has no token", () => {
    mockApi(() => signedOut);
    renderApp("/reset-password");
    expect(screen.getByText("This reset link is invalid or has expired. Ask for a new one.")).toBeTruthy();
  });
});

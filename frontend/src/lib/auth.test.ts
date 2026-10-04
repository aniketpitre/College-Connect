import { describe, expect, it } from "vitest";
import { makeMe } from "../test/utils";
import { hasPermission, pendingStep, safeNext } from "./auth";

describe("safeNext", () => {
  it("only allows same-site paths after sign-in", () => {
    expect(safeNext("/app/fees?x=1")).toBe("/app/fees?x=1");
    expect(safeNext("//evil.example/login")).toBeNull();
    expect(safeNext("https://evil.example")).toBeNull();
    expect(safeNext(null)).toBeNull();
  });
});

describe("pendingStep", () => {
  it("puts 2-step verification before a forced password change", () => {
    expect(pendingStep(makeMe({ session_state: "mfa_pending", must_change_password: true }))).toBe("/login/2-step");
    expect(pendingStep(makeMe({ must_change_password: true }))).toBe("/app/change-password");
    expect(pendingStep(makeMe())).toBeNull();
  });
});

describe("hasPermission", () => {
  it("checks the signed-in user's permissions", () => {
    expect(hasPermission(makeMe({ permissions: ["analytics.view"] }), "analytics.view")).toBe(true);
    expect(hasPermission(null, "analytics.view")).toBe(false);
  });
});

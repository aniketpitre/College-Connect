import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it } from "vitest";
import App from "./App";

afterEach(cleanup);

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe("routes", () => {
  it("serves the help desk at /", () => {
    renderAt("/");
    expect(screen.getByRole("heading", { name: "How can I help you today?" })).toBeTruthy();
  });

  it("redirects the old /#/admin link to the admin portal", () => {
    renderAt("/#/admin");
    expect(screen.getByRole("heading", { name: "Admin portal" })).toBeTruthy();
  });

  it("shows the verification code on the verify page", () => {
    renderAt("/verify/ABC123");
    expect(screen.getByText("ABC123")).toBeTruthy();
  });

  it("shows the portal shell with later-phase items disabled", () => {
    renderAt("/app");
    expect(screen.getByRole("link", { name: "Help desk analytics" })).toBeTruthy();
    expect(screen.getByText("Students").closest("[aria-disabled]")).toBeTruthy();
  });

  it("shows not found for unknown paths", () => {
    renderAt("/no/such/page");
    expect(screen.getByRole("heading", { name: "Page not found" })).toBeTruthy();
  });
});

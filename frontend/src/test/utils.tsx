import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { vi } from "vitest";
import App from "../app/App";
import type { Me } from "../lib/auth";

export type Handler = (method: string, path: string, body: unknown, headers: Headers) => { status: number; body?: unknown };

/** Replaces fetch with a fake API; returns the list of calls made. */
export function mockApi(handler: Handler) {
  const calls: { method: string; path: string; body: unknown; headers: Headers }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const method = init.method ?? "GET";
      const path = url.replace(/^.*\/api\/v1/, "");
      const body = init.body ? JSON.parse(init.body as string) : undefined;
      const headers = new Headers(init.headers);
      calls.push({ method, path, body, headers });
      const res = handler(method, path, body, headers);
      return new Response(res.body === undefined ? null : JSON.stringify(res.body), {
        status: res.status,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
  return calls;
}

export function renderApp(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

export const signedOut = { status: 401, body: { error: { code: "not_signed_in", message: "Please sign in." } } };

export function makeMe(overrides: Partial<Me> = {}): Me {
  return {
    id: "u1",
    kind: "staff",
    name: "Asha Kulkarni",
    email: "asha@college.edu.in",
    prn: null,
    roles: ["faculty"],
    role_labels: ["Faculty"],
    permissions: [],
    must_change_password: false,
    mfa_enabled: false,
    mfa_required: false,
    session_state: "active",
    ...overrides,
  };
}

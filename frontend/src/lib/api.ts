import type { AdminStats, Category, Language, QueryResponse } from "./types";

// Same origin in production (Vercel) and in development (Vite proxies /api to :8000).
const API_BASE: string = import.meta.env.VITE_API_BASE_URL ?? "";
export const API_V1 = `${API_BASE}/api/v1`;

/** Error returned by the API: {"error": {"code", "message", "field?"}}. */
export class ApiError extends Error {
  status: number;
  code: string;
  field?: string;

  constructor(status: number, code: string, message: string, field?: string) {
    super(message);
    this.status = status;
    this.code = code;
    this.field = field;
  }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body !== undefined && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  // Required by the backend on every cookie-authenticated change (blocks cross-site request forgery).
  headers.set("X-Requested-With", "XMLHttpRequest");
  let res: Response;
  try {
    res = await fetch(`${API_V1}${path}`, { ...init, headers, credentials: "include" });
  } catch {
    throw new ApiError(0, "network_error", "Could not reach the server. Check your connection and try again.");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const err = body?.error;
    throw new ApiError(res.status, err?.code ?? "error", err?.message ?? `Request failed (${res.status})`, err?.field);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export function askQuestion(question: string, language: Language, category?: Category): Promise<QueryResponse> {
  return apiFetch<QueryResponse>("/query", { method: "POST", body: JSON.stringify({ question, language, category }) });
}

export class AdminAuthError extends Error {}

export async function fetchAdminStats(token: string, days: number): Promise<AdminStats> {
  try {
    return await apiFetch<AdminStats>(`/admin/stats?days=${days}`, { headers: { Authorization: `Bearer ${token}` } });
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) throw new AdminAuthError(e.message);
    throw e;
  }
}

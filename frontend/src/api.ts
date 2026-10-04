import type { AdminStats, Category, Language, QueryResponse } from "./types";

// Dev: the FastAPI server on :8000. Production (Vercel): same origin, so relative "/api/..." URLs.
const API_BASE =
  import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "");

export async function askQuestion(
  question: string,
  language: Language,
  category?: Category,
): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE}/api/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, language, category }),
  });
  if (!res.ok) {
    throw new Error(`Query failed: ${res.status}`);
  }
  return res.json();
}

export class AdminAuthError extends Error {}

export async function fetchAdminStats(token: string, days: number): Promise<AdminStats> {
  const res = await fetch(`${API_BASE}/api/admin/stats?days=${days}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (res.status === 401) throw new AdminAuthError("Invalid admin token.");
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `Request failed: ${res.status}`);
  }
  return res.json();
}

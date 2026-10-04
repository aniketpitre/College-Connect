import type { Category, Language, QueryResponse } from "./types";

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

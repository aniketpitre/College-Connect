import type { Category, CategoryInfo, Language, QueryResponse } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

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

export async function fetchCategories(): Promise<CategoryInfo[]> {
  const res = await fetch(`${API_BASE}/api/categories`);
  if (!res.ok) {
    throw new Error(`Categories fetch failed: ${res.status}`);
  }
  return res.json();
}

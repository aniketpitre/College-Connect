import { useMutation } from "@tanstack/react-query";
import { apiFetch } from "./api";
import type { Language, QueryResponse } from "./types";

/** The signed-in help desk: documents and the notices this person may see. */
export function useAskAssistant() {
  return useMutation({
    mutationFn: (body: { question: string; language: Language }) => apiFetch<QueryResponse>("/assistant/ask", { method: "POST", body: JSON.stringify(body) }),
  });
}

export interface StaffAnswer {
  answered: boolean;
  summary: string;
  examples?: string[];
  query?: string;
  filters?: Record<string, string | number | boolean>;
  count?: number;
  columns?: { key: string; label: string; type: "text" | "money" | "number" | "date" }[];
  rows?: Record<string, string | number | boolean | null>[];
  more?: number;
  link?: string;
}

/** Staff: numbers and lists from the ERP through pre-defined, permission-checked queries. */
export function useAskStaff() {
  return useMutation({
    mutationFn: (question: string) => apiFetch<StaffAnswer>("/assistant/staff", { method: "POST", body: JSON.stringify({ question }) }),
  });
}

import { useMutation } from "@tanstack/react-query";
import { apiFetch } from "./api";
import type { Language, QueryResponse } from "./types";

/** The signed-in help desk: documents and the notices this person may see. */
export function useAskAssistant() {
  return useMutation({
    mutationFn: (body: { question: string; language: Language }) => apiFetch<QueryResponse>("/assistant/ask", { method: "POST", body: JSON.stringify(body) }),
  });
}

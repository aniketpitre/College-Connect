import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./api";

export interface KbDocument {
  id: string;
  title: string;
  document: string;
  category: string;
  audience: "public" | "everyone" | "students" | "staff" | "class";
  source: "bundled" | "upload" | "text" | "notice";
  notice_id: string | null;
  chunks: number;
  created_at: string;
  created_by: string | null;
}
export interface KbListing {
  documents: KbDocument[];
  status: {
    retrieval: "vector" | "bm25";
    generation: string;
    chunks: number;
    documents: number;
    embeddings_configured: boolean;
    chunks_total: number;
    chunks_embedded: number;
  };
  categories: string[];
}

const KEY = ["kb"] as const;

export const useKnowledge = () => useQuery({ queryKey: KEY, queryFn: () => apiFetch<KbListing>("/kb/documents") });

export function useAddDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { title: string; category: string; audience: string; text: string; file: File | null }) => {
      const form = new FormData();
      form.set("title", v.title);
      form.set("category", v.category);
      form.set("audience", v.audience);
      if (v.file) form.set("file", v.file);
      else form.set("text", v.text);
      return apiFetch<KbDocument>("/kb/documents", { method: "POST", body: form });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useRemoveDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch(`/kb/documents/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useReindex() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<{ notices: number; embedded: number; remaining: number }>("/kb/reindex", { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

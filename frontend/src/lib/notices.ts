import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./api";
import type { Language } from "./types";

export interface Translation {
  title: string;
  body: string;
}
export interface Notice {
  id: string;
  title: string;
  body?: string;
  hi: Translation | null;
  mr: Translation | null;
  audience: { kind: "everyone" | "students" | "staff" | "class"; programme_id?: string; year_of_study?: number; division_id?: string };
  audience_label: string;
  publish_at: string;
  expires_on: string | null;
  pinned: boolean;
  state: "published" | "scheduled" | "expired" | "withdrawn";
  has_attachment: boolean;
  author: string | null;
  emailed: number;
}
export interface EmailProgress {
  sent: number;
  failed: number;
  emailed: number;
  audience: number;
  remaining: number;
  done: boolean;
}

const KEY = ["notices"] as const;

/** The notice in the reader's language when staff typed one, otherwise English. */
export function localized(n: Pick<Notice, "title" | "body" | "hi" | "mr">, lang: Language): Translation {
  const t = lang === "en" ? null : n[lang];
  return { title: t?.title || n.title, body: (t?.body || n.body) ?? "" };
}

export function useNotices(q: string, manage = false) {
  const params = new URLSearchParams();
  if (q.trim()) params.set("q", q.trim());
  if (manage) params.set("manage", "true");
  return useQuery({ queryKey: [...KEY, q, manage], queryFn: () => apiFetch<Notice[]>(`/notices?${params}`) });
}

export const useNotice = (id: string) => useQuery({ queryKey: [...KEY, "one", id], queryFn: () => apiFetch<Notice>(`/notices/${id}`) });

function useInvalidate() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: KEY });
    qc.invalidateQueries({ queryKey: ["me", "home"] });
  };
}

export function useCreateNotice() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async ({ body, file }: { body: Record<string, unknown>; file: File | null }) => {
      const notice = await apiFetch<Notice>("/notices", { method: "POST", body: JSON.stringify(body) });
      if (!file) return notice;
      const form = new FormData();
      form.set("file", file);
      return apiFetch<Notice>(`/notices/${notice.id}/attachment`, { method: "POST", body: form });
    },
    onSuccess: invalidate,
  });
}

export function useUpdateNotice(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => apiFetch<Notice>(`/notices/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: invalidate,
  });
}

export function useEmailNotice(id: string) {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: () => apiFetch<EmailProgress>(`/notices/${id}/email`, { method: "POST" }), onSuccess: invalidate });
}

export const attachmentUrl = (id: string) => `/api/v1/notices/${id}/attachment`;

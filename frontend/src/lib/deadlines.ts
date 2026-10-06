import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./api";

export interface Deadline {
  id: string;
  notice_id: string;
  date: string;
  what: { en: string; hi?: string; mr?: string };
  status: "proposed" | "confirmed" | "dismissed";
  source: "ai" | "pattern" | "staff";
}

const key = (noticeId: string) => ["deadlines", noticeId] as const;

export const useNoticeDeadlines = (noticeId: string) =>
  useQuery({ queryKey: key(noticeId), queryFn: () => apiFetch<Deadline[]>(`/notices/${noticeId}/deadlines`) });

export function useDeadlineActions(noticeId: string) {
  const qc = useQueryClient();
  const done = () => qc.invalidateQueries({ queryKey: key(noticeId) });
  return {
    decide: useMutation({
      mutationFn: ({ id, ...body }: { id: string; status: "confirmed" | "dismissed"; date?: string; what?: string }) =>
        apiFetch<Deadline>(`/deadlines/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
      onSuccess: done,
    }),
    add: useMutation({
      mutationFn: (body: { date: string; what: string }) =>
        apiFetch<Deadline>(`/notices/${noticeId}/deadlines`, { method: "POST", body: JSON.stringify(body) }),
      onSuccess: done,
    }),
    find: useMutation({
      mutationFn: () => apiFetch<Deadline[]>(`/notices/${noticeId}/deadlines/find`, { method: "POST" }),
      onSuccess: done,
    }),
  };
}

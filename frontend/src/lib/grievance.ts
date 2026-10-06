import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./api";

export interface GrievanceEvent {
  at: string;
  kind: string;
  by: "student" | "staff" | "system";
  name?: string | null;
  text: string | null;
}
export interface Grievance {
  id: string;
  number: string;
  category: string;
  category_label: string;
  subject: string;
  text: string;
  status: "open" | "in_progress" | "resolved" | "closed";
  status_label: string;
  anonymous: boolean;
  sensitive: boolean;
  created_at: string;
  due_date: string;
  overdue: boolean;
  escalated: boolean;
  resolution: string | null;
  feedback: {
    satisfied: boolean;
    rating: number;
    comment: string | null;
  } | null;
  reopened: number;
  history?: GrievanceEvent[];
  student?: { name: string; prn: string } | null;
  handler?: string | null;
  can_act?: boolean;
}
export interface MyGrievances {
  grievances: Grievance[];
  categories: { key: string; label: string; sensitive: boolean }[];
  sla_days: Record<string, number>;
}
export interface GrievanceStats {
  received: number;
  open: number;
  overdue: number;
  resolved: number;
  resolved_in_time: number;
  average_days: number | null;
  satisfied: number;
  feedback: number;
  average_rating: number | null;
  by_category: {
    category: string;
    label: string;
    received: number;
    open: number;
    resolved: number;
  }[];
}

const post = <T>(path: string, body: unknown, method = "POST") => apiFetch<T>(path, { method, body: JSON.stringify(body) });

function useAct<V, T = unknown>(fn: (v: V) => Promise<T>, keys: string[][]) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => keys.forEach((k) => void qc.invalidateQueries({ queryKey: k })),
  });
}

export const useMyGrievances = () =>
  useQuery({
    queryKey: ["me", "grievances"],
    queryFn: () => apiFetch<MyGrievances>("/me/grievances"),
  });
export const useMyGrievance = (id: string | null) =>
  useQuery({
    queryKey: ["me", "grievances", id],
    queryFn: () => apiFetch<Grievance>(`/me/grievances/${id}`),
    enabled: !!id,
  });
export const useRaiseGrievance = () =>
  useAct((b: { category: string; subject: string; text: string; anonymous: boolean }) => post<Grievance>("/me/grievances", b), [["me", "grievances"]]);
export const useCommentGrievance = () =>
  useAct((b: { id: string; text: string }) => post<Grievance>(`/me/grievances/${b.id}/comment`, { text: b.text }), [["me", "grievances"]]);
export const useGrievanceFeedback = () =>
  useAct(
    (b: { id: string; satisfied: boolean; rating: number; comment: string }) =>
      post<Grievance>(`/me/grievances/${b.id}/feedback`, {
        satisfied: b.satisfied,
        rating: b.rating,
        comment: b.comment || null,
      }),
    [["me", "grievances"]],
  );

export const useGrievances = (status: string, category: string) =>
  useQuery({
    queryKey: ["grievances", status, category],
    queryFn: () => apiFetch<Grievance[]>(`/grievances?status=${status}${category ? `&category=${category}` : ""}`),
  });
export const useGrievance = (id: string | null) =>
  useQuery({
    queryKey: ["grievances", "one", id],
    queryFn: () => apiFetch<Grievance>(`/grievances/${id}`),
    enabled: !!id,
  });
export const useGrievanceStats = () =>
  useQuery({
    queryKey: ["grievances", "stats"],
    queryFn: () => apiFetch<GrievanceStats>("/grievances/stats"),
  });
export const useGrievanceAction = () =>
  useAct(
    (b: { id: string; action: string; text?: string }) =>
      post<Grievance>(`/grievances/${b.id}/action`, {
        action: b.action,
        text: b.text,
      }),
    [["grievances"], ["dashboard"]],
  );
export const useGrievanceSettings = (enabled: boolean) =>
  useQuery({
    queryKey: ["grievances", "settings"],
    queryFn: () => apiFetch<{ sla_days: Record<string, number>; close_after_days: number }>("/grievances/settings"),
    enabled,
  });
export const useSaveGrievanceSettings = () =>
  useAct((b: { sla_days: Record<string, number>; close_after_days: number }) => post("/grievances/settings", b, "PUT"), [["grievances", "settings"]]);

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./api";

export type Level = "high" | "medium" | "none";
export interface RiskRow {
  student_id: string;
  name: string;
  prn: string | null;
  class: string | null;
  level: Level;
  reasons: string[];
  signals: { attendance?: number | null; attendance_recent?: number | null; backlogs?: number; fees_overdue?: number };
  mentor: string | null;
  notes: number;
  last_note_at: string | null;
  follow_up_on: string | null;
  computed_at: string | null;
}
export interface RiskDetail extends RiskRow {
  history: { id: string; at: string; by: string; text: string; follow_up_on: string | null }[];
}
type Rule = { on: boolean; value: number };
export interface Rules {
  attendance_below: Rule;
  attendance_drop: Rule;
  marks_below: Rule;
  backlogs: Rule;
  fee_overdue: Rule;
}
export interface Assignments {
  students: { id: string; name: string; prn: string | null; mentor_id: string | null; mentor: string | null }[];
  mentors: { id: string; name: string }[];
}

function useAct<V, T = unknown>(fn: (v: V) => Promise<T>, keys: string[][]) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => keys.forEach((k) => void qc.invalidateQueries({ queryKey: k })) });
}
const send = <T>(path: string, method: string, body?: unknown) => apiFetch<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });

export const useMentees = (enabled: boolean) =>
  useQuery({
    queryKey: ["mentoring", "mentees"],
    queryFn: () => apiFetch<{ students: RiskRow[]; high: number; medium: number }>("/mentoring/mentees"),
    enabled,
  });
export const useAtRisk = (level: string, enabled: boolean) =>
  useQuery({
    queryKey: ["mentoring", "risk", level],
    queryFn: () => apiFetch<{ students: RiskRow[]; computed_at: string | null; rules: Rules }>(`/risk${level ? `?level=${level}` : ""}`),
    enabled,
  });
export const useRiskDetail = (id: string | null) =>
  useQuery({ queryKey: ["mentoring", "student", id], queryFn: () => apiFetch<RiskDetail>(`/risk/students/${id}`), enabled: !!id });
export const useAddNote = () =>
  useAct(
    (b: { id: string; text: string; follow_up_on: string | null }) =>
      send<RiskDetail>(`/risk/students/${b.id}/notes`, "POST", { text: b.text, follow_up_on: b.follow_up_on }),
    [["mentoring"]],
  );
export const useRules = (enabled: boolean) => useQuery({ queryKey: ["mentoring", "rules"], queryFn: () => apiFetch<Rules>("/risk/rules"), enabled });
export const useSaveRules = () => useAct((r: Rules) => send<Rules>("/risk/rules", "PUT", r), [["mentoring"]]);
export const useRecompute = () =>
  useAct(() => send<{ students: number; high: number; medium: number }>("/risk/recompute", "POST"), [["mentoring"], ["dashboard"]]);
export const useAssignments = (divisionId: string) =>
  useQuery({
    queryKey: ["mentoring", "assignments", divisionId],
    queryFn: () => apiFetch<Assignments>(`/mentoring/assignments?division_id=${divisionId}`),
    enabled: !!divisionId,
  });
export const useAssign = () =>
  useAct((b: { mentor_id: string | null; student_ids: string[] }) => send<{ updated: number }>("/mentoring/assignments", "PUT", b), [["mentoring"]]);

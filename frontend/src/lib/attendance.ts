import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./api";
import type { Lecture } from "./timetable";

export interface TodayLecture extends Lecture {
  takeable: boolean;
  editable_until: string;
  window_open: boolean;
  session: { present: number; total: number } | null;
}

export interface Today {
  date: string;
  holiday: string | null;
  lectures: TodayLecture[];
}

export interface SheetStudent {
  id: string;
  name: string;
  prn: string;
  roll_no: string | null;
  photo_url: string | null;
  exempt: "medical" | "official_duty" | null;
}

export interface Session {
  id: string;
  absent: string[];
  present: number;
  total: number;
  version: number;
  saved_by: string | null;
  saved_at: string;
}

export interface Sheet {
  lecture: Lecture;
  students: SheetStudent[];
  session: Session | null;
  can_save: boolean;
  can_request_edit: boolean;
  editable_until: string;
}

export interface MarkBody {
  slot_id: string;
  date: string;
  absent: string[];
  client_id?: string;
  base_version?: number | null;
}

export interface EditRequest {
  id: string;
  slot_id: string;
  date: string;
  class: string | null;
  subject: string;
  start: string | null;
  absent_now: number | null;
  absent_new: number;
  reason: string;
  status: "pending" | "approved" | "rejected";
  requested_by: string | null;
  requested_by_id: string;
  requested_at: string;
  decided_by: string | null;
  decision_reason: string | null;
}

export interface Exemption {
  id: string;
  student_id: string;
  student: string | null;
  prn: string | null;
  kind: "medical" | "official_duty";
  kind_label: string;
  from_date: string;
  to_date: string;
  reason: string;
  status: "active" | "cancelled";
  entered_by: string | null;
  created_at: string;
}

export const ATTENDANCE_KEY = ["attendance"] as const;

export function useToday(day: string, enabled = true) {
  return useQuery({ queryKey: [...ATTENDANCE_KEY, "today", day], queryFn: () => apiFetch<Today>(`/attendance/today?day=${day}`), enabled });
}

export const sheetPath = (slotId: string, day: string) => `/attendance/sheet?slot_id=${slotId}&day=${day}`;

export function useSheet(slotId: string, day: string) {
  return useQuery({ queryKey: [...ATTENDANCE_KEY, "sheet", slotId, day], queryFn: () => apiFetch<Sheet>(sheetPath(slotId, day)) });
}

export function saveAttendance(body: MarkBody): Promise<Session> {
  return apiFetch<Session>("/attendance/sheet", { method: "PUT", body: JSON.stringify(body) });
}

function useAttendanceMutation<V, R>(fn: (v: V) => Promise<R>) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => qc.invalidateQueries({ queryKey: ATTENDANCE_KEY }) });
}

export const useRequestEdit = () =>
  useAttendanceMutation((b: { slot_id: string; date: string; absent: string[]; reason: string }) =>
    apiFetch<EditRequest>("/attendance/edit-requests", { method: "POST", body: JSON.stringify(b) }),
  );

export function useEditRequests(status: string) {
  return useQuery({
    queryKey: [...ATTENDANCE_KEY, "requests", status],
    queryFn: () => apiFetch<EditRequest[]>(`/attendance/edit-requests${status ? `?status=${status}` : ""}`),
  });
}

export const useDecideEdit = () =>
  useAttendanceMutation(({ id, ...b }: { id: string; approve: boolean; reason?: string }) =>
    apiFetch<EditRequest>(`/attendance/edit-requests/${id}/decide`, { method: "POST", body: JSON.stringify(b) }),
  );

export function useExemptions(enabled: boolean) {
  return useQuery({ queryKey: [...ATTENDANCE_KEY, "exemptions"], queryFn: () => apiFetch<Exemption[]>("/attendance/exemptions"), enabled });
}

export const useAddExemption = () =>
  useAttendanceMutation((b: { student_id: string; kind: string; from_date: string; to_date: string; reason: string }) =>
    apiFetch<Exemption>("/attendance/exemptions", { method: "POST", body: JSON.stringify(b) }),
  );

export const useCancelExemption = () =>
  useAttendanceMutation(({ id, reason }: { id: string; reason: string }) =>
    apiFetch<void>(`/attendance/exemptions/${id}/cancel`, { method: "POST", body: JSON.stringify({ reason }) }),
  );

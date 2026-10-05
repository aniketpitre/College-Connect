import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./api";

export interface Slot {
  id: string;
  timetable_id: string;
  division_id: string;
  day: number;
  day_name: string;
  start: string;
  end: string;
  subject_id: string;
  subject_code: string | null;
  subject_name: string | null;
  subject_type: string | null;
  faculty_ids: string[];
  faculty: string[];
  room: string;
  batch: string | null;
}

export interface Lecture extends Slot {
  slot_id: string;
  date: string;
  status: "scheduled" | "cancelled" | "substitute" | "handed_over";
  division: string | null;
  substitute: string[];
  change_reason: string | null;
}

export interface Week {
  week_of: string;
  days: { date: string; day_name: string; holiday: string | null; lectures: Lecture[] }[];
}

export interface TimetableSummary {
  id: string;
  division_id: string;
  division: string | null;
  academic_year_id: string;
  term: number;
  semester: number;
  valid_from: string;
  valid_to: string;
  slots: number;
  can_manage: boolean;
}

export interface Timetable extends Omit<TimetableSummary, "slots"> {
  academic_year: string | null;
  slots: Slot[];
}

export interface TimetableOptions {
  subjects: { id: string; code: string; name: string; type: string }[];
  faculty: { id: string; name: string; department_id: string | null }[];
  rooms: string[];
}

export interface SlotInput {
  day: number;
  start: string;
  end: string;
  subject_id: string;
  faculty_ids: string[];
  room: string;
  batch: string | null;
}

const KEY = ["timetable"] as const;

export function useWeek(params: { divisionId?: string; mine?: boolean; student?: boolean; day: string }) {
  const { divisionId, mine, student, day } = params;
  return useQuery({
    queryKey: [...KEY, "week", { divisionId, mine, student, day }],
    queryFn: () => {
      if (student) return apiFetch<Week>(`/me/timetable?day=${day}`);
      const q = new URLSearchParams({ day });
      if (mine) q.set("mine", "true");
      else if (divisionId) q.set("division_id", divisionId);
      return apiFetch<Week>(`/timetable/week?${q}`);
    },
    enabled: Boolean(student || mine || divisionId),
  });
}

export function useTimetables(academicYearId?: string) {
  return useQuery({
    queryKey: [...KEY, "list", academicYearId],
    queryFn: () => apiFetch<TimetableSummary[]>(`/timetables${academicYearId ? `?academic_year_id=${academicYearId}` : ""}`),
  });
}

export function useTimetable(id: string | undefined) {
  return useQuery({ queryKey: [...KEY, "one", id], queryFn: () => apiFetch<Timetable>(`/timetables/${id}`), enabled: Boolean(id) });
}

export function useTimetableOptions(id: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: [...KEY, "options", id],
    queryFn: () => apiFetch<TimetableOptions>(`/timetables/${id}/options`),
    enabled: Boolean(id) && enabled,
  });
}

function useTimetableMutation<V, R>(fn: (v: V) => Promise<R>) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => qc.invalidateQueries({ queryKey: KEY }) });
}

const send = <T,>(path: string, method: string, body?: unknown) =>
  apiFetch<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });

export const useCreateTimetable = () =>
  useTimetableMutation((b: { academic_year_id: string; division_id: string; term: number; valid_from: string; valid_to: string }) =>
    send<Timetable>("/timetables", "POST", b),
  );
export const useUpdateTimetable = () =>
  useTimetableMutation(({ id, ...b }: { id: string; valid_from?: string; valid_to?: string }) => send<Timetable>(`/timetables/${id}`, "PATCH", b));
export const useSaveSlot = () =>
  useTimetableMutation(({ timetableId, slotId, body }: { timetableId: string; slotId?: string; body: SlotInput }) =>
    slotId ? send<Slot>(`/timetable-slots/${slotId}`, "PUT", body) : send<Slot>(`/timetables/${timetableId}/slots`, "POST", body),
  );
export const useRemoveSlot = () => useTimetableMutation((slotId: string) => send<void>(`/timetable-slots/${slotId}`, "DELETE"));
export const useSetChange = () =>
  useTimetableMutation(({ slotId, ...b }: { slotId: string; date: string; kind: "cancelled" | "substitute"; faculty_ids: string[]; room: string; reason: string }) =>
    send(`/timetable-slots/${slotId}/changes`, "POST", b),
  );
export const useUndoChange = () =>
  useTimetableMutation(({ slotId, date }: { slotId: string; date: string }) => send<void>(`/timetable-slots/${slotId}/changes/${date}`, "DELETE"));

/** YYYY-MM-DD in local time. */
export function isoDay(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function shiftDays(day: string, n: number): string {
  const [y, m, d] = day.split("-").map(Number);
  return isoDay(new Date(y, m - 1, d + n));
}

/** 1 = Monday … 6 = Saturday (0 = Sunday). */
export function dayNumber(iso: string): number {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).getDay(); // 1 = Monday … 6 = Saturday
}

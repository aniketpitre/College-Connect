import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "./api";
import * as offline from "./offline";
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
  /** Set when the network was unreachable and this is the copy saved on the phone. */
  offline?: boolean;
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
  offline?: boolean;
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

const isOffline = (e: unknown) => e instanceof ApiError && e.code === "network_error";

/** Fetch, keep a copy on the phone, and fall back to that copy when there is no network. */
async function withCache<T extends object>(key: string, path: string): Promise<T> {
  try {
    const data = await apiFetch<T>(path);
    await offline.put("cache", key, data);
    return data;
  } catch (e) {
    if (isOffline(e)) {
      const saved = await offline.get<T>("cache", key);
      if (saved) return { ...saved, offline: true };
    }
    throw e;
  }
}

export const sheetPath = (slotId: string, day: string) => `/attendance/sheet?slot_id=${slotId}&day=${day}`;
const sheetKey = (slotId: string, day: string) => `sheet:${slotId}:${day}`;

export function useToday(day: string, enabled = true) {
  return useQuery({
    queryKey: [...ATTENDANCE_KEY, "today", day],
    queryFn: async () => {
      const today = await withCache<Today>(`today:${day}`, `/attendance/today?day=${day}`);
      if (!today.offline) {
        // Save today's class lists on the phone too, so attendance works in a room without signal.
        for (const x of today.lectures.filter((l) => l.takeable))
          void withCache<Sheet>(sheetKey(x.slot_id, x.date), sheetPath(x.slot_id, x.date)).catch(() => undefined);
      }
      return today;
    },
    enabled,
  });
}

export function useSheet(slotId: string, day: string) {
  return useQuery({ queryKey: [...ATTENDANCE_KEY, "sheet", slotId, day], queryFn: () => withCache<Sheet>(sheetKey(slotId, day), sheetPath(slotId, day)) });
}

export function saveAttendance(body: MarkBody): Promise<Session> {
  return apiFetch<Session>("/attendance/sheet", { method: "PUT", body: JSON.stringify(body) });
}

// --- saves made offline ----------------------------------------------------------------------

export interface OutboxItem {
  key: string;
  body: MarkBody & { client_id: string };
  label: string;
  queued_at: string;
  state: "pending" | "conflict" | "failed";
  error?: string;
}

export const outboxKey = (slotId: string, day: string) => `${slotId}:${day}`;

/** Saves now, or keeps it on the phone when there is no network. */
export async function saveOrQueue(body: MarkBody & { client_id: string }, label: string): Promise<{ queued: boolean; session?: Session }> {
  try {
    return { queued: false, session: await saveAttendance(body) };
  } catch (e) {
    if (!isOffline(e)) throw e;
    const item: OutboxItem = { key: outboxKey(body.slot_id, body.date), body, label, queued_at: new Date().toISOString(), state: "pending" };
    await offline.put("outbox", item.key, item);
    return { queued: true };
  }
}

export function outboxItems(): Promise<OutboxItem[]> {
  return offline.all<OutboxItem>("outbox");
}

export function discardOutbox(key: string): Promise<void> {
  return offline.remove("outbox", key);
}

let syncing: Promise<{ sent: number; problems: number }> | null = null;

/** Sends waiting saves, oldest first. Stops at the first network failure (still offline). */
export function syncOutbox(): Promise<{ sent: number; problems: number }> {
  if (syncing) return syncing;
  syncing = (async () => {
    let sent = 0;
    let problems = 0;
    const items = (await outboxItems()).filter((i) => i.state === "pending").sort((a, b) => a.queued_at.localeCompare(b.queued_at));
    for (const item of items) {
      try {
        await saveAttendance(item.body);
        await offline.remove("outbox", item.key);
        await offline.remove("cache", sheetKey(item.body.slot_id, item.body.date));
        sent++;
      } catch (e) {
        if (isOffline(e)) break;
        const conflict = e instanceof ApiError && e.code === "attendance_conflict";
        await offline.put("outbox", item.key, { ...item, state: conflict ? "conflict" : "failed", error: (e as Error).message });
        problems++;
      }
    }
    return { sent, problems };
  })().finally(() => (syncing = null));
  return syncing;
}

export function useOutbox() {
  return useQuery({ queryKey: [...ATTENDANCE_KEY, "outbox"], queryFn: outboxItems, staleTime: 0 });
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

// --- percentages ------------------------------------------------------------------------------

export type AttendanceStatus = "ok" | "warning" | "critical" | "none";

export interface SubjectAttendance {
  subject_id: string;
  code: string | null;
  name: string | null;
  held: number;
  attended: number;
  percent: number | null;
  status: AttendanceStatus;
  can_miss: number;
  must_attend: number;
}

export interface MyAttendance {
  minimum: number;
  warning: number;
  overall: { held: number; attended: number; percent: number | null; status: AttendanceStatus };
  subjects: SubjectAttendance[];
  days: { date: string; lectures: { code: string | null; start: string; mark: "present" | "absent" | "exempt" }[] }[];
}

export const useMyAttendance = () => useQuery({ queryKey: [...ATTENDANCE_KEY, "mine"], queryFn: () => apiFetch<MyAttendance>("/me/attendance") });

export interface ClassReport {
  class: string;
  minimum: number;
  warning: number;
  subjects: { id: string; code: string | null; name: string | null; held: number }[];
  students: {
    student_id: string;
    name: string;
    prn: string;
    roll_no: string | null;
    subjects: Record<string, { held: number; attended: number; percent: number | null; status: AttendanceStatus }>;
    overall: number | null;
    status: AttendanceStatus;
    defaulter: boolean;
  }[];
}

export const useAttendanceClasses = () =>
  useQuery({ queryKey: [...ATTENDANCE_KEY, "classes"], queryFn: () => apiFetch<{ id: string; label: string }[]>("/attendance/classes") });

export function useClassReport(divisionId: string, from: string, to: string) {
  const q = new URLSearchParams({ division_id: divisionId });
  if (from) q.set("date_from", from);
  if (to) q.set("date_to", to);
  return useQuery({
    queryKey: [...ATTENDANCE_KEY, "report", divisionId, from, to],
    queryFn: () => apiFetch<ClassReport>(`/attendance/report?${q}`),
    enabled: Boolean(divisionId),
  });
}

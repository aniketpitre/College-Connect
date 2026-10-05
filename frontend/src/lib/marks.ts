import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./api";

export type MarkValue = number | "AB";
export type SheetStatus = "draft" | "published" | "approved" | "locked";

export const STATUS_TONE: Record<SheetStatus, "neutral" | "info" | "success" | "warning"> = {
  draft: "neutral",
  published: "info",
  approved: "success",
  locked: "warning",
};

export interface Component {
  key: string;
  name: string;
  max: number;
  held_on: string | null;
}

export interface Scheme {
  id: string;
  subject_id: string;
  academic_year_id: string;
  components: Component[];
  total: number;
  deadline: string | null;
  locked_in: boolean;
}

export interface SchemeRow {
  subject_id: string;
  code: string;
  name: string;
  semester: number;
  max_internal: number;
  scheme: Scheme | null;
  can_manage: boolean;
}

export interface ClassRow {
  division_id: string;
  class: string;
  subject_id: string;
  code: string;
  name: string;
  has_scheme: boolean;
  deadline: string | null;
  status: SheetStatus;
  status_label: string;
  complete: number;
  students: number;
}

export interface Sheet {
  class: string;
  division_id: string;
  subject: { id: string; code: string; name: string; max_internal: number };
  scheme: Scheme;
  status: SheetStatus;
  status_label: string;
  version: number;
  returned_reason: string | null;
  saved_by: string | null;
  approved_by: string | null;
  locked_by: string | null;
  deadline_passed: boolean;
  students: { id: string; name: string; prn: string; roll_no: string | null; marks: Record<string, MarkValue>; total: number | null }[];
  can_edit: boolean;
  can_publish: boolean;
  can_approve: boolean;
  can_return: boolean;
  can_lock: boolean;
  can_unlock: boolean;
}

export interface MyMarks {
  subject_id: string;
  code: string;
  name: string;
  out_of: number;
  status: SheetStatus;
  components: { name: string; max: number; mark: MarkValue | null }[];
  total: number | null;
}

export const MARKS_KEY = ["marks"] as const;

export const useMyClasses = (enabled: boolean) =>
  useQuery({ queryKey: [...MARKS_KEY, "mine"], queryFn: () => apiFetch<ClassRow[]>("/marks/my-classes"), enabled });
export const useMarksOverview = (enabled: boolean) =>
  useQuery({ queryKey: [...MARKS_KEY, "overview"], queryFn: () => apiFetch<ClassRow[]>("/marks/overview"), enabled });
export const useMyMarks = () => useQuery({ queryKey: [...MARKS_KEY, "me"], queryFn: () => apiFetch<MyMarks[]>("/me/marks") });

export function useSchemes(programmeId: string, semester: string) {
  const q = new URLSearchParams({ programme_id: programmeId });
  if (semester) q.set("semester", semester);
  return useQuery({ queryKey: [...MARKS_KEY, "schemes", programmeId, semester], queryFn: () => apiFetch<SchemeRow[]>(`/marks/schemes?${q}`), enabled: Boolean(programmeId) });
}

export function useSheet(divisionId: string, subjectId: string) {
  return useQuery({
    queryKey: [...MARKS_KEY, "sheet", divisionId, subjectId],
    queryFn: () => apiFetch<Sheet>(`/marks/sheet?division_id=${divisionId}&subject_id=${subjectId}`),
  });
}

function useMarksMutation<V, R>(fn: (v: V) => Promise<R>) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => qc.invalidateQueries({ queryKey: MARKS_KEY }) });
}

export const useSaveScheme = () =>
  useMarksMutation((b: { subject_id: string; components: { key?: string; name: string; max: number; held_on: string | null }[]; deadline?: string | null }) =>
    apiFetch<Scheme>("/marks/schemes", { method: "PUT", body: JSON.stringify(b) }),
  );
export const useSaveMarks = () =>
  useMarksMutation((b: { division_id: string; subject_id: string; marks: Record<string, Record<string, MarkValue | null>>; base_version: number }) =>
    apiFetch<Sheet>("/marks/sheet", { method: "PUT", body: JSON.stringify(b) }),
  );
export const useSheetAction = () =>
  useMarksMutation((b: { division_id: string; subject_id: string; action: string; reason?: string }) =>
    apiFetch<Sheet>("/marks/sheet/action", { method: "POST", body: JSON.stringify(b) }),
  );

// --- University Upload Guard ------------------------------------------------------------------

export interface GuardRow {
  class: string;
  division_id: string;
  subject_id: string;
  code: string;
  name: string;
  department?: string;
  has_scheme: boolean;
  status: SheetStatus;
  status_label: string;
  deadline: string | null;
  days_left: number | null;
  students: number;
  counts: { missing: number; above_max: number; absent_marked: number; ineligible: number };
  ready: boolean;
}

export interface GuardDetail extends GuardRow {
  issues: { kind: keyof GuardRow["counts"]; label: string; student_id: string; name: string; prn: string; detail: string }[];
}

export const useGuard = (enabled: boolean) =>
  useQuery({
    queryKey: [...MARKS_KEY, "guard"],
    queryFn: () => apiFetch<{ rows: GuardRow[]; departments: { name: string; subjects: number; ready: number; locked: number }[] }>("/marks/guard"),
    enabled,
  });

export const useGuardDetail = (divisionId: string, subjectId: string) =>
  useQuery({
    queryKey: [...MARKS_KEY, "guard", divisionId, subjectId],
    queryFn: () => apiFetch<GuardDetail>(`/marks/guard/detail?division_id=${divisionId}&subject_id=${subjectId}`),
  });

export function checkUploadFile(divisionId: string, subjectId: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<{ ok: boolean; rows?: number; problems: string[] }>(`/marks/guard/check-file?division_id=${divisionId}&subject_id=${subjectId}`, {
    method: "POST",
    body: form,
  });
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./api";

export type StudentStatus = "active" | "tc" | "graduated" | "dropped" | "detained";
export type DocStatus = "pending" | "verified" | "rejected";

export interface Address {
  line: string;
  city: string;
  district: string;
  state: string;
  pincode: string;
}
export interface Guardian {
  name: string;
  relation: string;
  phone: string | null;
  email: string | null;
}
export interface PreviousEducation {
  exam: string;
  board: string;
  year: number | null;
  percentage: number | null;
}

export interface StudentSummary {
  id: string;
  prn: string;
  name: string;
  phone: string | null;
  email: string | null;
  programme_id: string | null;
  programme_code: string | null;
  year_of_study: number | null;
  year_label: string | null;
  division_id: string | null;
  division: string | null;
  roll_no: string | null;
  batch?: string | null;
  category_code: string | null;
  status: StudentStatus;
  has_photo: boolean;
}

export interface StudentDocument {
  id: string;
  type: string;
  filename: string | null;
  status: DocStatus;
  reason: string | null;
  uploaded_at: string;
  url: string;
}

export interface Student extends StudentSummary {
  user_id: string;
  programme_name: string | null;
  category_id: string | null;
  category_name: string | null;
  mother_name: string | null;
  gender: "female" | "male" | "other" | null;
  dob: string | null;
  apaar_id: string | null;
  aadhaar_masked: string | null;
  address: Address | null;
  guardian: Guardian | null;
  previous_education: PreviousEducation | null;
  admission_date: string | null;
  guardian_consent: boolean;
  photo_url: string | null;
  documents: StudentDocument[];
}

export interface ChangeRequest {
  id: string;
  student_id: string;
  student_name?: string;
  prn?: string;
  changes: Record<string, unknown>;
  current: Record<string, unknown>;
  reason: string;
  status: "pending" | "approved" | "rejected";
  decision_reason: string | null;
  created_at: string;
  decided_at: string | null;
}

export interface HistoryEntry {
  at: string;
  action: string;
  by: string | null;
  reason: string | null;
  details: { before?: Record<string, unknown>; after?: Record<string, unknown> } | null;
}

export interface StudentFilters {
  q?: string;
  programme_id?: string;
  year_of_study?: string;
  division_id?: string;
  status?: string;
}

const KEY = ["students"] as const;
const ME_KEY = ["me", "student"] as const;

/** `/files/<id>` from the API → a URL the browser can open (same origin, cookie sent). */
export const fileUrl = (path: string) => `/api/v1${path}`;

export function useStudents(filters: StudentFilters) {
  const params = new URLSearchParams({ limit: "500" });
  for (const [k, v] of Object.entries(filters)) if (v) params.set(k, v);
  return useQuery({
    queryKey: [...KEY, "list", filters],
    queryFn: () => apiFetch<{ items: StudentSummary[]; total: number }>(`/students?${params}`),
  });
}

export function useStudent(id: string | undefined) {
  return useQuery({ queryKey: [...KEY, id], queryFn: () => apiFetch<Student>(`/students/${id}`), enabled: Boolean(id) });
}

export function useStudentHistory(id: string) {
  return useQuery({ queryKey: [...KEY, id, "history"], queryFn: () => apiFetch<HistoryEntry[]>(`/students/${id}/history`) });
}

export function useChangeQueue(status: string, studentId?: string) {
  const params = new URLSearchParams({ status });
  if (studentId) params.set("student_id", studentId);
  return useQuery({
    queryKey: [...KEY, "requests", status, studentId],
    queryFn: () => apiFetch<ChangeRequest[]>(`/students/change-requests?${params}`),
  });
}

function useInvalidate() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: KEY });
    qc.invalidateQueries({ queryKey: ME_KEY });
  };
}

export function useCreateStudent() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<{ student: Student; temporary_password: string }>("/students", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: invalidate,
  });
}

export function useUpdateStudent(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => apiFetch<Student>(`/students/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: invalidate,
  });
}

export function useDecideRequest() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, approve, reason }: { id: string; approve: boolean; reason?: string }) =>
      apiFetch<ChangeRequest>(`/students/change-requests/${id}/decide`, { method: "POST", body: JSON.stringify({ approve, reason }) }),
    onSuccess: invalidate,
  });
}

export function useDecideDocument(studentId: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ docId, verified, reason }: { docId: string; verified: boolean; reason?: string }) =>
      apiFetch<Student>(`/students/${studentId}/documents/${docId}/decide`, { method: "POST", body: JSON.stringify({ verified, reason }) }),
    onSuccess: invalidate,
  });
}

/** Multipart upload: a photo, or a document with its type. `base` is `/students/<id>` or `/me/student`. */
export function useUpload(base: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ kind, file, type }: { kind: "photo" | "documents"; file: File; type?: string }) => {
      const form = new FormData();
      form.set("file", file);
      if (type) form.set("type", type);
      return apiFetch<Student>(`${base}/${kind}`, { method: "POST", body: form });
    },
    onSuccess: invalidate,
  });
}

// --- the student themselves ---

export function useMyStudent() {
  return useQuery({ queryKey: ME_KEY, queryFn: () => apiFetch<Student>("/me/student") });
}

export function useMyRequests() {
  return useQuery({ queryKey: [...ME_KEY, "requests"], queryFn: () => apiFetch<ChangeRequest[]>("/me/student/change-requests") });
}

export function useRequestChange() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: { changes: Record<string, unknown>; reason: string }) =>
      apiFetch<ChangeRequest>("/me/student/change-requests", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: invalidate,
  });
}

export function useCorrectionOptions() {
  return useQuery({
    queryKey: [...ME_KEY, "options"],
    queryFn: () => apiFetch<{ categories: { id: string; code: string; name: string }[] }>("/me/student/options"),
    staleTime: 300_000,
  });
}

// --- import and promotion ---

export interface ImportError {
  row: number;
  field: string;
  message: string;
  prn: string | null;
}
export interface ImportReport {
  id: string;
  filename: string;
  status: "validated" | "has_errors" | "committing" | "done";
  total: number;
  valid: number;
  committed: number;
  error_count: number;
  errors: ImportError[];
  preview?: { line: number; prn: string; name: string }[];
}
export interface Credential {
  prn: string;
  name: string;
  temporary_password: string;
}
export interface PromotionPlan {
  programme: string;
  from_year: string;
  to_year: string | null;
  academic_year: string;
  students: { id: string; prn: string; name: string; outcome: "promoted" | "graduates" | "held_back" | "already_promoted" }[];
  counts: Record<"promoted" | "graduates" | "held_back" | "already_promoted", number>;
  dry_run: boolean;
}

export const IMPORT_TEMPLATE_URL = "/api/v1/students/imports/template.csv";

export function useValidateImport() {
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.set("file", file);
      return apiFetch<ImportReport>("/students/imports", { method: "POST", body: form });
    },
  });
}

export function useCommitImport() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiFetch<ImportReport & { done: boolean; credentials: Credential[] }>(`/students/imports/${id}/commit`, { method: "POST" }),
    onSuccess: invalidate,
  });
}

export function usePromote() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: { programme_id: string; from_year: number; hold_back: string[]; dry_run: boolean; reason?: string }) =>
      apiFetch<PromotionPlan>("/students/promote", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: (plan) => {
      if (!plan.dry_run) invalidate();
    },
  });
}

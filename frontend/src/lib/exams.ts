import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, API_V1 } from "./api";

export interface Paper {
  subject_id: string;
  code: string | null;
  name: string | null;
  date: string;
  start: string;
  end: string;
}

export interface ExamSession {
  id: string;
  name: string;
  kind: "university" | "internal";
  term: number;
  academic_year_id: string;
  classes: { programme_id: string; year_of_study: number; label: string }[];
  form_deadline: string;
  form_open: boolean;
  fee_head_code: string | null;
  seat_prefix: string;
  papers: Paper[];
  hall_tickets_released: boolean;
  counts?: { students: number; submitted: number; verified: number; rejected: number };
}

export type FormStatus = "not_submitted" | "submitted" | "verified" | "rejected";

export interface FormRow {
  student_id: string;
  name: string;
  prn: string;
  class: string | null;
  status: FormStatus;
  status_label: string;
  subjects: string[];
  backlogs: string[];
  seat_no: string | null;
  reason: string | null;
  attendance_ok: boolean;
  low_subjects: string[];
  fee_ok: boolean;
  fee_due: number;
  eligible: boolean;
}

export interface MyExam extends ExamSession {
  form_status: FormStatus;
  subjects: { code: string; name: string; backlog?: boolean }[];
  seat_no: string | null;
  reason: string | null;
  attendance_ok: boolean;
  low_subjects: string[];
  fee_ok: boolean;
  fee_due: number;
  hall_ticket: boolean;
}

const KEY = ["exams"] as const;

export const useExamSessions = (enabled = true) => useQuery({ queryKey: [...KEY, "sessions"], queryFn: () => apiFetch<ExamSession[]>("/exams/sessions"), enabled });
export const useExamForms = (id: string) => useQuery({ queryKey: [...KEY, "forms", id], queryFn: () => apiFetch<FormRow[]>(`/exams/sessions/${id}/forms`) });
export const useMyExams = () => useQuery({ queryKey: [...KEY, "me"], queryFn: () => apiFetch<MyExam[]>("/me/exams") });

function useExamMutation<V, R>(fn: (v: V) => Promise<R>) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => qc.invalidateQueries({ queryKey: KEY }) });
}
const post = <T,>(path: string, body?: unknown, method = "POST") => apiFetch<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });

export const useCreateSession = () =>
  useExamMutation((b: { name: string; kind: string; term: number; classes: { programme_id: string; year_of_study: number }[]; form_deadline: string; fee_head_code: string | null; seat_prefix: string }) =>
    post<ExamSession>("/exams/sessions", b),
  );
export const useUpdateSession = () =>
  useExamMutation(({ id, ...b }: { id: string; name?: string; form_deadline?: string; papers?: { subject_id: string; date: string; start: string; end: string }[]; hall_tickets_released?: boolean }) =>
    post<ExamSession>(`/exams/sessions/${id}`, b, "PATCH"),
  );
export const useVerifyForm = () =>
  useExamMutation(({ id, studentId, ...b }: { id: string; studentId: string; approve: boolean; reason?: string }) => post<FormRow>(`/exams/sessions/${id}/forms/${studentId}/verify`, b));
export const useVerifyEligible = () => useExamMutation((id: string) => post<{ verified: number; left: number }>(`/exams/sessions/${id}/verify-eligible`));
export const useAssignSeats = () => useExamMutation((id: string) => post<{ assigned: number; total: number }>(`/exams/sessions/${id}/seat-numbers`));
export const useSubmitForm = () => useExamMutation((id: string) => post<MyExam>(`/me/exams/${id}/form`));

export const examExportUrl = (id: string) => `${API_V1}/exams/sessions/${id}/export`;
export const hallTicketUrl = (id: string, studentId: string) => `${API_V1}/exams/sessions/${id}/hall-tickets/${studentId}.pdf`;
export const myHallTicketUrl = (id: string) => `${API_V1}/me/exams/${id}/hall-ticket.pdf`;

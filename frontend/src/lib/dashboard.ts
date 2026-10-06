import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./api";

export interface Dashboard {
  teaching?: {
    holiday: string | null;
    lectures: { slot_id: string; date: string; start: string; end: string; code: string; class: string; status: string; takeable: boolean; taken: boolean }[];
    marks_tasks: { division_id: string; subject_id: string; label: string; status: string; complete: number; students: number; deadline: string | null }[];
  };
  hod?: {
    classes: { division_id: string; class: string; students: number; attendance: number | null; defaulters: number }[];
    attendance_requests: number;
    marks_to_approve: number;
    workload: { name: string; hours: number }[];
  } | null;
  exam_cell?: {
    sessions: { id: string; name: string; form_deadline: string; to_verify: number; verified: number; results_published: boolean }[];
    marks: Record<string, number>;
    revaluations: number;
    subjects_without_scheme: number;
  };
  office?: { certificates_open: number; certificates_overdue: number; certificates_to_issue: number; corrections: number; documents: number };
  principal?: { approvals: number; exports: number; certificates_to_sign: number; certificates_overdue: number; attendance_minimum: number };
}

export const useDashboard = (enabled: boolean) =>
  useQuery({ queryKey: ["dashboard"], queryFn: () => apiFetch<Dashboard>("/dashboard"), enabled });

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, API_V1 } from "./api";

export interface ImportReport {
  rows: number;
  students: number;
  pass: number;
  atkt: number;
  problems: string[];
  imported: boolean;
}

export interface SessionResults {
  published: boolean;
  revaluation_until: string | null;
  students: { result_id: string; student_id: string; name: string | null; prn: string | null; sgpa: number | null; outcome: "pass" | "atkt" | "absent"; failed: string[] }[];
  counts: { pass: number; atkt: number; absent: number };
}

export interface Revaluation {
  id: string;
  exam: string | null;
  name: string | null;
  prn: string | null;
  code: string;
  old: { external: number | null; total: number | null; grade: string; grade_point: number; passed: boolean };
  new: { external: number | null; total: number | null; grade: string } | null;
  status: "requested" | "forwarded" | "changed" | "unchanged";
  status_label: string;
  requested_at: string;
}

export interface MyResult {
  id: string;
  exam: string;
  semesters: number[];
  sgpa: number | null;
  outcome: "pass" | "atkt" | "absent";
  credits: number;
  credits_earned: number;
  revaluation_until: string | null;
  subjects: {
    code: string;
    name: string;
    credits: number;
    internal: number | null;
    external: number | null;
    total: number | null;
    grade: string;
    grade_point: number;
    passed: boolean;
    revaluation: { status: string; status_label: string } | null;
    can_request_revaluation: boolean;
  }[];
}

export interface MyResults {
  cgpa: number | null;
  credits_earned: number;
  backlogs: { code: string; name: string; semester: number }[];
  results: MyResult[];
}

const KEY = ["results"] as const;

export const useSessionResults = (id: string, enabled: boolean) =>
  useQuery({ queryKey: [...KEY, "session", id], queryFn: () => apiFetch<SessionResults>(`/exams/sessions/${id}/results`), enabled });
export const useRevaluations = (status: string) =>
  useQuery({ queryKey: [...KEY, "revals", status], queryFn: () => apiFetch<Revaluation[]>(`/results/revaluations${status ? `?status=${status}` : ""}`) });
export const useMyResults = () => useQuery({ queryKey: [...KEY, "me"], queryFn: () => apiFetch<MyResults>("/me/results") });

export function importResults(id: string, file: File, dryRun: boolean) {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<ImportReport>(`/exams/sessions/${id}/results/import?dry_run=${dryRun}`, { method: "POST", body: form });
}

function useResultsMutation<V, R>(fn: (v: V) => Promise<R>) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => qc.invalidateQueries({ queryKey: KEY }) });
}

export const usePublishResults = () =>
  useResultsMutation(({ id, ...b }: { id: string; publish: boolean; revaluation_days?: number }) =>
    apiFetch<SessionResults>(`/exams/sessions/${id}/results/publish`, { method: "POST", body: JSON.stringify(b) }),
  );
export const useDecideReval = () =>
  useResultsMutation(({ id, ...b }: { id: string; status: string; external?: number | null; total?: number | null; grade?: string }) =>
    apiFetch<Revaluation>(`/results/revaluations/${id}/decide`, { method: "POST", body: JSON.stringify(b) }),
  );
export const useRequestReval = () =>
  useResultsMutation(({ resultId, code }: { resultId: string; code: string }) =>
    apiFetch<MyResults>(`/me/results/${resultId}/revaluation`, { method: "POST", body: JSON.stringify({ code }) }),
  );
export const myResultPdf = (id: string) => `${API_V1}/me/results/${id}.pdf`;

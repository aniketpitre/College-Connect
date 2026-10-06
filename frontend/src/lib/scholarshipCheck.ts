import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./api";

export interface SchemeResult {
  code: string;
  name: string;
  portal: string;
  link: string | null;
  note: string | null;
  status: "likely" | "missing_documents" | "check" | "applied" | "not_eligible";
  application_status: string | null;
  failed: ({ rule: string } & Record<string, unknown>)[];
  unknown: string[];
  missing_documents: string[];
}
export interface MyCheck {
  family_income: number | null;
  schemes: SchemeResult[];
}
export interface Scheme {
  code: string;
  name: string;
  portal: "MahaDBT" | "NSP" | "Other";
  link: string | null;
  categories: string[];
  income_limit: number | null;
  min_attendance: number | null;
  min_previous_percentage: number | null;
  gender: "any" | "female";
  domicile: string | null;
  years: number[];
  documents: string[];
  note: string | null;
  active: boolean;
}
export interface Candidate {
  student_id: string;
  name: string;
  prn: string;
  status: SchemeResult["status"];
  unknown: string[];
  missing_documents: string[];
}

export const useMyScholarshipCheck = () => useQuery({ queryKey: ["me", "scholarship-check"], queryFn: () => apiFetch<MyCheck>("/me/scholarship-check") });
export function useDeclareIncome() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (family_income: number) => apiFetch<MyCheck>("/me/scholarship-check/income", { method: "PUT", body: JSON.stringify({ family_income }) }),
    onSuccess: (data) => qc.setQueryData(["me", "scholarship-check"], data),
  });
}
export const useSchemes = () => useQuery({ queryKey: ["scholarship-schemes"], queryFn: () => apiFetch<Scheme[]>("/scholarship-schemes") });
export const useCandidates = (code: string) =>
  useQuery({
    queryKey: ["scholarship-schemes", code, "candidates"],
    queryFn: () => apiFetch<{ students: Candidate[] }>(`/scholarship-schemes/${code}/candidates`),
    enabled: !!code,
  });
export function useSaveScheme() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (s: Scheme) => apiFetch<Scheme>(`/scholarship-schemes/${s.code}`, { method: "PUT", body: JSON.stringify(s) }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["scholarship-schemes"] }),
  });
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./api";

export interface Metric {
  id: string;
  criterion: number;
  criterion_name: string;
  title: string;
  manual: boolean;
  value: string;
  columns: { key: string; label: string }[];
  rows: Record<string, string | number | null>[];
  gaps: string[];
  evidence_needed: string[];
  evidence: { id: string; title: string; filename: string; at: string }[];
}
export interface Aqar {
  year: { id: string; name: string };
  generated_at: string;
  metrics: Metric[];
  gaps: number;
  settings: { sanctioned_posts: number | null; intake: Record<string, number> };
}
type Counts = { total: number; female: number; male: number; other: number; general: number; ews: number; sc: number; st: number; obc: number };
export interface Aishe {
  year: string;
  students: (Counts & { programme: string; year: number })[];
  staff: (Counts & { staff: string; designation: string })[];
  gaps: string[];
}
export interface Nirf {
  year: string;
  points: { item: string; value: number | string | null }[];
}
export interface ApaarStudent {
  id: string;
  prn: string;
  name: string;
  apaar_id: string | null;
}
export interface ApaarCheck {
  students: number;
  valid: number;
  missing: ApaarStudent[];
  invalid: ApaarStudent[];
  duplicate: ApaarStudent[];
}
export interface Credits {
  year: string;
  rows: number;
  students: number;
  credits: number;
  skipped_without_apaar: number;
  sample: Record<string, string | number | null>[];
}

const q = (yearId: string) => (yearId ? `?year_id=${yearId}` : "");
export const reportUrl = (path: string, yearId = "") => `/api/v1/reports/${path}${q(yearId)}`;

export const useAqar = (yearId: string) => useQuery({ queryKey: ["reports", "naac", yearId], queryFn: () => apiFetch<Aqar>(`/reports/naac${q(yearId)}`) });
export const useAishe = (yearId: string, enabled: boolean) =>
  useQuery({ queryKey: ["reports", "aishe", yearId], queryFn: () => apiFetch<Aishe>(`/reports/aishe${q(yearId)}`), enabled });
export const useNirf = (yearId: string, enabled: boolean) =>
  useQuery({ queryKey: ["reports", "nirf", yearId], queryFn: () => apiFetch<Nirf>(`/reports/nirf${q(yearId)}`), enabled });
export const useApaar = (enabled: boolean) => useQuery({ queryKey: ["reports", "apaar"], queryFn: () => apiFetch<ApaarCheck>("/reports/apaar"), enabled });
export const useCredits = (yearId: string, enabled: boolean) =>
  useQuery({ queryKey: ["reports", "credits", yearId], queryFn: () => apiFetch<Credits>(`/reports/apaar/credits${q(yearId)}`), enabled });

function useAct<V, T = unknown>(fn: (v: V) => Promise<T>) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => void qc.invalidateQueries({ queryKey: ["reports"] }) });
}
export const useSaveNaacSettings = () =>
  useAct((b: { sanctioned_posts: number | null; intake: Record<string, number> }) =>
    apiFetch("/reports/naac/settings", { method: "PUT", body: JSON.stringify(b) }),
  );
export const useAddEvidence = () =>
  useAct((b: { metric: string; yearId: string; title: string; file: File }) => {
    const form = new FormData();
    form.append("file", b.file);
    form.append("title", b.title);
    if (b.yearId) form.append("year_id", b.yearId);
    return apiFetch(`/reports/naac/${b.metric}/evidence`, { method: "POST", body: form });
  });
export const useRemoveEvidence = () => useAct((id: string) => apiFetch(`/reports/naac/evidence/${id}`, { method: "DELETE" }));
export const useImportApaar = () =>
  useAct((file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiFetch<{ updated: number; problems: { row: number; prn: string; problem: string }[]; students: number; valid: number }>("/reports/apaar/import", {
      method: "POST",
      body: form,
    });
  });

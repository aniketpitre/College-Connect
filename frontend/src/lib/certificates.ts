import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, API_V1 } from "./api";

export type CertType = "bonafide" | "character" | "fee_paid" | "tc" | "migration" | "noc";
export type CertStatus = "requested" | "verified" | "signed" | "ready" | "rejected";

export interface CertTypeInfo {
  type: CertType;
  name: string;
  promised_days: number;
  enabled: boolean;
  signer: "office" | "principal" | "hod";
  signer_label: string;
  no_dues: boolean;
}

export interface CertRequest {
  id: string;
  type: CertType;
  type_name: string;
  signer: string;
  signer_label: string;
  student_id: string;
  student: string | null;
  prn: string | null;
  purpose: string;
  details: Record<string, string>;
  status: CertStatus;
  status_label: string;
  requested_at: string;
  due_date: string;
  overdue: boolean;
  escalated: boolean;
  reason: string | null;
  dues: { what: string; amount: number }[] | null;
  certificate_id: string | null;
  number: string | null;
  can?: { verify: boolean; sign: boolean; issue: boolean; reject: boolean };
}

export interface NewRequest {
  type: CertType;
  purpose: string;
  reason_for_leaving?: string;
  organisation?: string;
  from_date?: string;
  to_date?: string;
}

const KEY = ["certificates"] as const;

export const useMyCertificates = () =>
  useQuery({ queryKey: [...KEY, "me"], queryFn: () => apiFetch<{ types: CertTypeInfo[]; requests: CertRequest[] }>("/me/certificates") });
export const useCertQueue = (status: string) =>
  useQuery({ queryKey: [...KEY, "queue", status], queryFn: () => apiFetch<CertRequest[]>(`/certificates/requests${status ? `?status=${status}` : ""}`) });
export const useCertTypes = () => useQuery({ queryKey: [...KEY, "types"], queryFn: () => apiFetch<CertTypeInfo[]>("/certificates/types") });

function useCertMutation<V, R>(fn: (v: V) => Promise<R>) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => qc.invalidateQueries({ queryKey: KEY }) });
}
const send = <T,>(path: string, body: unknown, method = "POST") => apiFetch<T>(path, { method, body: JSON.stringify(body) });

export const useRequestCertificate = () => useCertMutation((b: NewRequest) => send<CertRequest>("/me/certificates", b));
export const useRequestFor = () => useCertMutation((b: NewRequest & { student_id: string }) => send<CertRequest>("/certificates/requests", b));
export const useCertAction = () =>
  useCertMutation(({ id, ...b }: { id: string; action: string; reason?: string }) => send<CertRequest>(`/certificates/requests/${id}/action`, b));
export const useUpdateCertType = () =>
  useCertMutation(({ type, ...b }: { type: string; promised_days: number; enabled: boolean }) => send<CertTypeInfo[]>(`/certificates/types/${type}`, b, "PUT"));

export const myCertificatePdf = (id: string) => `${API_V1}/me/certificates/${id}/pdf`;
export const staffCertificatePdf = (id: string) => `${API_V1}/certificates/requests/${id}/pdf`;

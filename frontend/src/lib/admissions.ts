import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./api";
import { ME_KEY, type Me } from "./auth";
import { checkout, type PaymentOrder } from "./payments";

export interface CycleProgramme {
  programme_id: string;
  code: string;
  name: string;
  year_of_study: number;
  seats: number;
  reserved: { category_id: string; code: string; seats: number }[];
}
export interface Cycle {
  id: string;
  name: string;
  status: "draft" | "open" | "closed";
  academic_year_id: string;
  apply_until: string;
  course_start: string;
  application_fee: number;
  documents: string[];
  open_now: boolean;
  programmes: CycleProgramme[];
  refund_rules?: { days_before: number; percent: number }[];
  processing_fee?: number;
}
export interface Options {
  cycles: Cycle[];
  categories: { id: string; code: string; name: string }[];
  online_payment: boolean;
}

export interface Application {
  id: string;
  number: string | null;
  cycle_id: string;
  cycle_name: string;
  apply_until: string;
  status: string;
  status_label: string;
  can_edit: boolean;
  personal: Record<string, unknown> & {
    name?: string;
    phone?: string;
    email?: string;
    dob?: string;
    gender?: string;
    category_id?: string;
    mother_name?: string;
    previous_education?: { exam?: string; board?: string; year?: number; percentage?: number };
  };
  programme_id: string | null;
  programme: string | null;
  programme_code: string | null;
  category: string | null;
  merit_score: number | null;
  required_documents: string[];
  documents: { id: string; type: string; filename: string; status: "pending" | "verified" | "rejected"; reason: string | null; url: string }[];
  fee: { status: "unpaid" | "paid" | "waived" | "not_needed"; amount: number; receipt_number?: string | null; mode?: string };
  reason: string | null;
  offer: { round: number; seat: string; seat_label: string; accept_by: string } | null;
  rank: number | null;
  prn: string | null;
  submitted_at: string | null;
  student_id?: string | null;
}

export const useAdmissionOptions = () => useQuery({ queryKey: ["admissions", "options"], queryFn: () => apiFetch<Options>("/admissions/options") });

const post = <T>(path: string, body?: unknown) => apiFetch<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const useStartApplication = () => useMutation({ mutationFn: (b: { cycle_id: string; name: string; phone: string; email: string }) => post<{ sent: boolean }>("/apply/start", b) });
export const useApplyCode = () => useMutation({ mutationFn: (phone: string) => post<{ sent: boolean }>("/apply/code", { phone }) });
export function useApplyVerify() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: { phone: string; code: string }) => post<Me>("/apply/verify", b),
    onSuccess: (me) => qc.setQueryData(ME_KEY, me),
  });
}
export const useEnquiry = () =>
  useMutation({ mutationFn: (b: { name: string; phone: string; programme_id?: string; message: string }) => post<{ ok: boolean }>("/admissions/enquiries/public", b) });

// --- the applicant ---
const MINE = ["me", "application"];
export const useMyApplication = () => useQuery({ queryKey: MINE, queryFn: () => apiFetch<Application>("/me/application") });
function useMineMutation<V>(fn: (v: V) => Promise<Application>) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: (a) => qc.setQueryData(MINE, a) });
}
export const useSaveApplication = () => useMineMutation((body: Record<string, unknown>) => apiFetch<Application>("/me/application", { method: "PUT", body: JSON.stringify(body) }));
export const useUploadApplicationDoc = () =>
  useMineMutation(({ type, file }: { type: string; file: File }) => {
    const form = new FormData();
    form.append("type", type);
    form.append("file", file);
    return apiFetch<Application>("/me/application/documents", { method: "POST", body: form });
  });
export const useSubmitApplication = () => useMineMutation(() => post<Application>("/me/application/submit"));
export const usePayApplicationFee = () =>
  useMineMutation(async () => {
    const order = await post<PaymentOrder>("/me/application/fee");
    const r = await checkout(order);
    if (!r) return apiFetch<Application>("/me/application");
    return post<Application>(`/me/application/fee/${order.id}/confirm`, { razorpay_payment_id: r.razorpay_payment_id, razorpay_signature: r.razorpay_signature });
  });

// --- Admission Cell ---
export interface ApplicationRow {
  id: string;
  number: string | null;
  name: string;
  phone: string;
  programme: string | null;
  category: string | null;
  merit_score: number | null;
  status: string;
  status_label: string;
  fee: string;
  documents_pending: number;
  rank: number | null;
  submitted_at: string | null;
}
export interface Enquiry {
  id: string;
  name: string;
  phone: string;
  email: string | null;
  programme: string | null;
  message: string;
  source: string;
  status: "new" | "contacted" | "applied" | "closed";
  follow_up_on: string | null;
  notes: { at: string; by: string; text: string }[];
  created_at: string;
}
export interface RoundPreview {
  dry_run: boolean;
  round?: number;
  accept_by: string;
  lapsed: number;
  offers: { application_id: string; number: string; name: string; category: string; merit_score: number; seat_label: string; rank: number }[];
  waiting: { application_id: string; number: string; name: string; category: string; merit_score: number; rank: number }[];
  seats_left_after: Record<string, number>;
}
export interface SeatInfo {
  seats: { total: Record<string, number>; taken: Record<string, number>; left: Record<string, number> };
  rounds: { number: number; accept_by: string; offers: number; waiting: number; created_at: string }[];
}
export interface Report {
  cycle: string;
  programmes: {
    programme_id: string;
    programme: string;
    seats: number;
    reserved: Record<string, number>;
    applied: number;
    drafts: number;
    verified: number;
    offered: number;
    admitted: number;
    waiting: number;
    cancelled: number;
    by_category: Record<string, { applied: number; admitted: number }>;
  }[];
}

export const useCycles = () => useQuery({ queryKey: ["admissions", "cycles"], queryFn: () => apiFetch<Cycle[]>("/admissions/cycles") });
export function useSaveCycle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Record<string, unknown> }) =>
      apiFetch<Cycle>(id ? `/admissions/cycles/${id}` : "/admissions/cycles", { method: id ? "PUT" : "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admissions"] }),
  });
}
export const useApplications = (f: { cycle_id?: string; programme_id?: string; status?: string; q?: string }) => {
  const params = new URLSearchParams(Object.entries(f).filter(([, v]) => v) as [string, string][]);
  return useQuery({ queryKey: ["admissions", "applications", f], queryFn: () => apiFetch<ApplicationRow[]>(`/admissions/applications?${params}`), enabled: Boolean(f.cycle_id) });
};
export const useApplication = (id: string) => useQuery({ queryKey: ["admissions", "application", id], queryFn: () => apiFetch<Application>(`/admissions/applications/${id}`) });
export function useApplicationAction(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ path, body }: { path: string; body: unknown }) => post<Record<string, unknown>>(`/admissions/applications/${id}/${path}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admissions"] }),
  });
}
export const useRefundQuote = (id: string, enabled: boolean) =>
  useQuery({ queryKey: ["admissions", "refund", id], queryFn: () => apiFetch<{ paid: number; percent: number; refundable: number; kept: number; days_before_start: number }>(`/admissions/applications/${id}/refund-quote`), enabled });
export const useEnquiries = (status: string) =>
  useQuery({ queryKey: ["admissions", "enquiries", status], queryFn: () => apiFetch<Enquiry[]>(`/admissions/enquiries${status ? `?status=${status}` : ""}`) });
export function useUpdateEnquiry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) => apiFetch<Enquiry>(`/admissions/enquiries/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admissions", "enquiries"] }),
  });
}
export const useSeatInfo = (cycleId: string, programmeId: string) =>
  useQuery({ queryKey: ["admissions", "rounds", cycleId, programmeId], queryFn: () => apiFetch<SeatInfo>(`/admissions/cycles/${cycleId}/rounds?programme_id=${programmeId}`), enabled: Boolean(cycleId && programmeId) });
export function useRound(cycleId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: { programme_id: string; accept_by: string; dry_run: boolean }) => post<RoundPreview>(`/admissions/cycles/${cycleId}/rounds`, b),
    onSuccess: (r) => {
      if (!r.dry_run) void qc.invalidateQueries({ queryKey: ["admissions"] });
    },
  });
}
export const useReport = (cycleId: string) =>
  useQuery({ queryKey: ["admissions", "report", cycleId], queryFn: () => apiFetch<Report>(`/admissions/cycles/${cycleId}/report`), enabled: Boolean(cycleId) });

export const STATUS_TONE: Record<string, "success" | "warning" | "danger" | "neutral" | "info"> = {
  submitted: "warning",
  returned: "danger",
  verified: "info",
  rejected: "neutral",
  offered: "success",
  waiting: "neutral",
  lapsed: "neutral",
  admitted: "success",
  cancelled: "neutral",
};

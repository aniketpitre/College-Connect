import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./api";
import type { StudentSummary } from "./students";

export interface FeeHead {
  id: string;
  code: string;
  name: string;
  status: "active" | "archived";
}
export interface Installment {
  label: string;
  due_date: string;
  amount: number;
}
export interface FeeStructure {
  id: string;
  academic_year_id: string;
  programme_id: string;
  year_of_study: number;
  category_id: string | null;
  name: string;
  items: { head_id: string; amount: number }[];
  installments: Installment[];
  late_fee: number;
  total: number;
  locked: boolean;
}
export interface LedgerEntry {
  id: string;
  at: string;
  type: string;
  label: string;
  amount: number;
  lines: { head: string; amount: number }[];
  reason: string | null;
  receipt_number: string | null;
  receipt_id: string | null;
  reverses: string | null;
  reversed: boolean;
}
export interface FeeAccount {
  student_id: string;
  academic_year_id: string;
  student?: StudentSummary;
  balance: number;
  demand: number;
  charges: number;
  paid: number;
  concessions: number;
  scholarships: number;
  refunds: number;
  overdue: number;
  late_fee: number;
  installments: (Installment & { paid: number; due: number; overdue: boolean })[];
  by_head: { head_id: string; code: string; name: string; outstanding: number }[];
  entries: LedgerEntry[];
  has_demand: boolean;
}
export interface DemandPlan {
  academic_year: string;
  class: string;
  students: { id: string; prn: string; name: string; outcome: "charge" | "already_charged" | "no_structure"; structure: string | null; amount: number }[];
  counts: Record<"charge" | "already_charged" | "no_structure", number>;
  total: number;
  dry_run: boolean;
}
export interface Approval {
  id: string;
  kind: "concession" | "receipt_cancel" | "refund";
  kind_label: string;
  status: "pending" | "approved" | "rejected";
  student_id: string;
  student_name: string | null;
  prn: string | null;
  amount: number;
  reason: string;
  details: Record<string, string | number | null>;
  requested_by: string | null;
  requested_by_id: string;
  requested_at: string;
  decided_by: string | null;
  decided_at: string | null;
  decision_reason: string | null;
}
export interface Scholarship {
  id: string;
  student_id: string;
  academic_year_id: string;
  scheme: string;
  reference: string;
  expected: number;
  sanctioned: number;
  received: number;
  status: "expected" | "sanctioned" | "received" | "rejected";
}

export const FEES_KEY = ["fees"] as const;
const post = <T>(path: string, body?: unknown, method = "POST") =>
  apiFetch<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });

function useFeesMutation<T, V>(fn: (v: V) => Promise<T>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: FEES_KEY });
      qc.invalidateQueries({ queryKey: ["approvals"] });
    },
  });
}

export const useFeeHeads = () => useQuery({ queryKey: [...FEES_KEY, "heads"], queryFn: () => apiFetch<FeeHead[]>("/fees/heads") });

export function useStructures(yearId?: string) {
  return useQuery({
    queryKey: [...FEES_KEY, "structures", yearId],
    queryFn: () => apiFetch<FeeStructure[]>(`/fees/structures?academic_year_id=${yearId}`),
    enabled: Boolean(yearId),
  });
}

export function useFeeAccount(studentId?: string, yearId?: string) {
  return useQuery({
    queryKey: [...FEES_KEY, "account", studentId, yearId],
    queryFn: () => apiFetch<FeeAccount>(`/fees/students/${studentId}${yearId ? `?academic_year_id=${yearId}` : ""}`),
    enabled: Boolean(studentId),
  });
}

export function useScholarships(studentId: string, yearId?: string) {
  return useQuery({
    queryKey: [...FEES_KEY, "scholarships", studentId, yearId],
    queryFn: () => apiFetch<Scholarship[]>(`/fees/scholarships?student_id=${studentId}${yearId ? `&academic_year_id=${yearId}` : ""}`),
  });
}

export function useApprovals(status: string, studentId?: string) {
  const params = new URLSearchParams({ status });
  if (studentId) params.set("student_id", studentId);
  return useQuery({ queryKey: ["approvals", status, studentId], queryFn: () => apiFetch<Approval[]>(`/approvals?${params}`) });
}

export const useCreateHead = () => useFeesMutation((b: { code: string; name: string }) => post<FeeHead>("/fees/heads", b));
export const useStarterHeads = () => useFeesMutation(() => post<{ created: number }>("/fees/heads/starter"));
export const useSaveStructure = () =>
  useFeesMutation(({ id, body }: { id?: string; body: Record<string, unknown> }) =>
    post<FeeStructure>(id ? `/fees/structures/${id}` : "/fees/structures", body, id ? "PUT" : "POST"),
  );
export const useGenerateDemands = () => useFeesMutation((b: Record<string, unknown>) => post<DemandPlan>("/fees/demands/generate", b));
export const useRequestConcession = () => useFeesMutation((b: Record<string, unknown>) => post<Approval>("/fees/concessions", b));
export const useAddCharge = () =>
  useFeesMutation(({ studentId, body }: { studentId: string; body: Record<string, unknown> }) => post<FeeAccount>(`/fees/students/${studentId}/charges`, body));
export const useApplyLateFees = () =>
  useFeesMutation(({ studentId, yearId }: { studentId: string; yearId: string }) => post<FeeAccount>(`/fees/students/${studentId}/late-fees?academic_year_id=${yearId}`));
export const useCreateScholarship = () => useFeesMutation((b: Record<string, unknown>) => post<Scholarship>("/fees/scholarships", b));
export const useScholarshipAction = () =>
  useFeesMutation(({ id, body }: { id: string; body: Record<string, unknown> }) => post<Scholarship>(`/fees/scholarships/${id}/actions`, body));
export const useDecide = () =>
  useFeesMutation(({ id, approve, reason }: { id: string; approve: boolean; reason?: string }) => post<Approval>(`/approvals/${id}/decide`, { approve, reason }));

export interface Receipt {
  id: string;
  number: string;
  academic_year: string;
  academic_year_id: string;
  student_id: string;
  student: { name: string; prn: string; class: string };
  amount: number;
  lines: { code: string; name: string; amount: number }[];
  mode: string;
  mode_label: string;
  reference: string;
  bank: string;
  instrument_date: string | null;
  note: string;
  collected_by: string;
  collected_at: string;
  status: "valid" | "cancelled";
  cancelled_at: string | null;
  cancel_reason: string | null;
  prints: number;
  verify_code: string;
}
export interface Today {
  date: string;
  total: number;
  count: number;
  cancelled: number;
  by_mode: { mode: string; label: string; amount: number }[];
  pending_approvals: number;
}

export const MODES: [string, string][] = [
  ["cash", "Cash"],
  ["upi", "UPI"],
  ["card", "Card"],
  ["cheque", "Cheque"],
  ["dd", "Demand draft"],
  ["bank_transfer", "Bank transfer"],
];

/** Opens in a new tab; the API marks every print after the first as DUPLICATE. */
export const receiptPdfUrl = (id: string) => `/api/v1/fees/receipts/${id}/pdf`;

export const useToday = () => useQuery({ queryKey: [...FEES_KEY, "today"], queryFn: () => apiFetch<Today>("/fees/today"), refetchInterval: 60_000 });

export function useReceipts(params: Record<string, string | undefined>) {
  const qs = new URLSearchParams(Object.entries(params).filter((e): e is [string, string] => Boolean(e[1])));
  return useQuery({ queryKey: [...FEES_KEY, "receipts", params], queryFn: () => apiFetch<Receipt[]>(`/fees/receipts?${qs}`) });
}

export const useCollect = () => useFeesMutation((b: Record<string, unknown>) => post<Receipt>("/fees/collect", b));
export const useEmailReceipt = () => useFeesMutation((id: string) => post<{ sent_to: string }>(`/fees/receipts/${id}/email`));

export const useCancelRequest = () =>
  useFeesMutation(({ receiptId, reason }: { receiptId: string; reason: string }) => post<Approval>(`/fees/receipts/${receiptId}/cancel-request`, { reason }));
export const useRefundRequest = () => useFeesMutation((b: Record<string, unknown>) => post<Approval>("/fees/refunds", b));

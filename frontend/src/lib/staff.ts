import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./api";

export interface Qualification {
  level: "ug" | "pg" | "mphil" | "phd" | "net" | "set" | "other";
  degree: string;
  university: string | null;
  year: number | null;
}
export interface StaffMember {
  user_id: string;
  name: string;
  email: string | null;
  roles: string[];
  status: string;
  department_id: string | null;
  department: string | null;
  has_record: boolean;
  employee_code: string | null;
  designation: string | null;
  employment: string | null;
  teaching: boolean;
  gender: "female" | "male" | "other" | null;
  social_category: "general" | "ews" | "sc" | "st" | "obc" | null;
  joined_on: string | null;
  experience_years: number;
  phone: string | null;
  qualifications: Qualification[];
  phd: boolean;
  net_set: boolean;
  appointment_order: string | null;
  appointment_date: string | null;
  university_approved: boolean;
  left_on: string | null;
}
export interface StaffSummary {
  staff: number;
  teaching: number;
  non_teaching: number;
  phd: number;
  net_set: number;
  by_employment: Record<string, number>;
  missing_records: number;
  by_department: { department: string; teachers: number; phd: number }[];
}
export interface Workload {
  date: string;
  staff: {
    user_id: string;
    name: string;
    department: string | null;
    designation: string | null;
    lectures: number;
    hours: number;
    subjects: number;
    divisions: number;
    leave_taken: number;
    on_leave_today: boolean;
  }[];
  on_leave_today: string[];
}
export interface LeaveType {
  code: string;
  name: string;
  days: number | null;
  half_day: boolean;
}
export interface Balance {
  code: string;
  name: string;
  half_day: boolean;
  allowance: number | null;
  taken: number;
  pending: number;
  available: number | null;
}
export interface LeaveRequest {
  id: string;
  user_id: string;
  name: string | null;
  code: string;
  type_name: string;
  from_date: string;
  to_date: string;
  half_day: boolean;
  days: number;
  reason: string;
  status: "pending" | "approved" | "rejected" | "cancelled";
  approver: "hod" | "principal" | "self";
  decided_by: string | null;
  decided_at: string | null;
  note: string | null;
  applied_at: string;
  balance?: Balance | null;
  lectures?: {
    date: string;
    start: string;
    end: string;
    subject: string | null;
    division: string | null;
    slot_id: string;
  }[];
}
export interface MyLeave {
  year: string;
  today: string;
  balances: Balance[];
  requests: LeaveRequest[];
  approver: "hod" | "principal" | "self";
  can_approve: boolean;
}

const send = <T>(path: string, body?: unknown, method = "POST") =>
  apiFetch<T>(path, {
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

function useAct<V, T = unknown>(fn: (v: V) => Promise<T>, keys: string[][]) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => keys.forEach((k) => void qc.invalidateQueries({ queryKey: k })),
  });
}

export const useStaffList = () =>
  useQuery({
    queryKey: ["staff", "list"],
    queryFn: () => apiFetch<StaffMember[]>("/staff"),
  });
export const useStaffSummary = () =>
  useQuery({
    queryKey: ["staff", "summary"],
    queryFn: () => apiFetch<StaffSummary>("/staff/summary"),
  });
export const useWorkload = (enabled: boolean) =>
  useQuery({
    queryKey: ["staff", "workload"],
    queryFn: () => apiFetch<Workload>("/staff/workload"),
    enabled,
  });
export const useSaveStaff = () => useAct((b: { id: string; body: Record<string, unknown> }) => send<StaffMember>(`/staff/${b.id}`, b.body, "PUT"), [["staff"]]);
export const useStaffBalances = (id: string | null) =>
  useQuery({
    queryKey: ["staff", "leave", id],
    queryFn: () => apiFetch<Balance[]>(`/staff/${id}/leave`),
    enabled: !!id,
  });

export const useLeaveTypes = () =>
  useQuery({
    queryKey: ["leave", "types"],
    queryFn: () => apiFetch<LeaveType[]>("/leave/settings"),
  });
export const useSaveLeaveTypes = () => useAct((types: LeaveType[]) => send<LeaveType[]>("/leave/settings", { types }, "PUT"), [["leave"], ["me", "leave"]]);
export const useAdjustLeave = () =>
  useAct(
    (b: { user_id: string; code: string; days: number; reason: string }) => send<Balance[]>("/leave/adjustments", b),
    [
      ["staff", "leave"],
      ["me", "leave"],
    ],
  );
export const useMyLeave = () =>
  useQuery({
    queryKey: ["me", "leave"],
    queryFn: () => apiFetch<MyLeave>("/me/leave"),
  });
export const useApplyLeave = () =>
  useAct((b: { code: string; from_date: string; to_date: string; half_day: boolean; reason: string }) => send<LeaveRequest>("/me/leave", b), [["me", "leave"]]);
export const useCancelLeave = () => useAct((id: string) => send<MyLeave>(`/me/leave/${id}/cancel`), [["me", "leave"]]);
export const useLeaveRequests = (status: string, enabled: boolean) =>
  useQuery({
    queryKey: ["leave", "requests", status],
    queryFn: () => apiFetch<LeaveRequest[]>(`/leave/requests?status=${status}`),
    enabled,
  });
export const useDecideLeave = () =>
  useAct(
    (b: { id: string; approve: boolean; note: string }) =>
      send<LeaveRequest>(`/leave/requests/${b.id}/decide`, {
        approve: b.approve,
        note: b.note || null,
      }),
    [["leave", "requests"], ["dashboard"], ["staff", "workload"]],
  );

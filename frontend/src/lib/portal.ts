import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./api";
import type { FeeAccount } from "./fees";

export interface HomeCard {
  kind:
    | "fee_overdue"
    | "fee_due_soon"
    | "document_rejected"
    | "correction_approved"
    | "correction_rejected"
    | "notice"
    | "attendance_low"
    | "attendance_warning"
    | "exam_form"
    | "hall_ticket"
    | "results"
    | "certificate_ready"
    | "deadline";
  severity: "danger" | "warning" | "info";
  amount?: number;
  since?: string;
  due_date?: string;
  label?: string;
  type?: string;
  reason?: string | null;
  fields?: string[];
  notice_id?: string;
  title?: string;
  hi?: { title: string } | null;
  mr?: { title: string } | null;
  code?: string;
  percent?: number;
  must_attend?: number;
  can_miss?: number;
  /** A deadline from a notice, in Hindi/Marathi when known. */
  what_hi?: string | null;
  what_mr?: string | null;
  days_left?: number;
}
export interface StudentHome {
  name: string;
  prn: string;
  class: string;
  academic_year: string | null;
  photo_url: string | null;
  balance: number | null;
  attendance?: number | null;
  cards: HomeCard[];
}
export interface MyFees extends Omit<FeeAccount, "student_id" | "student" | "late_fee"> {
  years: { id: string; name: string; is_current: boolean }[];
  /** The college has an online payment gateway set up. */
  online_payment?: boolean;
  receipts: { id: string; number: string; amount: number; mode_label: string; reference: string; collected_at: string; status: "valid" | "cancelled" }[];
}

export const useStudentHome = () => useQuery({ queryKey: ["me", "home"], queryFn: () => apiFetch<StudentHome>("/me/home") });

export function useMyFees(yearId?: string) {
  return useQuery({
    queryKey: ["me", "fees", yearId],
    queryFn: () => apiFetch<MyFees>(`/me/fees${yearId ? `?academic_year_id=${yearId}` : ""}`),
    retry: false,
  });
}

export const myReceiptPdf = (id: string) => `/api/v1/me/receipts/${id}/pdf`;
export const myStatementPdf = (yearId: string) => `/api/v1/me/fees/statement.pdf?academic_year_id=${yearId}`;

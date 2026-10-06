import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./api";

export interface PaymentOrder {
  id: string;
  order_id: string;
  key_id: string;
  amount: number;
  currency: string;
  name: string;
  description: string;
  prefill: { name: string; email: string; contact: string };
}

export interface OnlinePayment {
  id: string;
  purpose?: "fees" | "application";
  application_id?: string | null;
  student_id: string | null;
  student: { name: string; prn: string } | null;
  academic_year: string;
  amount: number;
  status: "created" | "paid" | "failed" | "expired" | "mismatch";
  status_label: string;
  order_id: string | null;
  gateway_payment_id: string | null;
  method: string | null;
  receipt_id: string | null;
  receipt_number: string | null;
  credit: number;
  paid_by: string | null;
  created_at: string;
  paid_at: string | null;
  settled_by: string | null;
  last_error: string | null;
}

interface RazorpayResponse {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
}
interface RazorpayInstance {
  open: () => void;
}
declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => RazorpayInstance;
  }
}

const CHECKOUT_JS = "https://checkout.razorpay.com/v1/checkout.js";

/** Razorpay Checkout is loaded only when someone pays, never on page load. */
function loadCheckout(): Promise<void> {
  if (window.Razorpay) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = CHECKOUT_JS;
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("Could not load the payment page. Check your connection."));
    document.body.appendChild(s);
  });
}

/** Opens Checkout for the order; resolves with the signed result, or null if the payer closed it. */
export async function checkout(order: PaymentOrder, color = "#14213d"): Promise<RazorpayResponse | null> {
  await loadCheckout();
  return new Promise((resolve) => {
    const rp = new window.Razorpay!({
      key: order.key_id,
      order_id: order.order_id,
      amount: order.amount,
      currency: order.currency,
      name: order.name,
      description: order.description,
      prefill: order.prefill,
      theme: { color },
      handler: (r: RazorpayResponse) => resolve(r),
      modal: { ondismiss: () => resolve(null) },
    });
    rp.open();
  });
}

export function usePayOnline() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { academic_year_id: string; amount: number }) => {
      const order = await apiFetch<PaymentOrder>("/me/payments", { method: "POST", body: JSON.stringify(body) });
      const result = await checkout(order);
      if (!result) return null;
      return apiFetch<OnlinePayment>(`/me/payments/${order.id}/confirm`, {
        method: "POST",
        body: JSON.stringify({ razorpay_payment_id: result.razorpay_payment_id, razorpay_signature: result.razorpay_signature }),
      });
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["me"] }),
  });
}

/** Accounts: a day's online payments. */
export interface PaymentDay {
  day: string;
  enabled: boolean;
  payments: OnlinePayment[];
  paid_count: number;
  paid_amount: number;
  waiting: number;
  problems: number;
}
export const useOnlinePayments = (day: string) =>
  useQuery({ queryKey: ["fees", "online", day], queryFn: () => apiFetch<PaymentDay>(`/fees/online-payments?day=${day}`) });

export function useCheckPayment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<OnlinePayment>(`/fees/online-payments/${id}/check`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["fees", "online"] }),
  });
}

export interface Reconciliation {
  rows: number;
  matched: number;
  matched_amount: number;
  amount_differs: (OnlinePayment & { gateway_amount: number })[];
  missing_in_collegeconnect: { gateway_payment_id: string; amount: number; payment: OnlinePayment | null }[];
  missing_in_gateway_file: OnlinePayment[];
}
export const useReconcile = () =>
  useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return apiFetch<Reconciliation>("/fees/online-payments/reconcile", { method: "POST", body: form });
    },
  });

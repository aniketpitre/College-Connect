import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./api";

const send = <T>(path: string, method: string, body?: unknown) =>
  apiFetch<T>(path, { method, body: body instanceof FormData ? body : body === undefined ? undefined : JSON.stringify(body) });

function useAct<V, T = unknown>(fn: (v: V) => Promise<T>, keys: string[][]) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => keys.forEach((k) => void qc.invalidateQueries({ queryKey: k })) });
}

// --- library ---
export interface Book {
  id: string;
  isbn: string | null;
  title: string;
  authors: string[];
  publisher: string;
  year: number | null;
  subject: string;
  copies: number;
  available: number;
  waiting: number;
  copy_list?: { barcode: string; status: string }[];
}
export interface Loan {
  id: string;
  book_id: string;
  title: string;
  authors: string[];
  barcode: string;
  issued_on: string;
  due_date: string;
  returned_on: string | null;
  status: "open" | "returned" | "lost";
  days_late: number;
  fine_so_far: number;
  fine: number;
  renewals: number;
  student?: { id: string; name: string; prn: string };
  held_for_reservation?: boolean;
}
export interface MyLibrary {
  rules: { loan_days: number; max_books: number; fine_per_day: number; max_renewals: number };
  loans: Loan[];
  history: Loan[];
  reservations: { id: string; book_id: string; title: string; status: "waiting" | "ready"; ready_until: string | null; position: number }[];
}
export interface LibraryOverview {
  titles: number;
  copies: number;
  issued: number;
  overdue: number;
  reservations: number;
  settings: { loan_days: number; max_books: number; fine_per_day: number; max_renewals: number; hold_days: number };
}

export const useBooks = (q: string) => useQuery({ queryKey: ["library", "books", q], queryFn: () => apiFetch<Book[]>(`/library/books?q=${encodeURIComponent(q)}`) });
export const useMyLibrary = () => useQuery({ queryKey: ["me", "library"], queryFn: () => apiFetch<MyLibrary>("/me/library") });
export const useReserve = () => useAct((bookId: string) => send("/me/library/reservations", "POST", { book_id: bookId }), [["me", "library"], ["library"]]);
export const useCancelReservation = () => useAct((id: string) => send(`/me/library/reservations/${id}`, "DELETE"), [["me", "library"]]);
export const useRenewMine = () => useAct((id: string) => send(`/me/library/loans/${id}/renew`, "POST"), [["me", "library"]]);
export const useLibraryOverview = () => useQuery({ queryKey: ["library", "overview"], queryFn: () => apiFetch<LibraryOverview>("/library/overview") });
export const useLoans = (status: string, q: string) =>
  useQuery({ queryKey: ["library", "loans", status, q], queryFn: () => apiFetch<Loan[]>(`/library/loans?status=${status}${q ? `&q=${encodeURIComponent(q)}` : ""}`) });
export const useIssue = () => useAct((b: { barcode: string; prn: string }) => send<Loan>("/library/issue", "POST", b), [["library"]]);
export const useReturn = () => useAct((barcode: string) => send<Loan>("/library/return", "POST", { barcode }), [["library"]]);
export const useAddBook = () => useAct((b: Record<string, unknown>) => send<Book>("/library/books", "POST", b), [["library"]]);
export const useLost = () => useAct((b: { id: string; price: number }) => send<Loan>(`/library/loans/${b.id}/lost`, "POST", { price: b.price }), [["library"]]);
export const isbnLookup = (isbn: string) => apiFetch<{ found: boolean; title?: string; authors?: string[]; publisher?: string; year?: number; subject?: string }>(`/library/isbn/${encodeURIComponent(isbn)}`);

// --- hostel ---
export interface Outpass {
  id: string;
  leave_at: string;
  return_by: string;
  destination: string;
  reason: string;
  status: "requested" | "approved" | "rejected" | "out" | "returned" | "cancelled";
  decision_reason: string | null;
  out_at: string | null;
  returned_at: string | null;
  late: boolean;
  created_at: string;
  student?: { id: string; name: string; prn: string };
}
export interface Complaint {
  id: string;
  category: string;
  text: string;
  status: "open" | "in_progress" | "resolved";
  room: string | null;
  notes: { at: string; text: string }[];
  created_at: string;
  student?: { name: string; prn: string };
}
export interface MyHostel {
  resident: boolean;
  allotment: { block: string; room: string; bed: number; since: string; annual_fee: string } | null;
  outpasses: Outpass[];
  complaints: Complaint[];
  mess_menu: Record<string, string> | null;
}
export interface HostelOverview {
  blocks: {
    id: string;
    name: string;
    gender: string;
    annual_fee: number;
    beds: number;
    occupied: number;
    rooms: { id: string; number: string; beds: number; occupants: { allotment_id: string; bed: number; name: string; prn: string; student_id: string }[] }[];
  }[];
  pending_outpasses: number;
  out_now: number;
  overdue_returns: number;
  open_complaints: number;
}
export const useMyHostel = () => useQuery({ queryKey: ["me", "hostel"], queryFn: () => apiFetch<MyHostel>("/me/hostel") });
export const useAskOutpass = () => useAct((b: Record<string, string>) => send("/me/hostel/outpasses", "POST", b), [["me", "hostel"]]);
export const useComplain = () => useAct((b: { category: string; text: string }) => send("/me/hostel/complaints", "POST", b), [["me", "hostel"]]);
export const useHostel = () => useQuery({ queryKey: ["hostel", "overview"], queryFn: () => apiFetch<HostelOverview>("/hostel") });
export const useOutpasses = (status: string) => useQuery({ queryKey: ["hostel", "outpasses", status], queryFn: () => apiFetch<Outpass[]>(`/hostel/outpasses?status=${status}`) });
export const useOutpassAction = () => useAct((b: { id: string; action: string; reason?: string }) => send(`/hostel/outpasses/${b.id}/action`, "POST", { action: b.action, reason: b.reason }), [["hostel"]]);
export const useComplaints = () => useQuery({ queryKey: ["hostel", "complaints"], queryFn: () => apiFetch<Complaint[]>("/hostel/complaints") });
export const useUpdateComplaint = () => useAct((b: { id: string; status: string; note?: string }) => send(`/hostel/complaints/${b.id}`, "PATCH", { status: b.status, note: b.note ?? "" }), [["hostel"]]);
export const useHostelAdmin = () =>
  useAct((b: { path: string; method?: string; body: unknown }) => send(`/hostel${b.path}`, b.method ?? "POST", b.body), [["hostel"]]);

// --- placement ---
export interface Drive {
  id: string;
  company: string;
  role: string;
  ctc_lpa: number;
  location: string;
  description: string;
  register_by: string;
  drive_date: string | null;
  rounds: string[];
  status: "open" | "closed" | "completed";
  open_now: boolean;
  eligibility: { programme_ids: string[]; programmes: string[]; years: number[]; min_cgpa: number | null; max_backlogs: number | null };
  counts?: Record<string, number>;
  eligible?: boolean;
  reasons?: string[];
  registration?: { id: string; status: string; stage: string; offer_lpa: number | null } | null;
}
export interface MyPlacement {
  profile: { skills: string; linkedin: string; resume_name: string | null; resume_url: string | null };
  cgpa: number | null;
  backlogs: number;
  drives: Drive[];
}
export interface Registration {
  id: string;
  student_id: string;
  name: string;
  prn: string;
  class: string;
  email: string | null;
  phone: string | null;
  cgpa: number | null;
  backlogs: number;
  status: string;
  round: number;
  stage: string;
  offer_lpa: number | null;
  has_resume: boolean;
}
export interface PlacementStats {
  drives: number;
  companies: number;
  offers: number;
  students_placed: number;
  registered_students: number;
  highest_lpa: number | null;
  average_lpa: number | null;
  median_lpa: number | null;
  by_programme: Record<string, number>;
}
export const useMyPlacement = () => useQuery({ queryKey: ["me", "placement"], queryFn: () => apiFetch<MyPlacement>("/me/placement") });
export const usePlacementMine = () =>
  useAct((b: { path: string; method?: string; body?: unknown }) => send<MyPlacement>(`/me/placement${b.path}`, b.method ?? "POST", b.body), [["me", "placement"]]);
export const useDrives = () => useQuery({ queryKey: ["placement", "drives"], queryFn: () => apiFetch<Drive[]>("/placement/drives") });
export const useRegistrations = (driveId: string) =>
  useQuery({ queryKey: ["placement", "regs", driveId], queryFn: () => apiFetch<{ drive: Drive; registrations: Registration[] }>(`/placement/drives/${driveId}/registrations`), enabled: Boolean(driveId) });
export const useSaveDrive = () => useAct((b: { id?: string; body: unknown }) => send<Drive>(b.id ? `/placement/drives/${b.id}` : "/placement/drives", b.id ? "PUT" : "POST", b.body), [["placement"]]);
export const useDriveResults = (driveId: string) =>
  useAct((b: { registration_ids: string[]; action: string; ctc_lpa?: number }) => send(`/placement/drives/${driveId}/results`, "POST", b), [["placement"]]);
export const usePlacementStats = () => useQuery({ queryKey: ["placement", "stats"], queryFn: () => apiFetch<PlacementStats>("/placement/stats") });

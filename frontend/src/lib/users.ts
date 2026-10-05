import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./api";

export interface User {
  id: string;
  kind: "staff" | "student" | "parent";
  name: string;
  email: string | null;
  prn: string | null;
  phone: string | null;
  roles: string[];
  department_id: string | null;
  role_labels: string[];
  status: "active" | "disabled";
  must_change_password: boolean;
  mfa_enabled: boolean;
  mfa_required: boolean;
  locked: boolean;
  last_login_at: string | null;
  created_at: string | null;
}

export interface RoleInfo {
  id: string;
  label: string;
  mfa_required: boolean;
}

export interface NewUser {
  kind: "staff" | "student";
  name: string;
  email?: string;
  prn?: string;
  phone?: string;
  roles: string[];
  department_id?: string;
}

export interface UserChanges {
  name?: string;
  email?: string;
  phone?: string;
  roles?: string[];
  department_id?: string;
  status?: "active" | "disabled";
  reason?: string;
}

const USERS = ["users"] as const;

export function useUsers(kind?: string) {
  return useQuery({
    queryKey: [...USERS, kind ?? "all"],
    queryFn: () => apiFetch<{ items: User[]; total: number }>(`/users?limit=200${kind ? `&kind=${kind}` : ""}`),
  });
}

export function useRoles() {
  return useQuery({ queryKey: ["users", "roles"], queryFn: () => apiFetch<RoleInfo[]>("/users/roles"), staleTime: Infinity });
}

function useInvalidate() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: USERS });
}

export function useCreateUser() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: NewUser) =>
      apiFetch<{ user: User; temporary_password: string }>("/users", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: invalidate,
  });
}

export function useUpdateUser() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, changes }: { id: string; changes: UserChanges }) =>
      apiFetch<User>(`/users/${id}`, { method: "PATCH", body: JSON.stringify(changes) }),
    onSuccess: invalidate,
  });
}

export function useResetPassword() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      apiFetch<{ temporary_password: string }>(`/users/${id}/reset-password`, { method: "POST", body: JSON.stringify({ reason }) }),
    onSuccess: invalidate,
  });
}

export function useUnlockUser() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiFetch<User>(`/users/${id}/unlock`, { method: "POST" }),
    onSuccess: invalidate,
  });
}

export function useResetTwoStep() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      apiFetch<User>(`/users/${id}/reset-2-step`, { method: "POST", body: JSON.stringify({ reason }) }),
    onSuccess: invalidate,
  });
}

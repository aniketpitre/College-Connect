import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { apiFetch } from "./api";
import { ME_KEY, type Me } from "./auth";
import { setChild } from "./child";
import { chooseLanguage } from "./language";

export type Area = "fees" | "attendance" | "results";
export type Access = Record<Area, boolean>;

export interface Child {
  id: string;
  name: string;
  prn: string;
  class: string;
  status: string;
  relation: string | null;
  photo_url: string | null;
  access: Access;
}

export const useChildren = (enabled: boolean) =>
  useQuery({ queryKey: ["parent", "children"], queryFn: () => apiFetch<Child[]>("/parent/children"), enabled });

/** Switching child: drop everything cached about the previous one. */
export function useSwitchChild() {
  const qc = useQueryClient();
  return useCallback(
    (id: string) => {
      setChild(id);
      qc.removeQueries({ predicate: (q) => q.queryKey[0] !== "auth" && q.queryKey[0] !== "parent" });
    },
    [qc],
  );
}

export const useRequestCode = () =>
  useMutation({ mutationFn: (phone: string) => apiFetch<{ sent: boolean }>("/auth/otp/request", { method: "POST", body: JSON.stringify({ phone }) }) });

export function useVerifyCode() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { phone: string; code: string }) => apiFetch<Me>("/auth/otp/verify", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: (me) => {
      if (me.language) chooseLanguage(me.language);
      qc.setQueryData(ME_KEY, me);
    },
  });
}

/** Students: what their parents can see. */
export interface Sharing {
  can_change: boolean;
  access: Access;
  parents: { name: string; relation: string | null }[];
}
export const useSharing = () => useQuery({ queryKey: ["me", "parent-access"], queryFn: () => apiFetch<Sharing>("/me/parent-access") });
export function useSetSharing() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (access: Access) => apiFetch<Sharing>("/me/parent-access", { method: "PUT", body: JSON.stringify(access) }),
    onSuccess: (data) => qc.setQueryData(["me", "parent-access"], data),
  });
}

/** Office: a student's linked parents. */
export interface LinkedParents {
  parents: { id: string; name: string; phone: string | null; email: string | null; relation: string | null; status: string; last_login_at: string | null; children: number }[];
  minor: boolean;
  consent_recorded: boolean;
  access: Access;
}
export const useStudentParents = (studentId: string) =>
  useQuery({ queryKey: ["students", studentId, "parents"], queryFn: () => apiFetch<LinkedParents>(`/students/${studentId}/parents`) });
export function useLinkParent(studentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; phone: string; email?: string; relation: string; consent: boolean }) =>
      apiFetch<LinkedParents>(`/students/${studentId}/parents`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: (data) => qc.setQueryData(["students", studentId, "parents"], data),
  });
}
export function useUnlinkParent(studentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (parentId: string) => apiFetch<LinkedParents>(`/students/${studentId}/parents/${parentId}`, { method: "DELETE" }),
    onSuccess: (data) => qc.setQueryData(["students", studentId, "parents"], data),
  });
}

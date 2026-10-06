import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./api";

export interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  scopes: string[];
  created_at: string;
  expires_at: string;
  last_used_at: string | null;
  calls: number;
  state: "active" | "revoked" | "expired";
}

export const useApiKeys = () => useQuery({ queryKey: ["api-keys"], queryFn: () => apiFetch<{ keys: ApiKey[]; scopes: Record<string, string> }>("/api-keys") });
export function useCreateKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: { name: string; scopes: string[]; valid_days: number }) =>
      apiFetch<ApiKey & { key: string }>("/api-keys", { method: "POST", body: JSON.stringify(b) }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["api-keys"] }),
  });
}
export function useRevokeKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<ApiKey>(`/api-keys/${id}/revoke`, { method: "POST" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["api-keys"] }),
  });
}

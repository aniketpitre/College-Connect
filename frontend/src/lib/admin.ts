import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, API_V1 } from "./api";

export interface AuditRow {
  id: string;
  at: string;
  action: string;
  actor: string | null;
  actor_id: string | null;
  target_type: string | null;
  target_id: string | null;
  target: string | null;
  ip: string | null;
  reason: string | null;
  details: Record<string, unknown>;
}

export interface AuditPage {
  rows: AuditRow[];
  next_before: string | null;
  areas: Record<string, string>;
}

export interface AuditFilters {
  area?: string;
  actor?: string;
  from?: string;
  to?: string;
}

export function useAudit(filters: AuditFilters) {
  return useInfiniteQuery({
    queryKey: ["audit", filters],
    initialPageParam: "",
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams();
      for (const [k, v] of Object.entries(filters)) if (v) params.set(k, v);
      if (pageParam) params.set("before", pageParam);
      return apiFetch<AuditPage>(`/audit?${params}`);
    },
    getNextPageParam: (last) => last.next_before ?? undefined,
  });
}

export interface ExportRequest {
  id: string;
  dataset: string;
  dataset_label: string;
  reason: string;
  status: "pending" | "approved" | "rejected";
  requested_by: string | null;
  requested_by_id: string;
  requested_at: string;
  decided_by: string | null;
  decided_at: string | null;
  decision_reason: string | null;
  expires_at: string | null;
  downloadable: boolean;
  downloads: number;
}

export function useExports() {
  return useQuery({
    queryKey: ["exports"],
    queryFn: () => apiFetch<{ datasets: Record<string, string>; requests: ExportRequest[] }>("/export/requests"),
  });
}

export function useRequestExport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { dataset: string; reason: string }) =>
      apiFetch<ExportRequest>("/export/requests", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["exports"] }),
  });
}

export function useDecideExport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; approve: boolean; reason?: string }) =>
      apiFetch<ExportRequest>(`/export/requests/${id}/decide`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["exports"] }),
  });
}

export const exportDownloadUrl = (id: string) => `${API_V1}/export/requests/${id}/download`;

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

export interface FullManifest {
  collections: { collection: string; count: number; description: string; fields: { name: string; types: string[] }[] }[];
  dictionary_md: string;
}

/** Builds the full export in the browser: the manifest, then each collection page by page (each
 * response stays small for the free hosting tier), saved as one ZIP. */
export async function downloadFullExport(id: string, onProgress: (done: number, total: number, name: string) => void): Promise<Blob> {
  const { makeZip } = await import("./zip");
  const manifest = await apiFetch<FullManifest>(`/export/requests/${id}/full`);
  const enc = new TextEncoder();
  const files = [
    { name: "manifest.json", data: enc.encode(JSON.stringify({ exported_at: new Date().toISOString(), collections: manifest.collections }, null, 2)) },
    { name: "data-dictionary.md", data: enc.encode(manifest.dictionary_md) },
  ];
  let done = 0;
  for (const c of manifest.collections) {
    onProgress(done, manifest.collections.length, c.collection);
    const chunks: string[] = [];
    let after: string | null = null;
    do {
      const url: string = `${API_V1}/export/requests/${id}/full/${c.collection}${after ? `?after=${encodeURIComponent(after)}` : ""}`;
      const res = await fetch(url, { credentials: "include", headers: { "X-Requested-With": "XMLHttpRequest" } });
      if (!res.ok) throw new Error(`Could not read ${c.collection} (${res.status}). Try again.`);
      chunks.push(await res.text());
      after = res.headers.get("X-Next-After");
    } while (after);
    files.push({ name: `collections/${c.collection}.jsonl`, data: enc.encode(chunks.join("")) });
    done += 1;
  }
  onProgress(done, manifest.collections.length, "");
  return makeZip(files);
}

export const fullExportName = () => `collegeconnect-full-${new Date().toISOString().slice(0, 10)}.zip`;

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./api";

export type Channel = "email" | "sms" | "whatsapp";
export interface MyChannels {
  channels: { channel: Channel; label: string; on: boolean; available: boolean; to: string | null }[];
}
export const useMyChannels = () => useQuery({ queryKey: ["me", "notifications"], queryFn: () => apiFetch<MyChannels>("/me/notifications") });
export function useSetChannels() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (values: Record<Channel, boolean>) => apiFetch<MyChannels>("/me/notifications", { method: "PUT", body: JSON.stringify(values) }),
    onSuccess: (data) => qc.setQueryData(["me", "notifications"], data),
  });
}

export interface MessageLog {
  available: Record<Channel, boolean>;
  waiting: number;
  templates: Record<string, string>;
  messages: { at: string; to_name: string; to: string; template: string; template_label: string; channel: Channel; status: "sent" | "failed"; error: string | null; student_id: string | null }[];
}
export const useMessageLog = (filters: { template?: string; status?: string }) => {
  const params = new URLSearchParams(Object.entries(filters).filter(([, v]) => v) as [string, string][]);
  return useQuery({ queryKey: ["messages", "log", filters], queryFn: () => apiFetch<MessageLog>(`/messages/log?${params}`) });
};

/** Sends the queue in short rounds (each server call stops after a few seconds) until it is empty. */
export function useRunQueue() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      let total = 0;
      for (let round = 0; round < 20; round++) {
        const r = await apiFetch<{ processed: number; sent: number; waiting: number }>("/messages/queue/run", { method: "POST" });
        total += r.sent;
        if (r.waiting === 0 || r.processed === 0) break;
      }
      return total;
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["messages"] }),
  });
}

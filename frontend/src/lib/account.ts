import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./api";
import { ME_KEY, type Me } from "./auth";

export interface MfaStatus {
  enabled: boolean;
  required: boolean;
  recovery_codes_left: number;
  enabled_at: string | null;
}

export interface MfaSetup {
  secret: string;
  otpauth_uri: string;
  qr_svg: string;
}

export interface DeviceSession {
  id: string;
  current: boolean;
  created_at: string;
  last_seen_at: string;
  ip: string | null;
  user_agent: string | null;
}

export interface LoginEvent {
  at: string;
  action: string;
  ip: string | null;
  reason: string | null;
}

const MFA_KEY = ["auth", "mfa"] as const;
const SESSIONS_KEY = ["auth", "sessions"] as const;

const post = <T>(path: string, body?: unknown) =>
  apiFetch<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export function useMfaStatus() {
  return useQuery({ queryKey: MFA_KEY, queryFn: () => apiFetch<MfaStatus>("/auth/mfa") });
}

export function useStartMfaSetup() {
  return useMutation({ mutationFn: () => post<MfaSetup>("/auth/mfa/setup") });
}

export function useEnableMfa() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (code: string) => post<{ recovery_codes: string[]; me: Me }>("/auth/mfa/enable", { code }),
    onSuccess: (r) => {
      qc.setQueryData(ME_KEY, r.me);
      qc.invalidateQueries({ queryKey: MFA_KEY });
      qc.invalidateQueries({ queryKey: SESSIONS_KEY });
    },
  });
}

export function useVerifyMfa() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (code: string) => post<Me & { recovery_codes_left: number }>("/auth/mfa/verify", { code }),
    onSuccess: (me) => qc.setQueryData(ME_KEY, me),
  });
}

export function useDisableMfa() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (password: string) => post<Me>("/auth/mfa/disable", { password }),
    onSuccess: (me) => {
      qc.setQueryData(ME_KEY, me);
      qc.invalidateQueries({ queryKey: MFA_KEY });
    },
  });
}

export function useNewRecoveryCodes() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (password: string) => post<{ recovery_codes: string[] }>("/auth/mfa/recovery-codes", { password }),
    onSuccess: () => qc.invalidateQueries({ queryKey: MFA_KEY }),
  });
}

export function useForgotPassword() {
  return useMutation({ mutationFn: (identifier: string) => post<{ ok: true }>("/auth/password/forgot", { identifier }) });
}

export function useCompleteReset() {
  return useMutation({
    mutationFn: (body: { token: string; new_password: string }) => post<{ ok: true }>("/auth/password/reset", body),
  });
}

export function useSessions() {
  return useQuery({ queryKey: SESSIONS_KEY, queryFn: () => apiFetch<DeviceSession[]>("/auth/sessions") });
}

export function useEndSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sid: string) => apiFetch<void>(`/auth/sessions/${encodeURIComponent(sid)}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: SESSIONS_KEY }),
  });
}

export function useLogoutEverywhere() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => post<{ signed_out_sessions: number }>("/auth/logout-all"),
    onSettled: () => {
      qc.clear();
      qc.setQueryData(ME_KEY, null);
    },
  });
}

export function useLoginHistory() {
  return useQuery({ queryKey: ["auth", "history"], queryFn: () => apiFetch<LoginEvent[]>("/auth/login-history") });
}

/** "Chrome on Android" from a user-agent string (product names stay in English). */
export function describeDevice(ua: string | null): string | null {
  if (!ua) return null;
  const browser = /Edg\//.test(ua)
    ? "Edge"
    : /Firefox\//.test(ua)
      ? "Firefox"
      : /Chrome\//.test(ua)
        ? "Chrome"
        : /Safari\//.test(ua)
          ? "Safari"
          : null;
  const os = /Android/.test(ua)
    ? "Android"
    : /iPhone|iPad/.test(ua)
      ? "iPhone/iPad"
      : /Windows/.test(ua)
        ? "Windows"
        : /Mac OS X/.test(ua)
          ? "Mac"
          : /Linux/.test(ua)
            ? "Linux"
            : null;
  if (browser && os) return `${browser} · ${os}`;
  return browser ?? os;
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "./api";
import { chooseLanguage } from "./language";
import * as offline from "./offline";
import type { Language } from "./types";

export type SessionState = "active" | "mfa_pending" | "mfa_setup";

export interface Me {
  id: string;
  kind: "staff" | "student" | "parent";
  name: string;
  email: string | null;
  prn: string | null;
  roles: string[];
  role_labels: string[];
  permissions: string[];
  must_change_password: boolean;
  mfa_enabled: boolean;
  mfa_required: boolean;
  session_state: SessionState;
  language?: Language | null;
  onboarding_required?: boolean;
  /** A student who has left (TC issued): can read and download, not change. */
  read_only?: boolean;
}

export const ME_KEY = ["auth", "me"] as const;

/** The signed-in user, or null when signed out. */
export function useMe() {
  return useQuery({
    queryKey: ME_KEY,
    queryFn: async () => {
      try {
        const me = await apiFetch<Me>("/auth/me");
        // Teachers can open the app without a connection (offline attendance): keep who is signed in.
        if (me.permissions.includes("attendance.take") && me.session_state === "active") await offline.put("cache", "me", me);
        return me;
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) {
          void offline.clearCache(); // not awaited: a slower answer here must not overwrite a sign-in that just happened
          return null;
        }
        if (e instanceof ApiError && e.code === "network_error") {
          const saved = await offline.get<Me>("cache", "me");
          if (saved) return saved;
        }
        throw e;
      }
    },
    staleTime: 60_000,
    retry: false,
  });
}

export function hasPermission(me: Me | null | undefined, permission: string): boolean {
  return Boolean(me?.permissions.includes(permission));
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { identifier: string; password: string }) =>
      apiFetch<Me>("/auth/login", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: (me) => {
      if (me.language) chooseLanguage(me.language); // the language saved on the account follows the user
      qc.setQueryData(ME_KEY, me);
    },
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<void>("/auth/logout", { method: "POST" }),
    onSettled: () => {
      qc.clear();
      qc.setQueryData(ME_KEY, null);
      // Class lists and the user kept for offline use leave the phone with the user.
      void offline.clearCache();
    },
  });
}

export function useChangePassword() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { current_password: string; new_password: string }) =>
      apiFetch<Me>("/auth/password/change", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: (me) => qc.setQueryData(ME_KEY, me),
  });
}

/** Where a signed-in user must go before anything else, or null if nowhere. */
export function pendingStep(me: Me): string | null {
  if (me.session_state === "mfa_pending" || me.session_state === "mfa_setup") return "/login/2-step";
  if (me.must_change_password) return "/app/change-password";
  if (me.onboarding_required) return "/app/welcome";
  return null;
}

/** Only same-site paths are allowed as a post-login destination. */
export function safeNext(next: string | null): string | null {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : null;
}

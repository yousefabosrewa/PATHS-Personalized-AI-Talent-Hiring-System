"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "@/types";
import { loginApi } from "@/lib/api/auth.api";

/** The user id currently persisted in `paths-auth` (or "anon"). */
function currentSessionUserId(): string {
  if (typeof window === "undefined") return "anon";
  try {
    const raw = localStorage.getItem("paths-auth");
    if (!raw) return "anon";
    const parsed = JSON.parse(raw) as { state?: { user?: { id?: string } | null } };
    return parsed?.state?.user?.id ?? "anon";
  } catch {
    return "anon";
  }
}

/**
 * Re-sync the onboarding draft with the user now in session. Drafts are
 * namespaced by user id so distinct users never share an in-progress profile.
 *
 * Critically: ``persist.rehydrate()`` is a no-op when the new user has NOTHING
 * stored — it leaves whatever draft is currently in memory untouched. That let
 * a previous (or abandoned) session's draft leak into a brand-new sign-up
 * (pre-filled basic info / contact / phantom CV). So when the new session has
 * no stored draft we explicitly ``reset()`` instead; only when a saved draft
 * exists do we rehydrate it (so a returning candidate resumes where they left).
 */
function syncOnboardingDraftWithSession() {
  queueMicrotask(() => {
    void import("@/lib/stores/onboarding.store").then(({ useOnboardingStore }) => {
      const key = `paths-onboarding-draft::${currentSessionUserId()}`;
      const hasStoredDraft =
        typeof window !== "undefined" && localStorage.getItem(key) != null;
      if (hasStoredDraft) {
        void useOnboardingStore.persist.rehydrate();
      } else {
        useOnboardingStore.getState().reset();
      }
    });
  });
}

/**
 * Mirror the session into a non-sensitive cookie that Next.js middleware can
 * read at the edge. The cookie does NOT carry the JWT — only a presence flag
 * (`paths-session=1`). All authoritative checks still run server-side via
 * /api/v1/* on the backend.
 */
function setSessionCookie(present: boolean) {
  if (typeof document === "undefined") return;
  if (present) {
    document.cookie = "paths-session=1; Path=/; SameSite=Lax; Max-Age=86400";
  } else {
    document.cookie = "paths-session=; Path=/; SameSite=Lax; Max-Age=0";
  }
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  _hasHydrated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  setUser: (user: User) => void;
  setHasHydrated: (v: boolean) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      _hasHydrated: false,

      // Real-backend login. There is intentionally NO demo fallback path:
      // a previous NEXT_PUBLIC_ALLOW_DEMO_LOGIN code path used to grant a
      // hardcoded `admin` user when the backend rejected the credentials,
      // which is a privilege-escalation footgun. It was removed during the
      // platform-admin rollout.
      login: async (email: string, password: string) => {
        set({ isLoading: true });

        const apiUrl = process.env.NEXT_PUBLIC_API_URL;
        if (!apiUrl) {
          set({ isLoading: false });
          throw new Error(
            "NEXT_PUBLIC_API_URL is not set. Configure the API base URL to sign in.",
          );
        }

        try {
          const { user, token } = await loginApi(email, password);
          set({
            user: user as unknown as User,
            token,
            isAuthenticated: true,
            isLoading: false,
          });
          setSessionCookie(true);
          syncOnboardingDraftWithSession();
        } catch (err) {
          set({ isLoading: false });
          throw err;
        }
      },

      logout: () => {
        set({ user: null, token: null, isAuthenticated: false });
        setSessionCookie(false);
      },

      setUser: (user) => set({ user, isAuthenticated: true }),
      setHasHydrated: (v) => set({ _hasHydrated: v }),
    }),
    {
      name: "paths-auth",
      partialize: (s) => ({
        user: s.user,
        token: s.token,
        isAuthenticated: s.isAuthenticated,
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
        // Re-sync the cookie based on what rehydrated from localStorage.
        if (typeof document !== "undefined") {
          setSessionCookie(!!state?.isAuthenticated);
        }
      },
    },
  ),
);

/**
 * PATHS — Candidate Session Store
 *
 * Holds the logged-in candidate's profile for use across the candidate portal.
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { CandidateProfile } from "@/types/candidate-profile.types";

interface CandidateSessionState {
  profile: CandidateProfile | null;
  isLoading: boolean;
  _hasHydrated: boolean;

  setProfile: (profile: CandidateProfile | null) => void;
  setLoading: (loading: boolean) => void;
  setHasHydrated: (v: boolean) => void;
  logout: () => void;
}

export const useCandidateStore = create<CandidateSessionState>()(
  persist(
    (set) => ({
      profile: null,
      isLoading: false,
      _hasHydrated: false,

      setProfile: (profile) => set({ profile }),
      setLoading: (isLoading) => set({ isLoading }),
      setHasHydrated: (v) => set({ _hasHydrated: v }),
      logout: () => set({ profile: null }),
    }),
    {
      name: "paths-candidate-session",
      storage: createJSONStorage(() => {
        if (typeof window === "undefined") {
          return { getItem: () => null, setItem: () => {}, removeItem: () => {} };
        }
        return localStorage;
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
    }
  )
);

/**
 * PATHS — Candidate Onboarding Zustand Store
 *
 * Persists draft per logged-in user so drafts are not shared across accounts.
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type {
  OnboardingState,
  OnboardingStep,
  OnboardingDraft,
} from "@/types/candidate-profile.types";
import { candidatePortalLegacyApi } from "@/lib/api/candidate-portal.api";

// ── Initial draft ─────────────────────────────────────────────────────────────

const initialDraft: OnboardingDraft = {
  fullName: "",
  currentTitle: "",
  summary: "",
  careerLevel: "mid",
  yearsExperience: 0,
  email: "",
  otherEmails: [],
  phone: "",
  locationText: "",
  education: [],
  experiences: [],
  skills: [],
  documents: [],
  links: {},
  preferences: {
    desiredRoles: [],
    jobTypes: [],
    workplaceTypes: [],
    preferredLocations: [],
    openToRelocation: false,
    salaryCurrency: "USD",
  },
  onboardingCompleted: false,
};

function readAuthUserId(): string {
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

const userScopedStorage = createJSONStorage(() => ({
  getItem: (name) => localStorage.getItem(`${name}::${readAuthUserId()}`),
  setItem: (name, value) => localStorage.setItem(`${name}::${readAuthUserId()}`, value),
  removeItem: (name) => localStorage.removeItem(`${name}::${readAuthUserId()}`),
}));

// ── Store ─────────────────────────────────────────────────────────────────────

export const useOnboardingStore = create<OnboardingState>()(
  persist(
    (set, get) => ({
      draft: { ...initialDraft },
      currentStep: "basic-info",
      completedSteps: new Set<OnboardingStep>(),
      isSubmitting: false,
      lastSavedAt: null,
      postOnboardingRedirect: null,

      setStep: (step) => set({ currentStep: step }),

      markStepComplete: (step) =>
        set((s) => ({
          completedSteps: new Set([...s.completedSteps, step]),
        })),

      updateDraft: (patch) =>
        set((s) => ({
          draft: { ...s.draft, ...patch },
        })),

      saveDraft: async () => {
        set({ lastSavedAt: new Date().toISOString() });
      },

      setPostOnboardingRedirect: (url) => set({ postOnboardingRedirect: url }),

      submitProfile: async () => {
        set({ isSubmitting: true });
        try {
          const { draft } = get();
          const apiUrl = process.env.NEXT_PUBLIC_API_URL;
          if (!apiUrl) {
            set({ isSubmitting: false });
            throw new Error("API not configured");
          }
          const updated = await candidatePortalLegacyApi.updateProfileFromDraft(draft);
          set({
            isSubmitting: false,
            draft: { ...initialDraft },
            currentStep: "basic-info",
            completedSteps: new Set(),
            lastSavedAt: null,
          });
          return updated.id;
        } catch (e) {
          set({ isSubmitting: false });
          throw e instanceof Error ? e : new Error("Failed to submit profile");
        }
      },

      reset: () =>
        set({
          draft: { ...initialDraft },
          currentStep: "basic-info",
          completedSteps: new Set(),
          isSubmitting: false,
          lastSavedAt: null,
          postOnboardingRedirect: null,
        }),
    }),
    {
      name: "paths-onboarding-draft",
      storage: userScopedStorage,
      partialize: (s) => ({
        draft: s.draft,
        currentStep: s.currentStep,
        completedSteps: [...s.completedSteps],
        lastSavedAt: s.lastSavedAt,
        postOnboardingRedirect: s.postOnboardingRedirect,
      }),
      onRehydrateStorage: () => (state) => {
        if (state && Array.isArray(state.completedSteps)) {
          state.completedSteps = new Set(
            state.completedSteps as unknown as OnboardingStep[],
          );
        }
      },
    },
  ),
);

// ── Selectors ─────────────────────────────────────────────────────────────────

export const selectCurrentStepIndex = (s: OnboardingState): number => {
  const steps: OnboardingStep[] = [
    "cv-upload",
    "basic-info",
    "contact",
    "skills",
    "experience",
    "education",
    "links",
    "preferences",
    "review",
  ];
  return steps.indexOf(s.currentStep);
};

export const selectProgressPercent = (s: OnboardingState): number => {
  const total = 9;
  return Math.round((s.completedSteps.size / total) * 100);
};

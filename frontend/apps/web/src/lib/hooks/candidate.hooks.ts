/**
 * PATHS — Candidate Portal TanStack Query Hooks
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { candidatePortalApi } from "@/lib/api/candidate-portal.api";
import type { CandidateProfile, OnboardingDraft } from "@/types/candidate-profile.types";

// ── Profile ───────────────────────────────────────────────────────────────────

export const useMyCandidateProfile = () =>
  useQuery({
    queryKey: ["candidate", "me", "profile"],
    queryFn: () => candidatePortalApi.getMyProfile(),
    staleTime: 5 * 60_000,
    retry: 1,
  });

export const useUpdateCandidateProfile = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: Partial<OnboardingDraft>) =>
      candidatePortalApi.updateProfile(patch),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["candidate", "me", "profile"] });
    },
  });
};

// ── Applications ──────────────────────────────────────────────────────────────

export const useMyCandidateApplications = () =>
  useQuery({
    queryKey: ["candidate", "me", "applications"],
    queryFn: () => candidatePortalApi.getApplications(),
    staleTime: 60_000,
    retry: 1,
  });

// ── CV upload ─────────────────────────────────────────────────────────────────

export const useUploadCV = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const profile =
        qc.getQueryData<CandidateProfile>(["candidate", "me", "profile"]) ??
        qc.getQueryData<CandidateProfile>(["candidate-profile"]);
      const cid = profile?.id;
      if (!cid) throw new Error("Your candidate profile is not loaded. Refresh and try again.");
      return candidatePortalApi.uploadCV(file, cid);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["candidate", "me", "profile"] });
      qc.invalidateQueries({ queryKey: ["candidate-profile"] });
    },
  });
};

// ── Learning Hub ────────────────────────────────────────────────────────────

/**
 * Personalised Learning Hub recommendations for a candidate.
 *
 * Pass the candidate's own id (from their loaded profile). The query stays
 * disabled until the id is known, so it is safe to call while the profile
 * is still loading.
 */
export const useLearningHub = (
  candidateId: string | undefined,
  targetRole?: string,
) =>
  useQuery({
    queryKey: ["candidate", "learning-hub", candidateId, targetRole ?? null],
    queryFn: () =>
      candidatePortalApi.getLearningHub(candidateId as string, targetRole),
    enabled: Boolean(candidateId),
    // Short cache so profile / CV changes are reflected promptly; the
    // mutation hooks also invalidate this key on profile + CV updates.
    staleTime: 60_000,
    retry: 1,
    // Keep the previous payload visible while switching target so the page
    // doesn't flash back to a full skeleton.
    placeholderData: (prev) => prev,
  });

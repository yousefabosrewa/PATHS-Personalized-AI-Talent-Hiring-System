/**
 * PATHS — Candidate Portal API wrappers (auth signup, profile helpers).
 * Prefer `candidatePortalApi` in `@/lib/api` for GET/PUT profile and applications.
 */

import { api } from "./client";
import type { CandidateProfile, OnboardingDraft } from "@/types/candidate-profile.types";
import type { LearningHubResponse } from "@/types/learning-hub.types";
import type { BackendCandidateAppOut, BackendCandidateProfileOut } from "@/lib/api";
import { adaptBackendCandidateProfileOut } from "@/lib/candidate/portal-profile";

// ── Candidate auth ────────────────────────────────────────────────────────────

export interface CandidateSignupPayload {
  full_name: string;
  email: string;
  password: string;
  phone?: string;
  location?: string;
  headline?: string;
}

export interface CandidateRegisterResponse {
  user_id: string;
  candidate_profile_id: string;
  account_type: string;
  message: string;
}

export const candidatePortalLegacyApi = {
  /**
   * Candidate sign-up — creates user + candidate record.
   * Backend: POST /api/v1/auth/register/candidate
   */
  signup: (payload: CandidateSignupPayload) =>
    api.post<CandidateRegisterResponse>("/api/v1/auth/register/candidate", payload),

  /**
   * Full profile shape (merges backend portal fields into empty template).
   */
  getMyProfile: async (): Promise<CandidateProfile> => {
    const raw = await api.get<BackendCandidateProfileOut>("/api/v1/candidates/me/profile");
    return adaptBackendCandidateProfileOut(raw);
  },

  /**
   * Partial update using camelCase draft fields → backend PUT body.
   */
  updateProfileFromDraft: async (patch: Partial<OnboardingDraft>): Promise<CandidateProfile> => {
    const body = draftToUpdateBody(patch);
    const raw = await api.put<BackendCandidateProfileOut>("/api/v1/candidates/me/profile", body);
    return adaptBackendCandidateProfileOut(raw);
  },

  getApplications: () => api.get<BackendCandidateAppOut[]>("/api/v1/candidates/me/applications"),

  /**
   * Submit a direct application for a job as the current candidate.
   * Returns 201 on success, throws ApiError(409) if already applied.
   */
  applyToJob: (jobId: string) =>
    api.post<{ id: string; job_id: string; stage: string; message: string }>(
      `/api/v1/candidates/me/jobs/${jobId}/apply`,
    ),

  /**
   * Check whether the current candidate has already applied to a job.
   * Returns { applied, application_id, stage } — never throws for missing profile.
   */
  getApplicationStatus: (jobId: string) =>
    api.get<{ applied: boolean; application_id: string | null; stage: string | null }>(
      `/api/v1/candidates/me/jobs/${jobId}/application-status`,
    ),

  /**
   * Personalised Learning Hub recommendations (roadmap.sh) for a candidate.
   * Backend: GET /api/v1/candidates/{id}/learning-hub
   */
  getLearningHub: (candidateId: string, targetRole?: string) =>
    api.get<LearningHubResponse>(
      `/api/v1/candidates/${candidateId}/learning-hub${
        targetRole ? `?target_role=${encodeURIComponent(targetRole)}` : ""
      }`,
    ),

  /**
   * Upload CV for ingestion (ties to candidate when `candidateId` is set).
   */
  uploadCV: async (file: File, candidateId?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (candidateId) form.append("candidate_id", candidateId);
    return api.postForm<{
      job_id: string;
      candidate_id: string | null;
      status: string;
    }>("/api/v1/cv-ingestion/upload", form);
  },
};

function draftToUpdateBody(patch: Partial<OnboardingDraft>): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  if (patch.fullName !== undefined) body.full_name = patch.fullName.trim() || undefined;
  if (patch.otherEmails !== undefined) {
    body.other_emails = patch.otherEmails
      .map((e) => e.trim().toLowerCase())
      .filter((e) => e.includes("@"));
  }
  if (patch.phone !== undefined) body.phone = patch.phone?.trim() || undefined;
  if (patch.currentTitle !== undefined) body.current_title = patch.currentTitle.trim() || undefined;
  if (patch.summary !== undefined) body.summary = patch.summary.trim() || undefined;
  if (patch.locationText !== undefined) body.location = patch.locationText.trim() || undefined;
  if (patch.yearsExperience !== undefined) body.years_experience = patch.yearsExperience;
  if (patch.careerLevel !== undefined) body.career_level = patch.careerLevel;
  if (patch.skills !== undefined) {
    body.skills = patch.skills.map((s) => s.name).filter(Boolean);
  }
  if (patch.preferences !== undefined) {
    const p = patch.preferences;
    if (p.jobTypes !== undefined) body.open_to_job_types = p.jobTypes;
    if (p.workplaceTypes !== undefined) body.open_to_workplace_settings = p.workplaceTypes;
    if (p.desiredRoles !== undefined) body.desired_job_titles = p.desiredRoles;
  }

  // Relational sections — only sent when the candidate actually entered rows,
  // so a profile submit never wipes data extracted from an uploaded CV.
  if (patch.education && patch.education.length > 0) {
    const education = patch.education
      .filter((e) => e.institution?.trim())
      .map((e) => ({
        institution: e.institution.trim(),
        degree: e.degree?.trim() || undefined,
        field_of_study: e.fieldOfStudy?.trim() || undefined,
        start_date: e.startYear != null ? String(e.startYear) : undefined,
        end_date: e.isOngoing
          ? undefined
          : e.endYear != null
            ? String(e.endYear)
            : undefined,
      }));
    if (education.length > 0) body.education = education;
  }
  if (patch.experiences && patch.experiences.length > 0) {
    const experiences = patch.experiences
      .filter((x) => x.companyName?.trim() && x.title?.trim())
      .map((x) => ({
        company_name: x.companyName.trim(),
        title: x.title.trim(),
        start_date: x.startDate?.trim() || undefined,
        end_date: x.isCurrent ? undefined : x.endDate?.trim() || undefined,
        description: x.description?.trim() || undefined,
      }));
    if (experiences.length > 0) body.experiences = experiences;
  }
  if (patch.links) {
    const links: { link_type: string; url: string; label?: string }[] = [];
    for (const key of ["linkedin", "github", "portfolio", "website", "twitter"] as const) {
      const url = patch.links[key];
      if (url && url.trim()) links.push({ link_type: key, url: url.trim() });
    }
    for (const other of patch.links.other ?? []) {
      if (other.url?.trim()) {
        links.push({
          link_type: "other",
          url: other.url.trim(),
          label: other.label?.trim() || undefined,
        });
      }
    }
    if (links.length > 0) body.links = links;
  }

  return body;
}

/** Same module paths as before (`@/lib/api/candidate-portal.api`). */
export const candidatePortalApi = {
  signup: candidatePortalLegacyApi.signup,
  getMyProfile: candidatePortalLegacyApi.getMyProfile,
  updateProfile: candidatePortalLegacyApi.updateProfileFromDraft,
  submitOnboarding: candidatePortalLegacyApi.updateProfileFromDraft,
  uploadCV: candidatePortalLegacyApi.uploadCV,
  getApplications: candidatePortalLegacyApi.getApplications,
  applyToJob: candidatePortalLegacyApi.applyToJob,
  getApplicationStatus: candidatePortalLegacyApi.getApplicationStatus,
  getLearningHub: candidatePortalLegacyApi.getLearningHub,
};

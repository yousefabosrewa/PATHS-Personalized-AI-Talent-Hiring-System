/**
 * Maps the backend candidate portal profile (full profile incl. education,
 * experience, links and documents) to the frontend CandidateProfile shape
 * without mixing in demo/mock data.
 */

import type { BackendCandidateProfileOut } from "@/lib/api";
import type {
  CandidateProfile,
  CareerLevel,
  ProfileEducation,
  ProfileExperience,
  ProfileLinks,
  UploadedDocument,
} from "@/types/candidate-profile.types";

const ISO_PLACEHOLDER = "1970-01-01T00:00:00.000Z";

const KNOWN_LINK_KEYS = ["linkedin", "github", "portfolio", "website", "twitter"] as const;

/** Pull a 4-digit year out of a free-form date string ("2022", "Sept 2022"). */
function yearFrom(value: string | null): number | null {
  if (!value) return null;
  const match = value.match(/\d{4}/);
  return match ? Number(match[0]) : null;
}

export function createEmptyCandidateProfile(): CandidateProfile {
  return {
    id: "",
    fullName: "",
    currentTitle: "",
    summary: "",
    careerLevel: "mid",
    yearsExperience: 0,
    email: "",
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
    status: "draft",
    onboardingCompleted: false,
    createdAt: ISO_PLACEHOLDER,
    updatedAt: ISO_PLACEHOLDER,
  };
}

export function adaptBackendCandidateProfileOut(
  raw: BackendCandidateProfileOut,
): CandidateProfile {
  const base = createEmptyCandidateProfile();
  const level = (raw.career_level ?? base.careerLevel) as CareerLevel;

  const education: ProfileEducation[] = (raw.education ?? []).map((e, i) => ({
    id: `edu-${i}`,
    institution: e.institution ?? "",
    degree: e.degree ?? "",
    fieldOfStudy: e.field_of_study ?? "",
    startYear: yearFrom(e.start_date),
    endYear: yearFrom(e.end_date),
    isOngoing: !e.end_date,
  }));

  const experiences: ProfileExperience[] = (raw.experiences ?? []).map((x, i) => ({
    id: `exp-${i}`,
    companyName: x.company_name ?? "",
    title: x.title ?? "",
    startDate: x.start_date ?? "",
    endDate: x.end_date ?? null,
    isCurrent: !x.end_date,
    description: x.description ?? undefined,
  }));

  const links: ProfileLinks = {};
  for (const item of raw.links ?? []) {
    const key = (item.link_type ?? "").toLowerCase();
    if ((KNOWN_LINK_KEYS as readonly string[]).includes(key)) {
      (links as Record<string, string>)[key] = item.url;
    } else {
      (links.other ??= []).push({ label: item.label ?? key, url: item.url });
    }
  }

  const documents: UploadedDocument[] = (raw.documents ?? []).map((d) => ({
    id: String(d.id),
    fileName: d.original_filename ?? "",
    fileSize: 0,
    mimeType: d.mime_type ?? "",
    // Real upload time from the database. Empty string when the backend
    // somehow returns null — the UI then renders an em-dash instead of 1970.
    uploadedAt: d.created_at ?? "",
    status: "processed" as const,
  }));

  return {
    ...base,
    id: String(raw.id),
    fullName: raw.full_name ?? "",
    currentTitle: raw.current_title ?? raw.headline ?? "",
    summary: raw.summary ?? "",
    email: raw.email ?? "",
    otherEmails: raw.other_emails ?? [],
    phone: raw.phone ?? "",
    locationText: raw.location ?? "",
    careerLevel: level,
    yearsExperience: raw.years_experience ?? 0,
    education,
    experiences,
    links,
    documents,
    cvDocument: documents[0],
    skills: (raw.skills ?? []).map((name, i) => ({
      id: `sk-${i}-${name}`,
      name,
      category: "technical" as const,
      proficiency: "intermediate" as const,
    })),
    preferences: {
      ...base.preferences,
      jobTypes: (raw.open_to_job_types ?? []) as CandidateProfile["preferences"]["jobTypes"],
      workplaceTypes: (raw.open_to_workplace_settings ??
        []) as CandidateProfile["preferences"]["workplaceTypes"],
      desiredRoles: raw.desired_job_titles ?? [],
    },
  };
}

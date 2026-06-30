/**
 * PATHS — Candidate Profile Data Model
 *
 * This is the single source of truth for candidate profile data.
 * Used by:
 *   - Candidate onboarding (public facing)
 *   - Candidate portal (logged-in view)
 *   - Recruiter internal view (full profile)
 *   - Anonymized screening view (PII stripped)
 *
 * Keep in sync with backend `CandidateFullProfile` shape.
 */

// ── Onboarding step keys ─────────────────────────────────────────────────────

export type OnboardingStep =
  | "basic-info"
  | "contact"
  | "cv-upload"
  | "education"
  | "experience"
  | "skills"
  | "links"
  | "preferences"
  | "review";

export const ONBOARDING_STEPS: { key: OnboardingStep; label: string; description: string }[] = [
  { key: "cv-upload",    label: "Upload CV",     description: "We'll auto-fill your profile" },
  { key: "basic-info",   label: "Basic Info",    description: "Name, title, and summary" },
  { key: "contact",      label: "Contact",       description: "Emails, phone, and location" },
  { key: "skills",       label: "Skills",        description: "Technical and soft skills" },
  { key: "experience",   label: "Experience",    description: "Work history and roles" },
  { key: "education",    label: "Education",     description: "Degrees and institutions" },
  { key: "links",        label: "Links",         description: "LinkedIn, GitHub, portfolio" },
  { key: "preferences",  label: "Preferences",   description: "Job type and work preferences" },
  { key: "review",       label: "Review",        description: "Confirm and submit" },
];

// ── Sub-types ────────────────────────────────────────────────────────────────

export interface ProfileEducation {
  id: string;
  institution: string;
  degree: string;            // e.g. "Bachelor of Science"
  fieldOfStudy: string;      // e.g. "Computer Science"
  startYear: number | null;
  endYear: number | null;
  isOngoing: boolean;
  gpa?: string;
  description?: string;
}

export interface ProfileExperience {
  id: string;
  companyName: string;
  title: string;
  location?: string;
  startDate: string;         // "YYYY-MM"
  endDate: string | null;    // null = current
  isCurrent: boolean;
  description?: string;
  achievements?: string[];
}

export interface ProfileSkill {
  id: string;
  name: string;
  category: "technical" | "soft" | "language" | "tool" | "other";
  proficiency: "beginner" | "intermediate" | "advanced" | "expert";
}

export interface ProfileLinks {
  linkedin?: string;
  github?: string;
  portfolio?: string;
  website?: string;
  twitter?: string;
  other?: { label: string; url: string }[];
}

export type JobType = "full_time" | "part_time" | "contract" | "freelance" | "internship";
export type WorkplaceType = "remote" | "hybrid" | "onsite";
export type CareerLevel = "junior" | "mid" | "senior" | "lead" | "manager" | "director" | "executive";

export interface ProfilePreferences {
  desiredRoles: string[];
  jobTypes: JobType[];
  workplaceTypes: WorkplaceType[];
  preferredLocations: string[];
  openToRelocation: boolean;
  desiredSalaryMin?: number;
  desiredSalaryMax?: number;
  salaryCurrency: string;
  availableFrom?: string;    // "YYYY-MM-DD"
  noticePeriodWeeks?: number;
}

export interface UploadedDocument {
  id: string;
  fileName: string;
  fileSize: number;          // bytes
  mimeType: string;
  uploadedAt: string;
  status: "processing" | "processed" | "failed";
  extractedText?: string;
}

// ── Full candidate profile ────────────────────────────────────────────────────

export interface CandidateProfile {
  id: string;

  // ── Basic info (Step 1) ──────────────────────────────────────────────────
  fullName: string;
  currentTitle: string;
  summary: string;
  avatarUrl?: string;
  careerLevel: CareerLevel;
  yearsExperience: number;

  // ── Contact (Step 2) ────────────────────────────────────────────────────
  email: string;            // Primary / sign-in email (from sign-up)
  otherEmails?: string[];   // Additional emails for contact + GitHub/LinkedIn verification
  phone?: string;
  locationCity?: string;
  locationCountry?: string;
  locationText?: string;     // Full string e.g. "Cairo, Egypt"

  // ── Education (Step 3) ──────────────────────────────────────────────────
  education: ProfileEducation[];

  // ── Experience (Step 4) ─────────────────────────────────────────────────
  experiences: ProfileExperience[];

  // ── Skills (Step 5) ─────────────────────────────────────────────────────
  skills: ProfileSkill[];

  // ── CV document (Step 6) ────────────────────────────────────────────────
  cvDocument?: UploadedDocument;
  documents: UploadedDocument[];

  // ── Links (Step 7) ──────────────────────────────────────────────────────
  links: ProfileLinks;

  // ── Preferences (Step 8) ────────────────────────────────────────────────
  preferences: ProfilePreferences;

  // ── Meta ────────────────────────────────────────────────────────────────
  status: "draft" | "submitted" | "active" | "passive" | "hired" | "withdrawn";
  onboardingCompleted: boolean;
  onboardingCompletedAt?: string;
  createdAt: string;
  updatedAt: string;
}

// ── Anonymized screening view (Blueprint Law #2) ─────────────────────────────

/**
 * AnonymizedCandidateView — what agents and recruiters see during blind screening.
 * PII is stripped or replaced with anonymous identifiers.
 */
export interface AnonymizedCandidateView {
  alias: string;             // "Candidate A3F2B1"
  currentTitle: string;      // Title kept — not a protected attribute
  careerLevel: CareerLevel;
  yearsExperience: number;
  summary: string;           // Name tokens replaced with [REDACTED]
  locationGeneral: string;   // City + country only, no street
  skills: { name: string; proficiency: string }[];
  education: { degree: string; fieldOfStudy: string; graduationYear: number | null }[];
  experiences: { title: string; durationMonths: number | null; description: string; isCurrent: boolean }[];
  certifications: string[];
  projects: { name: string; description: string; technologies: string[] }[];
  desiredJobTypes: JobType[];
  desiredWorkplace: WorkplaceType[];
  // Recruiter-visible assessment data
  matchScore?: number;
  matchConfidence?: number;
  screeningStatus?: string;
  biasFlags?: { rule: string; severity: "low" | "medium" | "high"; description: string }[];
}

// ── Onboarding state (Zustand) ───────────────────────────────────────────────

export type OnboardingDraft = Partial<Omit<CandidateProfile, "id" | "createdAt" | "updatedAt" | "status">>;

export interface OnboardingState {
  draft: OnboardingDraft;
  currentStep: OnboardingStep;
  completedSteps: Set<OnboardingStep>;
  isSubmitting: boolean;
  lastSavedAt: string | null;
  /** URL to redirect to after onboarding completes (e.g. the job page that triggered signup) */
  postOnboardingRedirect: string | null;

  // Actions
  setStep: (step: OnboardingStep) => void;
  markStepComplete: (step: OnboardingStep) => void;
  updateDraft: (patch: Partial<OnboardingDraft>) => void;
  saveDraft: () => Promise<void>;
  submitProfile: () => Promise<string>; // returns candidate ID
  setPostOnboardingRedirect: (url: string | null) => void;
  reset: () => void;
}

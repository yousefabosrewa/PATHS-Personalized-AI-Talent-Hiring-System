/**
 * PATHS Backend API — typed wrappers for every endpoint.
 * Each function corresponds 1-to-1 with a backend route.
 * Import from here in hooks; never call `api.*` directly in components.
 */

import { api } from "./client";

// ── Types matching backend response shapes ──────────────────────────────

/** One configurable stage in a job's hiring pipeline (candidate workflow). */
export type PipelineStageKind =
  | "screening"
  | "assessment"
  | "hr_interview"
  | "technical_interview"
  | "mixed_interview";

export interface JobPipelineStage {
  key: string;
  kind: PipelineStageKind;
  label: string;
  group?: string;
}

/** Stage as submitted when creating/updating a job. */
export interface JobPipelineStageInput {
  kind: PipelineStageKind;
  label?: string;
  key?: string;
}

export interface BackendJob {
  id: string;
  title: string;
  status: string;
  source_type: string | null;
  source_platform?: string | null;
  application_mode: string;
  external_apply_url: string | null;
  visibility: string;
  employment_type: string | null;
  seniority_level: string | null;
  workplace_type: string | null;
  location_text: string | null;
  location_mode: string | null;
  role_family: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  min_years_experience: number | null;
  max_years_experience: number | null;
  is_active: boolean;
  applicant_count: number;
  // Per-stage applicant counts for the jobs-list mini pipeline chart.
  pipeline_breakdown?: { stage: string; label: string; count: number }[];
  // Recruiter-entered required skills (job_skill_requirements rows).
  skills?: { name: string; required: boolean }[];
  summary?: string | null;
  description_text?: string | null;
  description?: string | null;
  requirements?: string | null;
  company_name?: string | null;
  company?: string | null;
  source?: string | null;
  job_url?: string | null;
  source_url?: string | null;
  hiring_pipeline?: JobPipelineStage[];
  created_at?: string | null;
  updated_at?: string | null;
}

/** Query params for GET /api/v1/jobs */
export interface JobsListFilters {
  activeOnly?: boolean;
  keyword?: string;
  location?: string;
  source?: string;
  company?: string;
  status?: string;
  remote?: boolean;
  employmentType?: string;
  limit?: number;
  offset?: number;
}

export interface JobImportRunResponse {
  success: boolean;
  found: number;
  inserted: number;
  duplicates: number;
  failed: number;
  errors: string[];
}

export interface JobImportPipelineStatus {
  last_run_at: string | null;
  last_success: boolean | null;
  last_inserted_count: number | null;
  last_error: string | null;
}

export interface BackendApplication {
  id: string;
  candidate_id: string;
  job_id: string;
  application_type: string;
  source_channel: string | null;
  current_stage_code: string;
  overall_status: string;
  created_at: string;
  updated_at: string | null;
  candidate_name: string | null;
  candidate_email: string | null;
  candidate_current_title?: string | null;
  candidate_skills?: string[];
  job_title: string | null;
  match_final_score?: number | null;
  match_confidence?: number | null;
  roadmap?: BackendRoadmap;
}

export interface BackendShortlistItem {
  application_id: string;
  candidate_id: string;
  candidate_name: string | null;
  current_stage_code: string;
  final_score: number | null;
  agent_score: number | null;
  vector_similarity_score: number | null;
  confidence: number | null;
  explanation: string | null;
  strengths: string[];
  weaknesses: string[];
  matched_skills: string[];
  missing_required_skills: string[];
  criteria_breakdown: Record<string, unknown> | null;
  rank: number;
}

export interface BackendApproval {
  id: string;
  organization_id: string;
  action_type: string;
  status: string;
  priority: string;
  entity_type: string;
  entity_id: string;
  entity_label: string;
  requested_by_name: string;
  requested_at: string;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  decision: string | null;
  reason: string | null;
  expires_at: string | null;
  meta_json: Record<string, string> | null;
  created_at: string;
}

export interface BackendMember {
  id: string;
  user_id: string;
  organization_id: string;
  role_code: string;
  is_active: boolean;
  // fix8&9 Update 2 — lifecycle fields. `status` is "active" for legacy
  // rows, "pending" until first successful login.
  status?: "active" | "pending" | "suspended" | string;
  joined_at: string;
  invited_at?: string | null;
  activated_at?: string | null;
  first_login_at?: string | null;
  invited_by_user_id?: string | null;
  full_name: string | null;
  email: string | null;
}

export interface BackendAuditEvent {
  id: number;
  actor_type: string;
  actor_id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  before_jsonb: Record<string, unknown> | null;
  after_jsonb: Record<string, unknown> | null;
  created_at: string;
}

export interface BackendDashboardStats {
  active_jobs: number;
  total_candidates: number;
  pending_approvals: number;
  applications_this_week: number;
  shortlisted_today: number;
  interviews_scheduled: number;
  hired_this_month: number;
  avg_time_to_hire_days: number;
}

export interface BackendAgentStatus {
  id: string;
  name: string;
  status: string;
  progress: number;
  current_task: string | null;
  jobs_processed: number;
  last_run: string | null;
}

export interface BackendFunnelItem {
  stage: string;
  count: number;
  conversionRate: number;
}

// ── Jobs ──────────────────────────────────────────────────────────────────

function jobsListQuery(filters: JobsListFilters = {}): string {
  const sp = new URLSearchParams();
  if (filters.activeOnly) sp.set("active_only", "true");
  if (filters.keyword?.trim()) sp.set("keyword", filters.keyword.trim());
  if (filters.location?.trim()) sp.set("location", filters.location.trim());
  if (filters.source?.trim()) sp.set("source", filters.source.trim());
  if (filters.company?.trim()) sp.set("company", filters.company.trim());
  if (filters.status?.trim()) sp.set("status", filters.status.trim());
  if (filters.remote === true) sp.set("remote", "true");
  if (filters.remote === false) sp.set("remote", "false");
  if (filters.employmentType?.trim()) {
    sp.set("employment_type", filters.employmentType.trim());
  }
  if (filters.limit != null) sp.set("limit", String(filters.limit));
  if (filters.offset != null) sp.set("offset", String(filters.offset));
  const q = sp.toString();
  return q ? `?${q}` : "";
}

export interface BackendScreeningSourceCandidate {
  candidate_id: string;
  name: string;
  headline: string | null;
  current_title: string | null;
  score: number | null;
  matched_skills: string[];
  already_applied: boolean;
}

// Write payload for creating/updating a job. Skills are sent as plain
// strings (the backend turns them into job_skill_requirements rows).
export type BackendJobWriteBody = Partial<Omit<BackendJob, "skills">> & {
  skills?: string[];
};

export const jobsApi = {
  list: (filters: JobsListFilters = {}) =>
    api.get<BackendJob[]>(`/api/v1/jobs${jobsListQuery(filters)}`),
  get: (jobId: string) =>
    api.get<BackendJob>(`/api/v1/jobs/${jobId}`),
  create: (body: BackendJobWriteBody) =>
    api.post<BackendJob>("/api/v1/jobs", body),
  update: (jobId: string, body: BackendJobWriteBody) =>
    api.patch<BackendJob>(`/api/v1/jobs/${jobId}`, body),
  // Permanently delete an org's job (and its dependent records). 204 No Content.
  delete: (jobId: string) => api.delete<void>(`/api/v1/jobs/${jobId}`),
  // Run Screening → top source-database candidates scored for this job.
  screeningSourceCandidates: (jobId: string, limit = 10) =>
    api.get<{ items: BackendScreeningSourceCandidate[] }>(
      `/api/v1/jobs/${jobId}/screening/source-candidates?limit=${limit}`,
    ),
  // Add a scored candidate into this job's process.
  addCandidateToJob: (jobId: string, candidateId: string) =>
    api.post<{ application_id: string; candidate_id: string; already_in_process: boolean }>(
      `/api/v1/jobs/${jobId}/applicants/${candidateId}`,
    ),
  runImport: (body: {
    keyword?: string;
    location?: string;
    limit?: number;
    source?: string;
  }) => api.post<JobImportRunResponse>("/api/v1/jobs/import/run", body),
  importStatus: () =>
    api.get<JobImportPipelineStatus>("/api/v1/jobs/import/status"),
};

// ── Applications ──────────────────────────────────────────────────────────

export const applicationsApi = {
  list: (stage?: string) =>
    api.get<BackendApplication[]>(
      `/api/v1/applications${stage ? `?stage=${stage}` : ""}`,
    ),
  get: (id: string) =>
    api.get<BackendApplication>(`/api/v1/applications/${id}`),
  listByJob: (jobId: string, stage?: string) =>
    api.get<BackendApplication[]>(
      `/api/v1/jobs/${jobId}/applications${stage ? `?stage=${stage}` : ""}`,
    ),
  advanceStage: (id: string, stage: string, reason?: string) =>
    api.patch<BackendApplication>(`/api/v1/applications/${id}/stage`, {
      stage,
      reason,
    }),
  shortlist: (jobId: string) =>
    api.get<BackendShortlistItem[]>(`/api/v1/jobs/${jobId}/shortlist`),
};

// ── Approvals ─────────────────────────────────────────────────────────────

export const approvalsApi = {
  list: (status?: string) =>
    api.get<BackendApproval[]>(
      `/api/v1/approvals${status ? `?status=${status}` : ""}`,
    ),
  pending: () => api.get<BackendApproval[]>("/api/v1/approvals?status=pending"),
  decide: (id: string, decision: "approved" | "rejected", reason?: string) =>
    api.post<BackendApproval>(`/api/v1/approvals/${id}/decide`, {
      decision,
      reason,
    }),
  create: (body: {
    action_type: string;
    entity_type: string;
    entity_id: string;
    entity_label: string;
    priority?: string;
    meta_json?: Record<string, string>;
  }) => api.post<BackendApproval>("/api/v1/approvals", body),
};

// ── Members ───────────────────────────────────────────────────────────────

export const membersApi = {
  list: () => api.get<BackendMember[]>("/api/v1/organizations/me/members"),
  invite: (orgId: string, body: { full_name: string; email: string; password: string; role_code: string }) =>
    api.post<{
      member_id: string;
      user_id: string;
      organization_id: string;
      role_code: string;
      status?: string;
      invited_at?: string | null;
    }>(
      `/api/v1/organizations/${orgId}/members`,
      body,
    ),
  // Compose the exact invite email (to/subject/body) for review — nothing is
  // created or sent until the admin approves and the real invite call runs.
  invitePreview: (
    orgId: string,
    body: { full_name: string; email: string; password: string; role_code: string },
  ) =>
    api.post<{ to: string; subject: string; body: string }>(
      `/api/v1/organizations/${orgId}/members/invite-preview`,
      body,
    ),
  // fix8&9 — resend invite + delete member
  resendInvite: (
    orgId: string,
    membershipId: string,
    body?: { temporary_password?: string | null },
  ) =>
    api.post<{ ok: boolean; provider?: string }>(
      `/api/v1/organizations/${orgId}/members/${membershipId}/resend-invite`,
      body ?? {},
    ),
  remove: (orgId: string, membershipId: string) =>
    api.delete<void>(
      `/api/v1/organizations/${orgId}/members/${membershipId}`,
    ),
};

// ── Audit ─────────────────────────────────────────────────────────────────

export const auditApi = {
  list: (search?: string) =>
    api.get<BackendAuditEvent[]>(
      `/api/v1/audit${search ? `?search=${encodeURIComponent(search)}` : ""}`,
    ),
};

// ── Dashboard ─────────────────────────────────────────────────────────────

export const dashboardApi = {
  stats: () => api.get<BackendDashboardStats>("/api/v1/dashboard/stats"),
  funnel: () => api.get<BackendFunnelItem[]>("/api/v1/dashboard/funnel"),
  weekly: () =>
    api.get<{ week: string; applications: number; shortlisted: number }[]>(
      "/api/v1/dashboard/weekly",
    ),
  agents: () => api.get<BackendAgentStatus[]>("/api/v1/dashboard/agents"),
};

// ── Candidates (recruiter view) ────────────────────────────────────────────

export const recruitCandidatesApi = {
  get: (id: string) => api.get<Record<string, unknown>>(`/api/v1/candidates/${id}`),
};

// ── Evidence ──────────────────────────────────────────────────────────────

export interface BackendEvidenceItem {
  id: string;
  candidate_id: string;
  ingestion_job_id: string | null;
  type: string;
  field_ref: string | null;
  source_uri: string | null;
  extracted_text: string | null;
  confidence: number | null;
  meta_json: Record<string, unknown> | null;
  created_at: string;
}

export interface BackendCandidateSource {
  id: string;
  candidate_id: string;
  source: string;
  url: string | null;
  raw_blob_uri: string | null;
  fetched_at: string | null;
  created_at: string;
}

export const evidenceApi = {
  listItems: (candidateId: string, type?: string) =>
    api.get<BackendEvidenceItem[]>(
      `/api/v1/candidates/${candidateId}/evidence${type ? `?type=${encodeURIComponent(type)}` : ""}`,
    ),
  listSources: (candidateId: string) =>
    api.get<BackendCandidateSource[]>(`/api/v1/candidates/${candidateId}/sources`),
  addSource: (candidateId: string, body: { source: string; url?: string; raw_blob_uri?: string }) =>
    api.post<BackendCandidateSource>(`/api/v1/candidates/${candidateId}/sources`, body),
};

// ── Candidate Portal ──────────────────────────────────────────────────────

export interface BackendEducationItem {
  institution: string;
  degree: string | null;
  field_of_study: string | null;
  start_date: string | null;
  end_date: string | null;
}

export interface BackendExperienceItem {
  company_name: string;
  title: string;
  start_date: string | null;
  end_date: string | null;
  description: string | null;
}

export interface BackendLinkItem {
  link_type: string;
  url: string;
  label: string | null;
}

export interface BackendDocumentItem {
  id: string;
  document_type: string;
  original_filename: string;
  mime_type: string;
  created_at: string | null;
}

export interface BackendCandidateProfileOut {
  id: string;
  full_name: string;
  email: string | null;
  other_emails?: string[];
  phone: string | null;
  location: string | null;
  headline: string | null;
  current_title: string | null;
  summary: string | null;
  years_experience: number | null;
  career_level: string | null;
  skills: string[];
  open_to_job_types: string[];
  open_to_workplace_settings: string[];
  desired_job_titles: string[];
  desired_job_categories: string[];
  education: BackendEducationItem[];
  experiences: BackendExperienceItem[];
  links: BackendLinkItem[];
  documents: BackendDocumentItem[];
}

export type RoadmapStepState = "done" | "current" | "upcoming";

export interface BackendRoadmapStep {
  key: string;
  kind: string;
  label: string;
  group: string;
  state: RoadmapStepState;
  clickable: boolean;
}

export interface BackendRoadmap {
  steps: BackendRoadmapStep[];
  current_index: number;
  terminal: boolean;
  terminal_label: string | null;
}

export interface BackendCandidateAppOut {
  id: string;
  job_id: string;
  job_title: string | null;
  company_name: string | null;
  location_text: string | null;
  workplace_type: string | null;
  current_stage_code: string;
  overall_status: string;
  created_at: string;
  match_score?: number | null;
  has_assessment?: boolean;
  assessment_status?: "not_started" | "submitted" | "none";
  assessment_score_percent?: number | null;
  roadmap?: BackendRoadmap;
}

export interface BackendApplicationFit {
  application_id: string;
  job_title: string | null;
  match: {
    score: number | null;
    matched_skills: string[];
    missing_skills: string[];
    explanation: string;
  };
  screening: {
    score: number | null;
    explanation: string;
    strengths: string[];
    gaps: string[];
  };
}

export interface BackendCandidateAssessmentQuestion {
  id: string;
  question: string | null;
  scenario?: string | null;
  type?: string | null;
  options?: string[] | null;
  score?: number | null;
  estimated_time_minutes?: number | null;
  difficulty?: string | null;
}

export interface BackendAssessmentReportQuestion {
  question_id: string;
  question: string;
  answer: string;
  awarded: number;
  max: number;
  feedback: string;
}

export interface BackendAssessmentReport {
  status: "submitted";
  score: number | null;
  max_score: number | null;
  score_percent: number | null;
  summary: string | null;
  strengths: string[];
  areas_to_improve: string[];
  per_question: BackendAssessmentReportQuestion[];
  submitted_at: string | null;
  provisional: boolean;
}

export interface BackendCandidateAssessment {
  application_id: string;
  job_id: string | null;
  job_title: string | null;
  available: boolean;
  // "locked" → the candidate hasn't reached the assessment stage yet.
  status: "not_started" | "submitted" | "locked";
  locked?: boolean;
  locked_reason?: string;
  assessment: {
    id: string;
    title: string;
    description: string | null;
    assessment_type: string;
    difficulty: string | null;
    duration_minutes: number | null;
    total_score: number | null;
    instructions: string | null;
    questions: BackendCandidateAssessmentQuestion[];
  } | null;
  report: BackendAssessmentReport | null;
}

export const candidatePortalApi = {
  getProfile: () =>
    api.get<BackendCandidateProfileOut>("/api/v1/candidates/me/profile"),
  updateProfile: (body: {
    full_name?: string;
    phone?: string;
    current_title?: string;
    summary?: string;
    location?: string;
    years_experience?: number;
    career_level?: string;
    skills?: string[];
    open_to_job_types?: string[];
    open_to_workplace_settings?: string[];
    desired_job_titles?: string[];
    desired_job_categories?: string[];
    links?: { link_type: string; url: string; label?: string }[];
    education?: {
      institution: string;
      degree?: string;
      field_of_study?: string;
      start_date?: string;
      end_date?: string;
    }[];
    experiences?: {
      company_name: string;
      title: string;
      start_date?: string;
      end_date?: string;
      description?: string;
    }[];
  }) => api.put<BackendCandidateProfileOut>("/api/v1/candidates/me/profile", body),
  getApplications: () =>
    api.get<BackendCandidateAppOut[]>("/api/v1/candidates/me/applications"),
  getApplicationAssessment: (appId: string) =>
    api.get<BackendCandidateAssessment>(
      `/api/v1/candidates/me/applications/${appId}/assessment`,
    ),
  submitApplicationAssessment: (appId: string, answers: Record<string, string>) =>
    api.post<BackendAssessmentReport>(
      `/api/v1/candidates/me/applications/${appId}/assessment/submit`,
      { answers },
      { timeoutMs: 120_000 },
    ),
  applyToJob: (jobId: string) =>
    api.post<{ id: string; job_id: string; stage: string; message: string }>(
      `/api/v1/candidates/me/jobs/${jobId}/apply`,
    ),
  getApplicationStatus: (jobId: string) =>
    api.get<{ applied: boolean; application_id: string | null; stage: string | null }>(
      `/api/v1/candidates/me/jobs/${jobId}/application-status`,
    ),
  // Delete a CV / document the candidate uploaded. Backend removes the DB
  // row + the file on disk; extracted profile data (skills, education, …) is
  // intentionally preserved.
  deleteDocument: (documentId: string) =>
    api.delete<void>(
      `/api/v1/candidates/me/documents/${encodeURIComponent(documentId)}`,
    ),
  // Development & growth plan (from the hiring decision) + progress tracking.
  getDevelopmentPlan: () =>
    api.get<BackendCandidateDevelopmentPlan>("/api/v1/candidates/me/development-plan"),
  updateDevelopmentProgress: (body: {
    plan_id: string;
    item_id: string;
    status: "todo" | "in_progress" | "done";
  }) =>
    api.post<BackendCandidateDevelopmentPlan>(
      "/api/v1/candidates/me/development-plan/progress",
      body,
    ),
  // Application roadmap: interview details + anonymized offer ranking.
  getApplicationInterview: (appId: string, kind?: string) =>
    api.get<BackendApplicationInterview>(
      `/api/v1/candidates/me/applications/${encodeURIComponent(appId)}/interview` +
        (kind ? `?kind=${encodeURIComponent(kind)}` : ""),
    ),
  getApplicationRanking: (appId: string) =>
    api.get<BackendApplicationRanking>(
      `/api/v1/candidates/me/applications/${encodeURIComponent(appId)}/ranking`,
    ),
  // Applied + CV-screening transparency: the candidate's match + CV-fit.
  getApplicationFit: (appId: string) =>
    api.get<BackendApplicationFit>(
      `/api/v1/candidates/me/applications/${encodeURIComponent(appId)}/fit`,
    ),
  // Per-stage result analysis — unlocks once the application is finalised
  // (accepted / rejected). Explains the outcome stage-by-stage to the candidate.
  getApplicationJourney: (appId: string) =>
    api.get<BackendApplicationJourney>(
      `/api/v1/candidates/me/applications/${encodeURIComponent(appId)}/journey`,
    ),
  // Onboarding step 1 — upload the CV, extract structured data, save the document.
  // Uses postForm (NOT post) so the multipart body + Authorization header are
  // sent as-is. The candidate is identified server-side from the JWT, so the
  // CV + extracted document are always linked to the logged-in candidate.
  extractMyCV: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.postForm<BackendCVExtractResult>("/api/v1/candidates/me/cv-extract", form);
  },
};

export interface BackendCVExtractExperience {
  company_name?: string | null;
  title?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  description?: string | null;
}

export interface BackendCVExtractEducation {
  institution?: string | null;
  degree?: string | null;
  field_of_study?: string | null;
  start_date?: string | null;
  end_date?: string | null;
}

export interface BackendCVExtractResult {
  document_id: string;
  full_name?: string | null;
  email?: string | null;
  phone?: string | null;
  location?: string | null;
  summary?: string | null;
  current_title?: string | null;
  years_experience?: number | null;
  skills: string[];
  experiences: BackendCVExtractExperience[];
  education: BackendCVExtractEducation[];
  certifications: { name?: string | null; issuer?: string | null }[];
}

export interface BackendApplicationInterview {
  has_interview: boolean;
  message?: string;
  interview_type?: string;
  status?: string;
  scheduled_at?: string | null;
  summary?: string;
  key_points?: string[];
  strengths?: string[];
  analysed?: boolean;
}

export interface BackendJourneyStage {
  key: string;
  kind: string;
  label: string;
  score: number | null;
  ai_explanation: string;
  status: string;
}

export interface BackendApplicationJourney {
  application_id: string;
  job_id: string | null;
  job_title: string | null;
  finalized: boolean;
  decision: "accepted" | "rejected" | null;
  overall: { score: number | null; recommendation: string | null };
  stages: BackendJourneyStage[];
  decision_message: string | null;
  development_plan: { plan_type: string; summary: string | null } | null;
}

export interface BackendRankingRow {
  rank: number;
  label: string;
  is_you: boolean;
  score: number;
  strengths: string[];
  explanation: string;
  recommendation?: string | null;
}

export interface BackendApplicationRanking {
  has_ranking: boolean;
  message?: string;
  job_title?: string | null;
  total?: number;
  your_rank?: number | null;
  you_in_ranking?: boolean;
  results?: BackendRankingRow[];
}

export type DevPlanTaskStatus = "todo" | "in_progress" | "done";

export interface BackendDevPlanTask {
  id: string;
  text: string;
  status: DevPlanTaskStatus;
}

export interface BackendDevPlanPhase {
  key: string;
  label: string;
  month_label: string;
  start_date: string | null;
  end_date: string | null;
  status: "not_started" | "in_progress" | "done";
  tasks: BackendDevPlanTask[];
  skills_to_improve: string[];
  learning_resources: string[];
  measurable_outcomes_or_kpis: string[];
  manager_check_in_points: string[];
  evidence_to_collect: string[];
}

export interface BackendCandidateDevelopmentPlan {
  has_plan: boolean;
  message?: string;
  plan_id?: string;
  job_id?: string | null;
  job_title?: string | null;
  company_name?: string | null;
  decision?: "accepted" | "rejected";
  plan_type?: string | null;
  title?: string;
  duration_months?: number;
  summary?: string;
  candidate_message?: string;
  started_at?: string | null;
  phases?: BackendDevPlanPhase[];
  progress?: {
    total: number;
    done: number;
    in_progress: number;
    todo: number;
    percent: number;
  };
}

// ── Public Jobs (no auth) ─────────────────────────────────────────────────

export const publicJobsApi = {
  list: (limit = 50) =>
    api.get<BackendJob[]>(`/api/v1/jobs/public?limit=${limit}`),
  get: (jobId: string) =>
    api.get<BackendJob>(`/api/v1/jobs/public/${jobId}`),
};

// ── CV Ingestion ──────────────────────────────────────────────────────────

export interface BackendIngestionJob {
  job_id: string;
  candidate_id: string | null;
  stage: string;
  status: string;
  error_message: string | null;
}

export const cvIngestionApi = {
  upload: (file: File, candidateId?: string) => {
    const formData = new FormData();
    formData.append("file", file);
    if (candidateId) formData.append("candidate_id", candidateId);
    return api.postForm<BackendIngestionJob>("/api/v1/cv-ingestion/upload", formData);
  },
  getJobStatus: (jobId: string) =>
    api.get<BackendIngestionJob>(`/api/v1/cv-ingestion/jobs/${jobId}`),
};

// ── Organization Profile ──────────────────────────────────────────────────

export interface BackendOrgProfile {
  id: string;
  name: string;
  slug: string;
  industry: string | null;
  companySize: string | null;
  companyType: string | null;
  contactEmail: string | null;
  /**
   * Persisted on ``organizations.website`` (added by the n140014
   * migration). Was missing from this interface, so the adapter could
   * not see it and the Save flow appeared to "lose" the value the
   * recruiter typed.
   */
  website: string | null;
  isActive: boolean;
}

export const organizationApi = {
  getMe: () => api.get<BackendOrgProfile>("/api/v1/organizations/me"),
};

// ── Bias & Fairness ───────────────────────────────────────────────────────

export interface BackendDeAnonEvent {
  id: string;
  candidate_id: string;
  purpose: string;
  requested_at: string;
  granted_at: string | null;
  denied_at: string | null;
  approval_id: string | null;
}

export interface BackendShortlistProposeOut {
  approval_id: string;
  status: string;
  message: string;
}

export interface BackendBiasFlagOut {
  id: string;
  scope: string;
  scope_id: string;
  rule: string;
  severity: string;
  status: string;
  detail: Record<string, unknown> | null;
  created_at: string | null;
}

export interface BackendBiasAuditOut {
  id: number;
  event_type: string;
  candidate_id: string | null;
  job_id: string | null;
  actor_id: string | null;
  detail_json: Record<string, unknown> | null;
  created_at: string;
}

export interface BackendAnonymizedViewOut {
  id: string;
  candidate_id: string;
  view_version: number;
  view_json: Record<string, unknown>;
  stripped_fields: string[] | null;
  created_at: string | null;
}

export const biasFairnessApi = {
  requestDeanon: (candidateId: string, purpose = "outreach") =>
    api.post<BackendDeAnonEvent>(`/api/v1/candidates/${candidateId}/deanonymize`, { purpose }),
  getDeanonStatus: (candidateId: string) =>
    api.get<BackendDeAnonEvent | null>(`/api/v1/candidates/${candidateId}/deanon-status`),
  proposeShortlist: (jobId: string) =>
    api.post<BackendShortlistProposeOut>(`/api/v1/jobs/${jobId}/shortlist/propose`, {}),
  getAnonymizedView: (candidateId: string) =>
    api.get<BackendAnonymizedViewOut>(`/api/v1/candidates/${candidateId}/anonymized`),
  listBiasFlags: (params?: { status?: string; scope?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.scope) q.set("scope", params.scope);
    if (params?.limit) q.set("limit", String(params.limit));
    const qs = q.toString();
    return api.get<BackendBiasFlagOut[]>(`/api/v1/bias/flags${qs ? `?${qs}` : ""}`);
  },
  readBiasAudit: (params?: { event_type?: string; candidate_id?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.event_type) q.set("event_type", params.event_type);
    if (params?.candidate_id) q.set("candidate_id", params.candidate_id);
    if (params?.limit) q.set("limit", String(params.limit));
    const qs = q.toString();
    return api.get<BackendBiasAuditOut[]>(`/api/v1/bias/audit${qs ? `?${qs}` : ""}`);
  },
};

// ── Knowledge Base / Vector Store ──────────────────────────────────────────

export interface BackendQdrantCollection {
  name: string;
  status: string;
  vectors_count: number | null;
  dimension: number | null;
}

export interface BackendDocumentChunk {
  id: string;
  content: string;
  score: number;
  source: string;
  metadata: Record<string, unknown>;
}

export interface BackendVectorSearchHit {
  id: string;
  score: number;
  payload: Record<string, unknown>;
}

export const kbApi = {
  listCollections: () =>
    api.get<{ collections: string[] }>("/api/v1/system/qdrant/collections"),
  getCollection: (name: string) =>
    api.get<BackendQdrantCollection>(
      `/api/v1/system/qdrant/collections/${encodeURIComponent(name)}`,
    ),
  initCollections: () =>
    api.post<{ status: string; collection: string; action: string }>(
      "/api/v1/system/qdrant/init-collections",
    ),
  search: (collection: string, query: string, limit = 5) =>
    api.post<BackendVectorSearchHit[]>("/api/v1/system/qdrant/search", {
      collection,
      query,
      limit,
    }),
};

// ── Identity Resolution ────────────────────────────────────────────────────

export interface BackendDuplicateOut {
  id: string;
  candidate_id_a: string;
  candidate_id_b: string;
  organization_id: string;
  match_reason: string;
  match_value: string;
  confidence: number;
  status: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  notes: string | null;
  merged_into_candidate_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface BackendDuplicateListOut {
  organization_id: string;
  total: number;
  items: BackendDuplicateOut[];
}

export interface BackendMergeHistoryOut {
  id: string;
  organization_id: string;
  kept_candidate_id: string;
  removed_candidate_id: string;
  merged_by: string;
  merged_at: string | null;
  merge_reason: string | null;
  audit_log: Record<string, unknown> | null;
  created_at: string | null;
}

export interface BackendMergeHistoryListOut {
  organization_id: string;
  total: number;
  items: BackendMergeHistoryOut[];
}

export interface BackendScanResult {
  organization_id: string;
  scanned: boolean;
  new_duplicates_found: number;
}

export const identityResolutionApi = {
  scan: () =>
    api.post<BackendScanResult>("/api/v1/identity-resolution/scan"),
  listDuplicates: (status?: string) =>
    api.get<BackendDuplicateListOut>(
      `/api/v1/identity-resolution/duplicates${status ? `?status=${status}` : ""}`,
    ),
  approveMerge: (id: string, notes?: string) =>
    api.post<BackendDuplicateOut>(`/api/v1/identity-resolution/duplicates/${id}/approve`, notes ? { notes } : {}),
  rejectMerge: (id: string, notes?: string) =>
    api.post<BackendDuplicateOut>(`/api/v1/identity-resolution/duplicates/${id}/reject`, notes ? { notes } : {}),
  getMergeHistory: () =>
    api.get<BackendMergeHistoryListOut>("/api/v1/identity-resolution/merge-history"),
};

// ── Assessment Agent (fix5.md — job-level templates) ─────────────────────

export type AssessmentTypeValue =
  | "technical_assessment"
  | "hr_assessment"
  | "iq_test"
  | "problem_solving_coding"
  | "problem_solving_thinking"
  | "quiz";

export type AssessmentDifficulty = "junior" | "intermediate" | "senior" | "expert";

export const ASSESSMENT_TYPE_OPTIONS: { value: AssessmentTypeValue; label: string }[] = [
  { value: "technical_assessment", label: "Technical Assessment" },
  { value: "hr_assessment", label: "HR Assessment" },
  { value: "iq_test", label: "IQ Test" },
  { value: "problem_solving_coding", label: "Problem Solving: Coding" },
  { value: "problem_solving_thinking", label: "Problem Solving: Thinking" },
  { value: "quiz", label: "Quiz" },
];

export interface BackendAssessmentQuestion {
  id?: string;
  question?: string;
  scenario?: string;
  type?: string;
  difficulty?: string;
  estimated_time_minutes?: number;
  score?: number;
  expected_answer?: string;
  rubric?: { criterion: string; points: number }[];
  agent_reason?: string;
  measures?: string[];
  mapped_job_requirements?: string[];
  // HR
  competency_measured?: string;
  strong_answer_indicators?: string[];
  weak_answer_indicators?: string[];
  // IQ / quiz
  options?: string[];
  correct_answer?: string | string[];
  explanation?: string;
  skill_measured?: string;
  // Coding
  input_output_examples?: { input: string; output: string }[];
  constraints?: string[];
  expected_solution_approach?: string;
  hidden_test_ideas?: string[];
  // Thinking
  expected_reasoning_path?: string[];
  // Allow extra fields the agent might add
  [key: string]: unknown;
}

export interface BackendAssessmentOut {
  id: string;
  organization_id: string;
  job_id: string;
  application_id: string | null;
  candidate_id: string | null;
  title: string;
  description: string | null;
  assessment_type: string;
  difficulty: string | null;
  duration_minutes: number | null;
  total_score: number | null;
  status: string;
  questions: BackendAssessmentQuestion[] | null;
  agent_metadata: Record<string, unknown> | null;
  source_file_id: string | null;
  source_file_name: string | null;
  // Legacy attempt-side fields (kept rendering for old rows)
  score: number | null;
  max_score: number | null;
  score_percent: number | null;
  instructions: string | null;
  submission_text: string | null;
  submission_uri: string | null;
  reviewer_notes: string | null;
  criteria_breakdown: Record<string, unknown> | null;
  // Workflow timestamps
  created_by: string | null;
  approved_by: string | null;
  approved_at: string | null;
  assigned_at: string | null;
  submitted_at: string | null;
  reviewed_at: string | null;
  created_at: string | null;
}

export interface BackendAssessmentResultRow {
  application_id: string;
  candidate_id: string | null;
  candidate_name: string | null;
  current_title: string | null;
  stage: string | null;
  status: "submitted" | "not_started";
  score: number | null;
  max_score: number | null;
  score_percent: number | null;
  summary: string | null;
  strengths: string[];
  areas_to_improve: string[];
  provisional: boolean;
  submitted_at: string | null;
  attempt_id: string | null;
}

export interface BackendAssessmentResults {
  job_id: string;
  has_assessment: boolean;
  template_title: string | null;
  submitted_count: number;
  total_count: number;
  results: BackendAssessmentResultRow[];
}

export interface BackendAssessmentGenerateDraftBody {
  job_id: string;
  assessment_type: AssessmentTypeValue;
  difficulty?: AssessmentDifficulty | null;
  question_count?: number | null;
  duration_minutes?: number | null;
  hr_instructions?: string | null;
  source_file_id?: string | null;
  candidate_instructions?: string | null;
}

export interface BackendAssessmentCreateBody {
  job_id: string;
  application_id?: string | null;
  candidate_id?: string | null;
  title?: string;
  assessment_type?: string;
  difficulty?: AssessmentDifficulty | null;
  duration_minutes?: number | null;
  total_score?: number | null;
  instructions?: string | null;
  max_score?: number | null;
}

export interface BackendAssessmentUpdateBody {
  title?: string;
  description?: string | null;
  status?: string;
  difficulty?: AssessmentDifficulty | null;
  duration_minutes?: number | null;
  total_score?: number | null;
  instructions?: string | null;
  questions?: BackendAssessmentQuestion[];
  agent_metadata?: Record<string, unknown>;
  score?: number | null;
  max_score?: number | null;
  reviewer_notes?: string | null;
  criteria_breakdown?: Record<string, unknown> | null;
  submission_text?: string | null;
  submission_uri?: string | null;
}

export interface BackendUploadSourceFileResponse {
  source_file_id: string;
  source_file_name: string;
  extracted_chars: number;
}

export const assessmentsApi = {
  list: (params?: {
    application_id?: string;
    candidate_id?: string;
    job_id?: string;
    status?: string;
    assessment_type?: string;
    limit?: number;
  }) => {
    const q = new URLSearchParams();
    if (params?.application_id) q.set("application_id", params.application_id);
    if (params?.candidate_id) q.set("candidate_id", params.candidate_id);
    if (params?.job_id) q.set("job_id", params.job_id);
    if (params?.status) q.set("status", params.status);
    if (params?.assessment_type) q.set("assessment_type", params.assessment_type);
    if (params?.limit) q.set("limit", String(params.limit));
    const qs = q.toString();
    return api.get<BackendAssessmentOut[]>(`/api/v1/assessments${qs ? `?${qs}` : ""}`);
  },
  listByJob: (jobId: string) =>
    api.get<BackendAssessmentOut[]>(`/api/v1/jobs/${encodeURIComponent(jobId)}/assessments`),
  listPublishedByJob: (jobId: string) =>
    api.get<BackendAssessmentOut[]>(
      `/api/v1/jobs/${encodeURIComponent(jobId)}/published-assessments`,
    ),
  resultsByJob: (jobId: string) =>
    api.get<BackendAssessmentResults>(
      `/api/v1/jobs/${encodeURIComponent(jobId)}/assessment-results`,
    ),
  get: (id: string) =>
    api.get<BackendAssessmentOut>(`/api/v1/assessments/${id}`),
  create: (body: BackendAssessmentCreateBody) =>
    api.post<BackendAssessmentOut>("/api/v1/assessments", body),
  generateDraft: (body: BackendAssessmentGenerateDraftBody) =>
    api.post<BackendAssessmentOut>("/api/v1/assessments/generate-draft", body),
  approve: (id: string, publish = true) =>
    api.post<BackendAssessmentOut>(
      `/api/v1/assessments/${encodeURIComponent(id)}/approve`,
      { publish },
    ),
  uploadSourceFile: async (file: File): Promise<BackendUploadSourceFileResponse> => {
    const fd = new FormData();
    fd.append("file", file);
    return api.postForm<BackendUploadSourceFileResponse>(
      "/api/v1/assessments/upload-source-file",
      fd,
    );
  },
  update: (id: string, body: BackendAssessmentUpdateBody) =>
    api.patch<BackendAssessmentOut>(`/api/v1/assessments/${id}`, body),
  delete: (id: string) =>
    api.delete<void>(`/api/v1/assessments/${id}`),
};

// ── Decision Support System ───────────────────────────────────────────────

export interface BackendDSSGenerateOut {
  packet_id: string;
  recommendation: string | null;
  final_journey_score: number | null;
}

export interface BackendDSSPacket {
  id?: string;
  packet_id?: string;
  application_id?: string;
  final_journey_score: number | null;
  recommendation: string | null;
  confidence?: number | null;
  compliance_status?: string | null;
  packet_json: Record<string, unknown> | null;
  evidence_json?: Record<string, unknown> | null;
  human_review_required?: boolean;
}

export interface BackendDSSEmail {
  email_id: string;
  email_type?: string;
  subject: string;
  body: string;
  status: string;
}

export interface BackendDSSDevPlan {
  plan_json: Record<string, unknown> | null;
  summary: string | null;
}

export interface BackendHrDecisionOut {
  id: string;
  final_hr_decision: string;
}

export const dssApi = {
  generate: (
    orgId: string,
    body: { application_id: string; candidate_id: string; job_id: string },
  ) =>
    api.post<BackendDSSGenerateOut>(
      `/api/v1/decision-support/generate?org_id=${orgId}`,
      body,
    ),
  getLatestForApplication: (applicationId: string, orgId: string) =>
    api.get<BackendDSSPacket>(
      `/api/v1/decision-support/applications/${applicationId}/latest?org_id=${orgId}`,
    ),
  getPacket: (packetId: string, orgId: string) =>
    api.get<BackendDSSPacket>(
      `/api/v1/decision-support/${packetId}?org_id=${orgId}`,
    ),
  hrDecision: (
    packetId: string,
    orgId: string,
    body: { final_decision: string; hr_notes?: string; override_reason?: string },
  ) =>
    api.post<BackendHrDecisionOut>(
      `/api/v1/decision-support/${packetId}/hr-decision?org_id=${orgId}`,
      body,
    ),
  generateDevPlan: (packetId: string, orgId: string) =>
    api.post<{ id: string; plan_type: string; plan_json: Record<string, unknown> }>(
      `/api/v1/decision-support/${packetId}/development-plan?org_id=${orgId}`,
      {},
    ),
  getDevPlan: (packetId: string, orgId: string) =>
    api.get<BackendDSSDevPlan>(
      `/api/v1/decision-support/${packetId}/development-plan?org_id=${orgId}`,
    ),
  generateEmail: (
    packetId: string,
    orgId: string,
    emailType: "acceptance" | "rejection",
  ) =>
    api.post<BackendDSSEmail>(
      `/api/v1/decision-support/${packetId}/generate-email?org_id=${orgId}&email_type=${emailType}`,
      {},
    ),
  getEmail: (packetId: string, orgId: string) =>
    api.get<BackendDSSEmail>(
      `/api/v1/decision-support/${packetId}/email?org_id=${orgId}`,
    ),
  patchEmail: (
    packetId: string,
    orgId: string,
    body: { subject?: string; body?: string },
  ) =>
    api.patch<{ ok: boolean }>(
      `/api/v1/decision-support/${packetId}/email?org_id=${orgId}`,
      body,
    ),
  approveEmail: (packetId: string, orgId: string) =>
    api.post<{ ok: boolean }>(
      `/api/v1/decision-support/${packetId}/email/approve?org_id=${orgId}`,
      {},
    ),
  sendEmail: (packetId: string, orgId: string) =>
    api.post<{ ok: boolean }>(
      `/api/v1/decision-support/${packetId}/email/send?org_id=${orgId}`,
      {},
    ),
  managerDecision: (
    packetId: string,
    orgId: string,
    body: {
      decision:
        | "accepted"
        | "rejected"
        | "request_more_interview"
        | "request_more_evidence";
      manager_notes?: string;
    },
  ) =>
    api.post<{
      ok: boolean;
      decision: string;
      decision_id: string;
      packet_id: string;
      development_plan_id: string | null;
      development_plan_error?: string;
    }>(
      `/api/v1/decision-support/${packetId}/manager-decision?org_id=${orgId}`,
      body,
    ),
  decisionReport: (packetId: string, orgId: string) =>
    api.get<BackendDecisionReport>(
      `/api/v1/decision-support/${packetId}/decision-report?org_id=${orgId}`,
    ),
  reportPdfUrl: (packetId: string, orgId: string) =>
    `/api/v1/decision-support/${packetId}/report/pdf?org_id=${orgId}`,
  /** Authenticated PDF fetch — returns a Blob the caller saves. A plain
   *  <a href> 404s (it hits the frontend origin) and carries no auth token. */
  downloadReportPdf: (packetId: string, orgId: string) =>
    api.getBlob(
      `/api/v1/decision-support/${packetId}/report/pdf?org_id=${orgId}`,
      { timeoutMs: 60_000 },
    ),
  /** HR scores the human-feedback rubric stage (0-100); recomputes the score. */
  setHumanFeedback: (
    packetId: string,
    orgId: string,
    body: { score: number; notes?: string },
  ) =>
    api.post<{
      ok: boolean;
      human_feedback_score: number;
      final_score: number | null;
      recommendation: string | null;
      confidence: number | null;
    }>(`/api/v1/decision-support/${packetId}/human-feedback?org_id=${orgId}`, body),
};

export interface BackendIdssV2 {
  version: "v2";
  final_score: number;
  recommendation: string;
  confidence: string;
  score_breakdown: Record<string, {
    score: number | null;
    weight: number;
    weighted_score: number;
    evidence: string[];
    missing: boolean;
    /**
     * Brief-mandated reason code so the UI can write a clear "missing
     * because X did not provide Y" sentence instead of blaming PATHS.
     * One of: ``available`` | ``missing_candidate_input`` |
     * ``missing_recruiter_input`` | ``missing_job_requirements`` |
     * ``missing_outreach_activity`` | ``not_applicable``.
     */
    missing_reason?: string;
    reasoning?: string;
  }>;
  weights: Record<string, number>;
  missing_evidence: string[];
  overrides_applied: string[];
  bias_guardrail_notes: string[];
  bias_risk: boolean;
  must_have_skills_missing: boolean;
  technical_role: boolean;
  agent_error: string | null;
  summary_for_hiring_manager: string;
  final_reasoning: string;
  strengths: string[];
  weaknesses: string[];
  risks: string[];
  recommended_next_action: string;
}

export interface BackendDecisionReport {
  packet_id: string;
  candidate: {
    id: string | null;
    full_name: string | null;
    current_title: string | null;
    skills: string[];
  };
  job: {
    id: string | null;
    title: string | null;
    seniority_level: string | null;
  };
  organization: { id: string | null; name: string | null };
  final_score: number | null;
  recommendation: string | null;
  confidence: number | null;
  human_review_required: boolean;
  compliance_status: string | null;
  packet_json: Record<string, unknown>;
  idss_v2: BackendIdssV2 | null;
  development_plan: {
    id: string;
    plan_type: string;
    status: string;
    summary: string | null;
    plan_json: Record<string, unknown>;
  } | null;
  email: {
    id: string;
    subject: string;
    body: string;
    status: string;
  } | null;
  per_stage_breakdown?: BackendPerStageBreakdown[];
  hr_decision?: {
    final_hr_decision: string | null;
    hr_notes: string | null;
    override_reason: string | null;
    decided_at: string | null;
  } | null;
}

export interface BackendPerStageBreakdown {
  key: string;
  kind: string;
  label: string;
  score: number | null;
  ai_explanation: string;
  hr_notes: string;
  status: string;
}

export interface BackendDevelopmentPlan {
  id: string;
  decision_packet_id: string;
  candidate_id: string;
  job_id: string;
  plan_type: string;
  status: string;
  summary: string | null;
  plan_json: Record<string, unknown>;
  created_at?: string | null;
}

export const developmentPlansApi = {
  generate: (
    orgId: string,
    body: { candidate_id: string; job_id: string; decision_id: string },
  ) =>
    api.post<{
      plan_id: string;
      plan_type: string;
      status: string;
      summary: string | null;
    }>(`/api/v1/development-plans/generate?org_id=${orgId}`, body),
  get: (planId: string, orgId: string) =>
    api.get<BackendDevelopmentPlan>(
      `/api/v1/development-plans/${planId}?org_id=${orgId}`,
    ),
  forCandidate: (candidateId: string, orgId: string) =>
    api.get<{ candidate_id: string; items: BackendDevelopmentPlan[] }>(
      `/api/v1/candidates/${candidateId}/development-plans?org_id=${orgId}`,
    ),
  approve: (planId: string, orgId: string, body?: { notes?: string }) =>
    api.post<BackendDevelopmentPlan>(
      `/api/v1/development-plans/${planId}/approve?org_id=${orgId}`,
      body ?? {},
    ),
  revise: (planId: string, orgId: string, body?: { notes?: string }) =>
    api.post<BackendDevelopmentPlan>(
      `/api/v1/development-plans/${planId}/revise?org_id=${orgId}`,
      body ?? {},
    ),
  setCandidateFeedback: (
    planId: string,
    orgId: string,
    body: { candidate_facing_message: string },
  ) =>
    api.post<BackendDevelopmentPlan>(
      `/api/v1/development-plans/${planId}/candidate-feedback?org_id=${orgId}`,
      body,
    ),
  sendFeedback: (
    planId: string,
    orgId: string,
    body?: { recipient_email?: string },
  ) =>
    api.post<BackendDevelopmentPlan>(
      `/api/v1/development-plans/${planId}/send-feedback?org_id=${orgId}`,
      body ?? {},
    ),
};

// ── Outreach Agent (Google + scheduling) ──────────────────────────────────

export interface BackendGoogleStatus {
  connected: boolean;
  configured: boolean;
  email: string | null;
  expires_at: string | null;
  scopes: string[];
  last_error: string | null;
}

export interface BackendGeneratedEmail {
  subject: string;
  body: string;
  model: string | null;
  fallback: boolean;
}

export interface BackendOutreachAvailabilityIn {
  day_of_week: number;
  start_time: string;
  end_time: string;
  timezone?: string;
}

export interface BackendOutreachCreateBody {
  candidate_id: string;
  job_id?: string | null;
  subject: string;
  email_body: string;
  interview_type?: string;
  duration_minutes?: number;
  buffer_minutes?: number;
  timezone?: string;
  expires_at?: string | null;
  availability?: BackendOutreachAvailabilityIn[];
  recipient_email?: string;
}

export interface BackendOutreachCreateResponse {
  session_id: string;
  status: string;
  booking_link: string;
  expires_at: string | null;
}

export interface BackendOutreachSendResponse {
  ok: boolean;
  session_id: string;
  status: string;
  error: string | null;
  gmail_message_id: string | null;
}

export interface BackendOutreachHistoryItem {
  id: string;
  candidate_id: string;
  job_id: string | null;
  status: string;
  subject: string | null;
  interview_type: string | null;
  sent_at: string | null;
  booked_at: string | null;
  expires_at: string | null;
  last_error: string | null;
  booking: {
    selected_start_time: string;
    selected_end_time: string;
    google_meet_link: string | null;
  } | null;
}

export interface BackendPublicSchedule {
  organization_name: string | null;
  job_title: string | null;
  candidate_name: string | null;
  interview_type: string | null;
  duration_minutes: number;
  timezone: string;
  expires_at: string | null;
  booked: boolean;
  slots: { start: string; end: string; timezone: string }[];
  booking: {
    selected_start_time: string;
    selected_end_time: string;
    timezone: string;
    google_meet_link: string | null;
    status: string;
  } | null;
}

export interface BackendBookSlotResponse {
  ok: boolean;
  error: string | null;
  booking_id: string | null;
  selected_start_time: string | null;
  selected_end_time: string | null;
  google_meet_link: string | null;
  google_connected: boolean;
}

export const googleIntegrationApi = {
  status: () => api.get<BackendGoogleStatus>("/api/v1/google-integration/status"),
  connect: () =>
    api.get<{ authorize_url: string }>("/api/v1/google-integration/connect"),
  disconnect: () =>
    api.post<{ ok: true }>("/api/v1/google-integration/disconnect"),
};

export const outreachAgentApi = {
  generateEmail: (body: {
    candidate_id: string;
    job_id?: string | null;
    interview_type?: string;
    is_final_offer?: boolean;
    extra_instructions?: string;
  }) => api.post<BackendGeneratedEmail>("/api/v1/outreach/generate-email", body),
  saveDraft: (body: BackendOutreachCreateBody) =>
    api.post<BackendOutreachCreateResponse>("/api/v1/outreach/save-draft", body),
  send: (body: BackendOutreachCreateBody) =>
    api.post<BackendOutreachSendResponse>("/api/v1/outreach/send", body),
  history: (candidateId: string) =>
    api.get<{ candidate_id: string; items: BackendOutreachHistoryItem[] }>(
      `/api/v1/outreach/${candidateId}/history`,
    ),
  // Complete-profile outreach: invite the candidate to create their own
  // account on PATHS. No booking link / availability / Google involved.
  profileCompletionGenerate: (body: { candidate_id: string }) =>
    api.post<{ subject: string; body: string; signup_url: string }>(
      "/api/v1/outreach/profile-completion/generate",
      body,
    ),
  profileCompletionSend: (body: {
    candidate_id: string;
    subject: string;
    body: string;
    recipient_email?: string;
  }) =>
    api.post<{ ok: boolean; provider?: string; recipient: string }>(
      "/api/v1/outreach/profile-completion/send",
      body,
    ),
};

// ── In-app context-aware assistant (floating support chatbot) ─────────────
export interface BackendAssistantMessage {
  role: "user" | "assistant";
  content: string;
  created_at?: string | null;
}

function assistantQuery(contextKey: string, entityId?: string | null): string {
  const parts = [`context_key=${encodeURIComponent(contextKey)}`];
  if (entityId) parts.push(`entity_id=${encodeURIComponent(entityId)}`);
  return parts.join("&");
}

export const assistantApi = {
  chat: (body: { context_key: string; entity_id?: string | null; message: string }) =>
    api.post<{ reply: string; context_key: string; entity_id?: string | null }>(
      "/api/v1/assistant/chat",
      body,
    ),
  history: (contextKey: string, entityId?: string | null) =>
    api.get<{
      context_key: string;
      entity_id?: string | null;
      items: BackendAssistantMessage[];
    }>(`/api/v1/assistant/history?${assistantQuery(contextKey, entityId)}`),
  clear: (contextKey: string, entityId?: string | null) =>
    api.delete<void>(
      `/api/v1/assistant/history?${assistantQuery(contextKey, entityId)}`,
    ),
};

export const publicSchedulingApi = {
  view: (token: string) =>
    api.get<BackendPublicSchedule>(`/api/v1/schedule/${encodeURIComponent(token)}`),
  book: (
    token: string,
    body: { selected_start_time: string; selected_end_time: string },
  ) =>
    api.post<BackendBookSlotResponse>(
      `/api/v1/schedule/${encodeURIComponent(token)}/book`,
      body,
    ),
};

// ── Interview Intelligence runtime (live Q&A) ─────────────────────────────

export interface BackendInterviewSessionDetail {
  session: {
    id: string;
    application_id: string;
    candidate_id: string;
    job_id: string;
    organization_id: string;
    interview_type: string;
    status: string;
    created_at: string | null;
  };
  candidate: {
    id: string | null;
    full_name: string | null;
    current_title: string | null;
    headline: string | null;
    skills: string[];
    summary: string | null;
    years_experience: number | null;
  };
  job: {
    id: string | null;
    title: string | null;
    summary: string | null;
    seniority_level: string | null;
    requirements: string | null;
  };
  questions: { text: string; category: string; pack_id?: string; order?: number; skills?: string[] }[];
  turns: BackendInterviewTurn[];
  completed: boolean;
}

export interface BackendInterviewTurn {
  index: number;
  question: string;
  answer: string;
  asked_at: string | null;
  answered_at: string | null;
  is_followup: boolean;
  parent_index: number | null;
}

export interface BackendInterviewHumanDecision {
  final_decision: string | null;
  hr_notes: string | null;
  decided_by: string | null;
  decided_at: string | null;
}

export interface BackendInterviewRecordingMeta {
  has_recording: boolean;
  recording_id: string | null;
  bot_id: string | null;
  status: string | null;
  status_message?: string | null;
  meeting_url: string | null;
  transcript_available: boolean;
}

export interface BackendInterviewReport {
  session_id: string;
  completed: boolean;
  interview_type: string | null;
  status: string | null;
  candidate: BackendInterviewSessionDetail["candidate"];
  job: BackendInterviewSessionDetail["job"];
  summary: Record<string, unknown> | null;
  evaluations: Record<string, unknown>[];
  decision_packet: Record<string, unknown> | null;
  turns: BackendInterviewTurn[];
  transcript_text: string | null;
  hr_notes: string | null;
  human_decision: BackendInterviewHumanDecision | null;
  recording: BackendInterviewRecordingMeta | null;
}

export interface BackendInterviewRecordingUrl {
  video_url: string | null;
  status: string | null;
  status_message?: string | null;
  has_recording: boolean;
  meeting_url: string | null;
}

export interface BackendCreateInterviewSessionBody {
  application_id?: string | null;
  candidate_id?: string | null;
  job_id?: string | null;
  organization_id?: string | null;
  interview_type?: "hr" | "technical" | "mixed";
  difficulty?: "junior" | "mid" | "senior" | null;
  num_questions?: number | null;
  follow_ups_enabled?: boolean;
  interview_mode?: "text" | "voice";
}

export const interviewRuntimeApi = {
  createSession: (body: BackendCreateInterviewSessionBody) =>
    api.post<{
      session_id: string;
      status: string;
      candidate_id: string;
      job_id: string;
      application_id: string;
    }>("/api/v1/interviews/sessions", body),
  getSession: (sessionId: string) =>
    api.get<BackendInterviewSessionDetail>(
      `/api/v1/interviews/sessions/${sessionId}`,
    ),
  generateQuestions: (interviewId: string, orgId: string, body?: {
    include_hr?: boolean;
    include_technical?: boolean;
    regenerate?: boolean;
  }) =>
    api.post<{ question_pack_ids: string[] }>(
      `/api/v1/interviews/${interviewId}/generate-questions?org_id=${orgId}`,
      body ?? { include_hr: true, include_technical: true, regenerate: false },
    ),
  recordAnswer: (
    sessionId: string,
    body: {
      question: string;
      answer: string;
      is_followup?: boolean;
      parent_index?: number | null;
    },
  ) =>
    api.post<BackendInterviewTurn>(
      `/api/v1/interviews/sessions/${sessionId}/answer`,
      body,
    ),
  generateFollowUp: (sessionId: string, parentIndex: number) =>
    api.post<{ question: string; parent_index: number }>(
      `/api/v1/interviews/sessions/${sessionId}/follow-up`,
      { parent_index: parentIndex },
    ),
  finish: (sessionId: string) =>
    api.post<{
      ok: boolean;
      status: string;
      turn_count: number;
      already_completed: boolean;
    }>(`/api/v1/interviews/sessions/${sessionId}/finish`),
  evaluate: (sessionId: string) =>
    api.post<Record<string, unknown>>(
      `/api/v1/interviews/sessions/${sessionId}/evaluate`,
    ),
  getReport: (sessionId: string) =>
    api.get<BackendInterviewReport>(
      `/api/v1/interviews/sessions/${sessionId}/report`,
    ),
  /** Lazily resolve a playable video URL for the meeting recording. */
  getRecording: (sessionId: string) =>
    api.get<BackendInterviewRecordingUrl>(
      `/api/v1/interviews/sessions/${sessionId}/recording`,
    ),
  reportPdfUrl: (sessionId: string) =>
    `/api/v1/interviews/sessions/${sessionId}/report/pdf`,
  /** Authenticated PDF fetch — returns a Blob the caller can save. */
  downloadReportPdf: (sessionId: string) =>
    api.getBlob(`/api/v1/interviews/sessions/${sessionId}/report/pdf`, {
      timeoutMs: 60_000,
    }),
};

// ── Find Talent (LinkedIn outbound sourcing + ranking) ─────────────────────

export type FindTalentSource = "linkedin" | "all";

export interface FindTalentRequest {
  query: string;
  source: FindTalentSource;
  job_id?: string | null;
  count?: number;
  location?: string | null;
  verify_open_to_work?: boolean;
}

export interface BackendFindTalentCandidate {
  rank: number;
  score: number;
  source: "linkedin" | "database";
  external_candidate_id: string | null;
  candidate_id: string | null;
  full_name: string | null;
  headline: string | null;
  current_title: string | null;
  current_company: string | null;
  location: string | null;
  profile_url: string | null;
  skills: string[];
  explanation: string;
  matched_skills: string[];
  missing_skills: string[];
  open_to_work: boolean;
  open_to_work_status: "verified" | "not_detected" | "unverified";
  open_to_work_evidence: string | null;
  import_status: string;
  imported_candidate_id: string | null;
}

export interface BackendFindTalentResponse {
  batch_id: string | null;
  job_id: string | null;
  provider_available: boolean;
  message: string | null;
  results: BackendFindTalentCandidate[];
}

export interface BackendImportExternalResponse {
  status: "imported" | "duplicate" | "already_imported";
  candidate_id: string;
  created_account: boolean;
  duplicate_detected: boolean;
  message: string;
}

export const sourceCandidateApi = {
  findTalent: (body: FindTalentRequest) =>
    api.post<BackendFindTalentResponse>(
      "/api/v1/recruiter/source-candidate/find-talent",
      {
        query: body.query,
        source: body.source,
        job_id: body.job_id ?? null,
        count: body.count ?? 8,
        location: body.location ?? null,
        verify_open_to_work: body.verify_open_to_work ?? true,
      },
      { timeoutMs: 300_000 },
    ),
  importExternal: (externalCandidateId: string) =>
    api.post<BackendImportExternalResponse>(
      `/api/v1/recruiter/source-candidate/external/${externalCandidateId}/import`,
    ),
};

// ── Interview Intelligence ─────────────────────────────────────────────────

export interface BackendInterviewScheduleOut {
  interview_id: string;
  status: string;
  meeting_url: string | null;
  meeting_provider: string | null;
  calendar_event_id: string | null;
  message: string | null;
}

export interface BackendInterviewListItem {
  interview_id: string;
  application_id: string;
  job_id: string | null;
  candidate_id: string | null;
  candidate_name: string;
  job_title: string;
  interview_type: string;
  status: string;
  scheduled_start: string | null;
  meeting_url: string | null;
  recommendation: string | null;
  final_score: number | null;
  confidence: number | null;
}

export interface BackendInterviewQuestionPack {
  id: string;
  question_pack_type: string;
  questions_json: Record<string, unknown> | null;
  approved_by_hr: boolean;
  approved_at: string | null;
}

export interface BackendInterviewAnalysis {
  interview_id: string;
  summary: {
    id: string;
    summary_json: Record<string, unknown>;
    created_at: string;
  } | null;
  hr_evaluation: {
    id: string;
    evaluation_type: string;
    score_json: Record<string, unknown> | null;
    recommendation: string | null;
    confidence: number | null;
    created_at: string;
  } | null;
  technical_evaluation: {
    id: string;
    evaluation_type: string;
    score_json: Record<string, unknown> | null;
    recommendation: string | null;
    confidence: number | null;
    created_at: string;
  } | null;
  decision_packet: {
    id: string;
    recommendation: string | null;
    final_score: number | null;
    confidence: number | null;
    decision_packet_json: Record<string, unknown> | null;
    human_review_required: boolean;
    created_at: string;
  } | null;
  compliance: Record<string, unknown>;
}

export interface BackendInterviewHumanDecisionOut {
  id: string;
  interview_id: string;
  final_decision: string;
  hr_notes: string | null;
  override_reason: string | null;
  decided_by?: string;
  created_at: string;
  candidate_id?: string | null;
  application_id?: string | null;
  job_id?: string | null;
  interview_status?: string | null;
}

export const interviewsApi = {
  list: (orgId: string, limit = 50) =>
    api.get<BackendInterviewListItem[]>(
      `/api/v1/interviews?org_id=${encodeURIComponent(orgId)}&limit=${limit}`,
    ),
  schedule: (body: {
    application_id: string;
    organization_id: string;
    interview_type: string;
    slot_start: string;
    slot_end: string;
    timezone?: string;
    participant_user_ids?: string[];
    meeting_provider?: string;
    manual_meeting_url?: string | null;
    create_calendar_event?: boolean;
  }) =>
    api.post<BackendInterviewScheduleOut>("/api/v1/interviews/schedule", body),
  getQuestions: (interviewId: string, orgId: string) =>
    api.get<{ interview_id: string; packs: BackendInterviewQuestionPack[] }>(
      `/api/v1/interviews/${interviewId}/questions?org_id=${orgId}`,
    ),
  generateQuestions: (
    interviewId: string,
    orgId: string,
    body: { include_hr?: boolean; include_technical?: boolean; regenerate?: boolean },
  ) =>
    api.post<{ question_pack_ids: string[] }>(
      `/api/v1/interviews/${interviewId}/generate-questions?org_id=${orgId}`,
      body,
    ),
  approveQuestions: (
    interviewId: string,
    orgId: string,
    body: { approved: boolean; edited_questions_json?: Record<string, unknown> | null },
  ) =>
    api.patch<{ ok: boolean }>(
      `/api/v1/interviews/${interviewId}/questions/approve?org_id=${orgId}`,
      body,
    ),
  uploadTranscript: (
    interviewId: string,
    orgId: string,
    body: {
      transcript_text: string;
      transcript_source?: string;
      language?: string;
      quality_hint?: string | null;
    },
  ) =>
    api.post<{ transcript_id: string }>(
      `/api/v1/interviews/${interviewId}/transcript?org_id=${orgId}`,
      body,
    ),
  analyze: (interviewId: string, orgId: string) =>
    api.post<BackendInterviewAnalysis>(
      `/api/v1/interviews/${interviewId}/analyze?org_id=${orgId}`,
      {},
    ),
  getSummary: (interviewId: string, orgId: string) =>
    api.get<{ id: string; summary_json: Record<string, unknown>; created_at: string }>(
      `/api/v1/interviews/${interviewId}/summary?org_id=${orgId}`,
    ),
  humanDecision: (
    interviewId: string,
    orgId: string,
    body: { final_decision: string; hr_notes?: string; override_reason?: string },
  ) =>
    api.post<BackendInterviewHumanDecisionOut>(
      `/api/v1/interviews/${interviewId}/human-decision?org_id=${orgId}`,
      body,
    ),
  cancel: (interviewId: string, orgId: string, reason?: string) =>
    api.patch<{ interview_id: string; status: string }>(
      `/api/v1/interviews/${interviewId}/cancel?org_id=${orgId}`,
      reason ? { reason } : {},
    ),
  reschedule: (
    interviewId: string,
    orgId: string,
    body: { new_start: string; new_end: string; timezone?: string },
  ) =>
    api.patch<{ interview_id: string; status: string }>(
      `/api/v1/interviews/${interviewId}/reschedule?org_id=${orgId}`,
      body,
    ),
  // PATHS.md §1 — has a proceed/reject decision already been taken?
  getDecisionState: (interviewId: string, orgId: string) =>
    api.get<{
      interview_id: string;
      status: string;
      decision_taken: boolean;
      final_decision: string | null;
      candidate_id: string;
    }>(`/api/v1/interviews/${interviewId}/decision-state?org_id=${orgId}`),
  // INST.md §8/§9 — persisted HR Notes (feed Run Analysis).
  getHrNotes: (interviewId: string, orgId: string) =>
    api.get<{ interview_id: string; hr_notes: string }>(
      `/api/v1/interviews/${interviewId}/hr-notes?org_id=${orgId}`,
    ),
  saveHrNotes: (interviewId: string, orgId: string, hrNotes: string) =>
    api.put<{ interview_id: string; hr_notes: string }>(
      `/api/v1/interviews/${interviewId}/hr-notes?org_id=${orgId}`,
      { hr_notes: hrNotes },
    ),
};

// ── Per-skill evidence (CV / GitHub / LinkedIn MCP tools) ────────────────

export interface SkillEvidenceSnippet {
  text: string;
  source_url: string | null;
  weight_hint?: number;
  metadata?: Record<string, unknown>;
}

export interface SkillEvidenceSource {
  source: "cv" | "github" | "linkedin";
  status: string;
  score: number | null;
  reasoning: string;
  snippets: SkillEvidenceSnippet[];
  source_url: string | null;
  weight: number;
  fallback?: boolean;
}

export interface SkillEvidenceItem {
  skill: string;
  aggregate_score: number;
  confidence: "high" | "medium" | "low";
  summary: string;
  last_refreshed_at: string | null;
  sources: SkillEvidenceSource[];
}

export interface SkillEvidenceList {
  candidate_id: string;
  items: SkillEvidenceItem[];
}

export interface SkillEvidenceProfileUrls {
  candidate_id: string;
  github: string | null;
  linkedin: string | null;
  portfolio: string | null;
}

export const skillEvidenceApi = {
  list: (candidateId: string) =>
    api.get<SkillEvidenceList>(
      `/api/v1/candidates/${candidateId}/skills/evidence`,
    ),
  refresh: (candidateId: string, body?: { skills?: string[]; max_skills?: number }) =>
    api.post<SkillEvidenceList>(
      `/api/v1/candidates/${candidateId}/skills/evidence/refresh`,
      body ?? {},
    ),
  getProfileUrls: (candidateId: string) =>
    api.get<SkillEvidenceProfileUrls>(
      `/api/v1/candidates/${candidateId}/skills/evidence/profile-urls`,
    ),
  setProfileUrls: (
    candidateId: string,
    body: { github?: string | null; linkedin?: string | null; portfolio?: string | null },
  ) =>
    api.put<SkillEvidenceProfileUrls>(
      `/api/v1/candidates/${candidateId}/skills/evidence/profile-urls`,
      body,
    ),
};

// ── Recall.ai notetaker bot ───────────────────────────────────────────────
//
// Two recording modes are supported and the HR user picks one before the
// bot is dispatched:
//   * "post_meeting"  — bot records, transcript is fetched after the call
//   * "real_time"     — bot streams transcript chunks live via SSE
//
// All endpoints are gated behind require_org_hr on the backend.

export type RecallRecordingMode = "post_meeting" | "real_time";

export interface BackendRecallState {
  interview_id: string;
  recording_mode: RecallRecordingMode | null;
  bot_id: string | null;
  recording_id: string | null;
  transcript_id: string | null;
  status: string | null;
  status_message: string | null;
  transcript_available: boolean;
  transcript_path: string | null;
  configured: boolean;
}

export interface BackendRecallTranscript {
  interview_id: string;
  status: string | null;
  // Recall's JSON schema — kept loose so a future schema bump doesn't break us.
  transcript_json: unknown | null;
  transcript_text: string;
  transcript_path: string | null;
  updated_at: string | null;
}

export const recallApi = {
  getState: (interviewId: string) =>
    api.get<BackendRecallState>(
      `/api/v1/interviews/${interviewId}/recall/state`,
    ),
  setMode: (interviewId: string, mode: RecallRecordingMode) =>
    api.put<BackendRecallState>(
      `/api/v1/interviews/${interviewId}/recall/recording-mode`,
      { mode },
    ),
  start: (interviewId: string) =>
    api.post<BackendRecallState>(
      `/api/v1/interviews/${interviewId}/recall/start`,
      {},
    ),
  stop: (interviewId: string) =>
    api.post<BackendRecallState>(
      `/api/v1/interviews/${interviewId}/recall/stop`,
      {},
    ),
  /** Pull current bot/recording/transcript state from Recall.ai and persist
   *  it. Use this when RECALL_PUBLIC_WEBHOOK_URL is blank — i.e. no
   *  automatic webhook delivery. Idempotent. */
  sync: (interviewId: string) =>
    api.post<BackendRecallState>(
      `/api/v1/interviews/${interviewId}/recall/sync`,
      {},
    ),
  getTranscript: (interviewId: string) =>
    api.get<BackendRecallTranscript>(
      `/api/v1/interviews/${interviewId}/recall/transcript`,
    ),
  /** Absolute SSE URL — EventSource can't set headers, so the token is
   *  passed as a query string. The backend validates it. */
  streamUrl: (interviewId: string, token: string) => {
    const base =
      process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "";
    return `${base}/api/v1/interviews/${encodeURIComponent(
      interviewId,
    )}/recall/stream?token=${encodeURIComponent(token)}`;
  },
};

// ── Organization Matching / Outreach ──────────────────────────────────────

export interface BackendMatchingShortlistItem {
  candidate_id: string;
  candidate_name: string | null;
  rank: number;
  score: number | null;
  match_score: number | null;
  matched_skills: string[];
  missing_skills: string[];
  explanation: string | null;
  ranking_id?: string;
  status?: string;
}

export interface BackendMatchingRun {
  matching_run_id?: string;
  id?: string;
  job_id?: string;
  top_k?: number;
  status?: string;
  total_candidates?: number;
  relevant_candidates?: number;
  scored_candidates?: number;
  shortlisted_candidates?: number;
  shortlist?: BackendMatchingShortlistItem[];
}

export interface BackendOutreachDraft {
  message_id: string;
  status: string;
  subject: string;
  body: string;
}

// ── Open-to-Work Candidate Sourcing ───────────────────────────────────────

export interface BackendSourcedSource {
  source: string;
  url: string | null;
  fetched_at: string | null;
}

export interface BackendSourcedCandidate {
  candidate_id: string;
  full_name: string | null;
  headline: string | null;
  current_title: string | null;
  location_text: string | null;
  years_experience: number | null;
  skills: string[];
  open_to_job_types: string[];
  open_to_workplace_settings: string[];
  desired_job_titles: string[];
  summary: string | null;
  status: string | null;
  source: BackendSourcedSource | null;
  open_to_work: boolean;
}

export interface BackendSourcedCandidateMatch {
  candidate_id: string;
  score: number;
  vector_score: number;
  skill_overlap_score: number;
  matched_skills: string[];
  missing_required_skills: string[];
  workplace_match: boolean;
  location_match: boolean;
  candidate: BackendSourcedCandidate;
  source: BackendSourcedSource | null;
}

export interface BackendCandidateJobReasoning {
  candidate_id: string;
  job_id: string;
  decision: "strong_match" | "potential_match" | "weak_match";
  overall_score: number;
  summary: string;
  strengths: string[];
  gaps: string[];
  red_flags: string[];
  recommended_next_step: string;
  model: string | null;
  fallback: boolean;
}

export interface BackendCandidateSourcingStatus {
  enabled: boolean;
  provider: string;
  interval_minutes: number;
  max_per_run: number;
  reasoning_enabled: boolean;
  reasoning_model: string;
  metadata: Record<string, unknown> | null;
}

export interface BackendSourcedCandidateListResponse {
  organization_id: string;
  total: number;
  items: BackendSourcedCandidate[];
  job_id: string | null;
  filters: Record<string, unknown>;
}

export interface BackendSourcedCandidateMatchListResponse {
  organization_id: string;
  job_id: string;
  total: number;
  top_k: number;
  items: BackendSourcedCandidateMatch[];
  filters: Record<string, unknown>;
}

export interface SourcedListFilters {
  title?: string;
  skills?: string[];
  location?: string;
  workplace?: string;
  employmentType?: string;
  minYearsExperience?: number;
  maxYearsExperience?: number;
  limit?: number;
  offset?: number;
}

export interface SourcedMatchFilters {
  topK?: number;
  location?: string;
  workplace?: string[];
  employmentType?: string[];
  minScore?: number;
}

function sourcedListQuery(f: SourcedListFilters = {}): string {
  const sp = new URLSearchParams();
  if (f.title?.trim()) sp.set("title", f.title.trim());
  if (f.location?.trim()) sp.set("location", f.location.trim());
  if (f.workplace?.trim()) sp.set("workplace", f.workplace.trim());
  if (f.employmentType?.trim()) sp.set("employment_type", f.employmentType.trim());
  if (f.minYearsExperience != null) sp.set("min_years_experience", String(f.minYearsExperience));
  if (f.maxYearsExperience != null) sp.set("max_years_experience", String(f.maxYearsExperience));
  if (f.limit != null) sp.set("limit", String(f.limit));
  if (f.offset != null) sp.set("offset", String(f.offset));
  for (const s of f.skills ?? []) {
    if (s.trim()) sp.append("skill", s.trim());
  }
  const q = sp.toString();
  return q ? `?${q}` : "";
}

function sourcedMatchQuery(f: SourcedMatchFilters = {}): string {
  const sp = new URLSearchParams();
  if (f.topK != null) sp.set("top_k", String(f.topK));
  if (f.location?.trim()) sp.set("location", f.location.trim());
  if (f.minScore != null) sp.set("min_score", String(f.minScore));
  for (const w of f.workplace ?? []) if (w.trim()) sp.append("workplace", w.trim());
  for (const e of f.employmentType ?? []) if (e.trim()) sp.append("employment_type", e.trim());
  const q = sp.toString();
  return q ? `?${q}` : "";
}

export interface BackendCandidateSourcingRunResult {
  source_platform: string;
  requested_limit: number;
  started_at: string;
  finished_at: string | null;
  fetched_count: number;
  valid_count: number;
  inserted_count: number;
  updated_count: number;
  skipped_count: number;
  failed_count: number;
  graph_synced_count: number;
  vector_synced_count: number;
  candidate_ids: string[];
  errors: string[];
  status: string;
}

export const sourcingApi = {
  status: () =>
    api.get<BackendCandidateSourcingStatus>(
      "/api/v1/organization-candidate-sourcing/status",
    ),
  runImport: (body: {
    limit?: number;
    provider?: string;
    keywords?: string[];
    location?: string;
  }) =>
    api.post<BackendCandidateSourcingRunResult>(
      "/api/v1/admin/candidate-sourcing/run-once",
      body,
    ),
  list: (filters: SourcedListFilters = {}) =>
    api.get<BackendSourcedCandidateListResponse>(
      `/api/v1/organization-candidate-sourcing/candidates${sourcedListQuery(filters)}`,
    ),
  matchForJob: (jobId: string, filters: SourcedMatchFilters = {}) =>
    api.get<BackendSourcedCandidateMatchListResponse>(
      `/api/v1/organization-candidate-sourcing/jobs/${jobId}/match${sourcedMatchQuery(filters)}`,
    ),
  explain: (jobId: string, candidateId: string) =>
    api.post<BackendCandidateJobReasoning>(
      `/api/v1/organization-candidate-sourcing/jobs/${jobId}/match/${candidateId}/explain`,
    ),
  shortlist: (
    jobId: string,
    body: { candidate_id: string; job_id: string; stage_code?: string; note?: string },
  ) =>
    api.post<{
      candidate_id: string;
      job_id: string;
      application_id: string | null;
      stage_code: string;
      overall_status: string;
      note: string | null;
      created: boolean;
    }>(`/api/v1/organization-candidate-sourcing/jobs/${jobId}/shortlist`, body),
};

// ── Candidate Job Description Analysis (fix8&9 Update 1) ────────────────

export interface BackendJdAnalysisResponse {
  overall_fit_score: number;
  summary: string;
  matching_skills: string[];
  missing_skills: string[];
  weak_skills: string[];
  experience_alignment: string;
  project_alignment: string;
  education_alignment: string;
  recommended_improvements: string[];
  interview_preparation: string[];
  learning_recommendations: string[];
  used_fallback: boolean;
  fallback_reason?: string | null;
}

// JD analysis + match explanation run an LLM; allow up to 5 minutes before
// the client gives up (covers the free-model fallback + backoff chain).
const AI_ANALYSIS_TIMEOUT_MS = 5 * 60 * 1000;

export interface BackendJdAnalysisHistoryItem {
  id: string;
  created_at: string;
  job_description_text: string;
  result: BackendJdAnalysisResponse;
}

export const candidateJdAnalysisApi = {
  analyze: (body: { job_description_text: string }) =>
    api.post<BackendJdAnalysisResponse>(
      "/api/v1/candidates/me/job-description-analysis",
      body,
      { timeoutMs: AI_ANALYSIS_TIMEOUT_MS },
    ),
  /** Saved JD analyses for the candidate — newest first. */
  list: () =>
    api.get<{ items: BackendJdAnalysisHistoryItem[] }>(
      "/api/v1/candidates/me/job-description-analyses",
    ),
};

// ── Candidate portal: top matching jobs + per-job explanation ───────────
export interface BackendMatchingJob {
  job_id: string;
  title: string;
  company_name: string | null;
  location_text: string | null;
  workplace_type: string | null;
  seniority_level: string | null;
  salary_text: string | null;
  match_score: number;
  matched_skills: string[];
  application_mode: string;
  external_apply_url: string | null;
  source_url: string | null;
  source: string | null;
  already_applied: boolean;
}

export const candidateMatchingApi = {
  topJobs: (params?: { minScore?: number; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.minScore != null) qs.set("min_score", String(params.minScore));
    if (params?.limit != null) qs.set("limit", String(params.limit));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return api.get<BackendMatchingJob[]>(
      `/api/v1/candidates/me/matching-jobs${suffix}`,
    );
  },
  explain: (jobId: string) =>
    api.post<BackendJdAnalysisResponse>(
      `/api/v1/candidates/me/matching-jobs/${encodeURIComponent(jobId)}/explain`,
      undefined,
      { timeoutMs: AI_ANALYSIS_TIMEOUT_MS },
    ),
  importFreshJobs: () =>
    api.post<{ imported: number; scraped: number; generated: number; source: string }>(
      "/api/v1/candidates/me/discover/import-fresh-jobs",
      undefined,
      { timeoutMs: 90_000 },
    ),
  myInterviews: () =>
    api.get<BackendCandidateInterview[]>("/api/v1/candidates/me/interviews"),
};

export interface BackendCandidateInterview {
  id: string;
  job_title: string | null;
  company_name: string | null;
  interview_type: string;
  status: string;
  scheduled_start_time: string | null;
  scheduled_end_time: string | null;
  timezone: string | null;
  meeting_url: string | null;
  meeting_provider: string | null;
}

// ── Matching workspace: semantic search + RAG test (fix7.md) ────────────

export type MatchingSourceFilter = "database" | "outbound" | "imported_csv" | "all";

export interface BackendSemanticSearchRow {
  candidate_id: string;
  anonymized_label: string;
  source: string;
  source_display: string;
  headline: string | null;
  current_title: string | null;
  semantic_score: number;
  confidence: number;
  matched_evidence: string[];
  missing_signals: string[];
  agent_explanation: string;
}

export interface BackendSemanticSearchResponse {
  query: string;
  source: MatchingSourceFilter;
  limit: number;
  semantic_search_used: boolean;
  agent_available: boolean;
  results: BackendSemanticSearchRow[];
}

export interface SemanticSearchRequest {
  query: string;
  source?: MatchingSourceFilter;
  limit?: number;
}

export interface BackendRagRubric {
  technical_fit: number;
  experience_fit: number;
  skill_evidence: number;
  project_portfolio_evidence: number;
  missing_requirements: number;
  risk_factors: number;
}

export interface BackendRagEvidenceItem {
  field: string;
  label: string;
  excerpt: string;
  relevance: number;
}

export interface BackendRagTestRow {
  candidate_id: string;
  anonymized_label: string;
  job_title: string | null;
  requirement_label: string;
  final_score: number;
  confidence: number;
  next_action: string;
  rubric: BackendRagRubric;
  agent_explanation: string;
  candidate_evidence_used: BackendRagEvidenceItem[];
  requirement_evidence_used: string[];
  missing_data: string[];
  used_agent_fallback: boolean;
}

export interface BackendRagTestResponse {
  tests: BackendRagTestRow[];
  agent_available: boolean;
  retrieval_used: boolean;
  requirement_label: string;
  job_title: string | null;
}

export interface RagTestRequest {
  candidate_ids: string[];
  job_id?: string | null;
  custom_requirements?: string | null;
  top_k_chunks?: number;
}

export const matchingWorkspaceApi = {
  semanticSearch: (body: SemanticSearchRequest) =>
    api.post<BackendSemanticSearchResponse>(
      "/api/v1/matching/semantic-search",
      body,
    ),
  ragTest: (body: RagTestRequest) =>
    api.post<BackendRagTestResponse>("/api/v1/matching/rag-test", body),
};

// ── Outreach search (fix4.md) ─────────────────────────────────────────────

export type OutreachSourceMode = "database" | "outbound";
export type OutreachConfidence = "high" | "medium" | "low";

export interface BackendOutreachShortlistRow {
  candidate_id: string;
  alias: string;
  source: OutreachSourceMode;
  match_score: number;
  confidence: OutreachConfidence;
  matched_skills: string[];
  missing_skills: string[];
  agent_explanation: string;
  confidence_rationale: string;
  risks_or_missing_evidence: string;
  used_fallback: boolean;
}

export interface BackendOutreachSearchResponse {
  source_mode: OutreachSourceMode;
  query: string;
  shortlist: BackendOutreachShortlistRow[];
  agent_available: boolean;
}

export interface OutreachSearchRequest {
  mode: OutreachSourceMode;
  query: string;
  top_k?: number;
  job_id?: string | null;
  required_skills?: string[];
  seniority_level?: string | null;
  workplace_type?: string | null;
}

export const outreachSearchApi = {
  search: (body: OutreachSearchRequest) =>
    api.post<BackendOutreachSearchResponse>("/api/v1/outreach/search", body),
};

// ── Organization Matching / Outreach ──────────────────────────────────────

export const orgMatchingApi = {
  databaseSearch: (body: {
    organization_id: string;
    top_k?: number;
    job: {
      title: string;
      description?: string;
      required_skills?: string[];
      nice_to_have_skills?: string[];
      seniority_level?: string;
      workplace_type?: string;
    };
  }) =>
    api.post<BackendMatchingRun>(
      "/api/v1/organization-matching/database-search",
      body,
    ),
  getRun: (runId: string) =>
    api.get<BackendMatchingRun>(
      `/api/v1/organization-matching/runs/${runId}`,
    ),
  getShortlist: (runId: string) =>
    api.get<{ shortlist: BackendMatchingShortlistItem[] }>(
      `/api/v1/organization-matching/runs/${runId}/shortlist`,
    ),
  approveOutreach: (
    runId: string,
    rankingId: string,
    body?: { booking_link?: string | null; deadline_days?: number | null },
  ) =>
    api.post<{ ok: boolean; booking_link?: string; deadline_days?: number }>(
      `/api/v1/organization-matching/runs/${runId}/shortlist/${rankingId}/approve-outreach`,
      body ?? {},
    ),
  generateDraft: (
    runId: string,
    rankingId: string,
    body?: { booking_link?: string | null; deadline_days?: number | null },
  ) =>
    api.post<BackendOutreachDraft>(
      `/api/v1/organization-matching/runs/${runId}/outreach/${rankingId}/generate-draft`,
      body ?? {},
    ),
  sendOutreach: (messageId: string, body: { recipient_email: string }) =>
    api.post<{ ok: boolean }>(
      `/api/v1/organization-matching/outreach/${messageId}/send`,
      body,
    ),
};

// ── Contact Enrichment ───────────────────────────────────────────────────

export interface BackendEnrichedContactOut {
  id: string;
  candidate_id: string;
  organization_id: string;
  contact_type: string;
  original_value: string;
  enriched_value: string | null;
  confidence: number;
  status: string;
  source: string;
  provenance: string | null;
  validated_at: string | null;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface BackendEnrichmentStatusOut {
  total: number;
  pending: number;
  approved: number;
  rejected: number;
  by_type: Record<string, number>;
  by_status: Record<string, number>;
}

export const contactEnrichmentApi = {
  status: () =>
    api.get<BackendEnrichmentStatusOut>("/api/v1/contact-enrichment/status"),
  list: (params?: { status?: string; contact_type?: string }) => {
    const sp = new URLSearchParams();
    if (params?.status) sp.set("status", params.status);
    if (params?.contact_type) sp.set("contact_type", params.contact_type);
    const q = sp.toString();
    return api.get<BackendEnrichedContactOut[]>(
      `/api/v1/contact-enrichment/contacts${q ? `?${q}` : ""}`,
    );
  },
  approve: (id: string, body?: { reviewer_name?: string }) =>
    api.post<BackendEnrichedContactOut>(
      `/api/v1/contact-enrichment/contacts/${id}/approve`,
      body ?? {},
    ),
  reject: (id: string, body?: { reviewer_name?: string }) =>
    api.post<BackendEnrichedContactOut>(
      `/api/v1/contact-enrichment/contacts/${id}/reject`,
      body ?? {},
    ),
  // Contact Finder — candidates in the interview process + enrichment.
  interviewCandidates: () =>
    api.get<ContactFinderCandidate[]>(
      "/api/v1/contact-enrichment/interview-candidates",
    ),
  enrichCandidate: (candidateId: string) =>
    api.post<ContactFinderEnrichResult>(
      `/api/v1/contact-enrichment/candidates/${candidateId}/enrich`,
      {},
    ),
};

export interface ContactFinderCandidate {
  candidate_id: string;
  name: string;
  current_title: string | null;
  email: string | null;
  phone: string | null;
  linkedin: string | null;
  github: string | null;
  portfolio: string | null;
  socials: { type: string; value: string }[];
  missing: string[];
  complete: boolean;
}

export interface ContactFinderEnrichResult {
  candidate: ContactFinderCandidate;
  found: string[];
  still_missing: string[];
  notes: string[];
}


// ── Candidate Sourcing & Pool ─────────────────────────────────────────────
//
// Backend: app/api/v1/candidate_sourcing.py — every endpoint is gated behind
// require_active_org_status, so org isolation is enforced server-side. The
// UI never sends organization_id — it is read from the JWT.

export type SourceTypeKey =
  | "paths_profile"
  | "sourced"
  | "company_uploaded"
  | "job_fair"
  | "ats_import"
  | "manual_add";

export interface SourceCatalogEntry {
  source_type: SourceTypeKey;
  label: string;
  description: string;
}
export interface SourceCatalogResponse {
  sources: SourceCatalogEntry[];
}

export interface OrgSourceSettings {
  organization_id: string;
  use_paths_profiles_default: boolean;
  use_sourced_candidates_default: boolean;
  use_uploaded_candidates_default: boolean;
  use_job_fair_candidates_default: boolean;
  use_ats_candidates_default: boolean;
  default_top_k: number;
  default_min_profile_completeness: number;
  default_min_evidence_confidence: number;
  updated_at: string | null;
  updated_by_user_id: string | null;
}

export interface OrgSourceSettingsUpdate {
  use_paths_profiles_default?: boolean;
  use_sourced_candidates_default?: boolean;
  use_uploaded_candidates_default?: boolean;
  use_job_fair_candidates_default?: boolean;
  use_ats_candidates_default?: boolean;
  default_top_k?: number;
  default_min_profile_completeness?: number;
  default_min_evidence_confidence?: number;
}

export interface SourceCountEntry {
  source_type: SourceTypeKey;
  label: string;
  count: number;
}
export interface SourceCountsResponse {
  organization_id: string;
  counts: SourceCountEntry[];
  total: number;
}

export interface JobPoolConfig {
  job_id: string;
  organization_id: string;
  use_paths_profiles: boolean;
  use_sourced_candidates: boolean;
  use_uploaded_candidates: boolean;
  use_job_fair_candidates: boolean;
  use_ats_candidates: boolean;
  top_k: number;
  min_profile_completeness: number;
  min_evidence_confidence: number;
  filters_json: Record<string, unknown> | null;
  updated_at: string | null;
}

export interface JobPoolConfigUpdate {
  use_paths_profiles?: boolean;
  use_sourced_candidates?: boolean;
  use_uploaded_candidates?: boolean;
  use_job_fair_candidates?: boolean;
  use_ats_candidates?: boolean;
  top_k?: number;
  min_profile_completeness?: number;
  min_evidence_confidence?: number;
  filters_json?: Record<string, unknown> | null;
}

export interface PoolPreview {
  job_id: string;
  organization_id: string;
  config_snapshot: Record<string, unknown>;
  source_breakdown: Partial<Record<SourceTypeKey, number>>;
  total_candidates_found: number;
  duplicates_removed: number;
  excluded_incomplete_profile: number;
  excluded_low_evidence: number;
  eligible_candidates: number;
}

export interface PoolBuildResult {
  pool_run_id: string;
  job_id: string;
  organization_id: string;
  eligible_candidates: number;
  excluded_candidates: number;
  duplicates_removed: number;
  source_breakdown: Partial<Record<SourceTypeKey, number>>;
  status: string;
}

export interface PoolRunSummary {
  pool_run_id: string;
  job_id: string;
  eligible_candidates: number;
  excluded_candidates: number;
  duplicates_removed: number;
  source_breakdown: Partial<Record<SourceTypeKey, number>> | null;
  status: string;
  created_at: string | null;
  completed_at: string | null;
}
export interface PoolRunListResponse {
  runs: PoolRunSummary[];
}

/** GET /api/v1/health — liveness (no auth). */
export interface BackendHealthResponse {
  status: string;
  app_name: string;
  environment: string;
}

export function getApiHealth(): Promise<BackendHealthResponse> {
  return api.get<BackendHealthResponse>("/api/v1/health");
}

export const candidateSourcingApi = {
  catalog: () =>
    api.get<SourceCatalogResponse>("/api/v1/candidate-source-catalog"),
  getSettings: () =>
    api.get<OrgSourceSettings>("/api/v1/organization/candidate-source-settings"),
  updateSettings: (body: OrgSourceSettingsUpdate) =>
    api.put<OrgSourceSettings>(
      "/api/v1/organization/candidate-source-settings",
      body,
    ),
  counts: () =>
    api.get<SourceCountsResponse>(
      "/api/v1/organization/candidate-source-counts",
    ),
  getJobPoolConfig: (jobId: string) =>
    api.get<JobPoolConfig>(
      `/api/v1/jobs/${encodeURIComponent(jobId)}/candidate-pool/config`,
    ),
  updateJobPoolConfig: (jobId: string, body: JobPoolConfigUpdate) =>
    api.put<JobPoolConfig>(
      `/api/v1/jobs/${encodeURIComponent(jobId)}/candidate-pool/config`,
      body,
    ),
  previewJobPool: (jobId: string) =>
    api.post<PoolPreview>(
      `/api/v1/jobs/${encodeURIComponent(jobId)}/candidate-pool/preview`,
      {},
    ),
  buildJobPool: (jobId: string) =>
    api.post<PoolBuildResult>(
      `/api/v1/jobs/${encodeURIComponent(jobId)}/candidate-pool/build`,
      {},
    ),
  listPoolRuns: (jobId: string) =>
    api.get<PoolRunListResponse>(
      `/api/v1/jobs/${encodeURIComponent(jobId)}/candidate-pool/runs`,
    ),
};

// ── Phase 1: Job Detail Hub ──────────────────────────────────────────────

export type PipelineStage =
  | "define" | "source" | "screen" | "shortlist"
  | "reveal" | "outreach" | "interview" | "evaluate" | "decide";

export interface BackendFairnessRubric {
  protected_attrs: Record<string, boolean>;
  disparate_impact_threshold: number;
  enabled: boolean;
}

export interface BackendStageStats {
  define: number; source: number; screen: number; shortlist: number;
  reveal: number; outreach: number; interview: number; evaluate: number; decide: number;
}

export interface BackendJobStats {
  total_candidates: number;
  by_stage: BackendStageStats;
}

export interface BackendSkillWeight { name: string; weight: number; }

export interface BackendJobDetail {
  id: string;
  title: string;
  department: string | null;
  location: string | null;
  employment_type: string | null;
  salary_min: number | null;
  salary_max: number | null;
  description: string | null;
  required_skills: BackendSkillWeight[];
  optional_skills: BackendSkillWeight[];
  status: string;
  posted_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  stats: BackendJobStats;
  fairness_rubric: BackendFairnessRubric | null;
  hiring_pipeline?: JobPipelineStage[];
}

export interface BackendStageCandidatePreview {
  id: string; name: string; score: number | null;
}

export interface BackendPipelineStage {
  key: PipelineStage;
  count: number;
  preview: BackendStageCandidatePreview[];
}

export interface BackendPipelineStages {
  stages: BackendPipelineStage[];
}

export interface BackendCandidateListItem {
  id: string;
  application_id: string;
  name: string;
  headline: string | null;
  overall_score: number | null;
  match_score: number | null;
  interview_score: number | null;
  decision_score: number | null;
  matched_skills?: string[];
  pipeline_stage: PipelineStage;
  source_channel: string | null;
  created_at: string | null;
}

export interface BackendCandidateList {
  items: BackendCandidateListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface JobCandidatesQuery {
  stage?: PipelineStage;
  min_score?: number;
  source?: string;
  q?: string;
  sort?: string;
  page?: number;
  page_size?: number;
}

export interface BackendScoreCriterion {
  criterion: string;
  score: number | null;
  weight: number | null;
  reasoning: string | null;
}

export interface BackendActivityEvent {
  type: string;
  at: string;
  actor: string;
  payload: Record<string, unknown>;
}

export interface BackendCandidateDetail {
  id: string;
  name: string;
  headline: string | null;
  location: string | null;
  email_masked: string | null;
  phone_masked: string | null;
  current_role: string | null;
  years_experience: number | null;
  overall_score: number | null;
  pipeline_stage: PipelineStage | null;
  cv: {
    experience: { company: string; title: string; start_date: string | null; end_date: string | null; description: string | null }[];
    education: { institution: string; degree: string | null; field: string | null; graduation_year: number | null }[];
    skills: { skill_id: string; proficiency: number | null }[];
    certifications: { name: string; issuer: string | null }[];
  };
  scores: BackendScoreCriterion[];
  activity: BackendActivityEvent[];
}

export interface FairnessRubricInput {
  protected_attrs: Record<string, boolean>;
  disparate_impact_threshold: number;
  enabled: boolean;
}

export async function getJobDetail(id: string): Promise<BackendJobDetail> {
  return api.get<BackendJobDetail>(`/api/v1/jobs/${encodeURIComponent(id)}/detail`);
}

export async function getJobPipelineStages(id: string): Promise<BackendPipelineStages> {
  return api.get<BackendPipelineStages>(`/api/v1/jobs/${encodeURIComponent(id)}/pipeline-stages`);
}

export async function getJobCandidates(id: string, q: JobCandidatesQuery = {}): Promise<BackendCandidateList> {
  const params = new URLSearchParams();
  if (q.stage) params.set("stage", q.stage);
  if (q.min_score != null) params.set("min_score", String(q.min_score));
  if (q.source) params.set("source", q.source);
  if (q.q) params.set("q", q.q);
  if (q.sort) params.set("sort", q.sort);
  if (q.page) params.set("page", String(q.page));
  if (q.page_size) params.set("page_size", String(q.page_size));
  const qs = params.toString();
  return api.get<BackendCandidateList>(`/api/v1/jobs/${encodeURIComponent(id)}/candidates${qs ? `?${qs}` : ""}`);
}

export async function moveApplicationStage(appId: string, stage: PipelineStage): Promise<{ id: string; stage: string; updated_at: string }> {
  return api.put(`/api/v1/candidate-applications/${encodeURIComponent(appId)}/stage`, { stage });
}

export async function putFairnessRubric(jobId: string, rubric: FairnessRubricInput) {
  return api.put(`/api/v1/jobs/${encodeURIComponent(jobId)}/fairness-rubric`, rubric);
}

export async function getCandidateDetail(candidateId: string, jobId?: string): Promise<BackendCandidateDetail> {
  const qs = jobId ? `?job_id=${encodeURIComponent(jobId)}` : "";
  return api.get<BackendCandidateDetail>(`/api/v1/candidates/${encodeURIComponent(candidateId)}/profile${qs}`);
}

// ── Screening Agent (Phase 2) ─────────────────────────────────────────────

export interface BackendScreeningResult {
  result_id: string;
  blind_label: string;
  rank_position: number | null;
  agent_score: number;
  vector_similarity_score: number;
  final_score: number;
  relevance_score: number | null;
  recommendation: string | null;
  match_classification: string | null;
  status: string;
}

export interface BackendScreeningRun {
  screening_run_id: string;
  organization_id: string;
  job_id: string;
  source: string;
  top_k: number;
  status: string;
  total_candidates_scanned: number;
  candidates_passed_filter: number;
  candidates_scored: number;
  candidates_failed: number;
  error_message: string | null;
  results?: BackendScreeningResult[];
}

export interface BackendBiasReportEntry {
  attribute_name: string;
  group_label: string;
  selection_count: number;
  total_count: number;
  selection_rate: number;
  disparate_impact_ratio: number | null;
  threshold: number;
  passed: boolean;
}

export interface BackendBiasReport {
  screening_run_id: string;
  job_id: string;
  organization_id: string;
  has_flags: boolean;
  flagged_attributes: string[];
  entries: BackendBiasReportEntry[];
}

export const screeningApi = {
  run: (jobId: string, body: { organization_id: string; top_k?: number; force_rescore?: boolean }) =>
    api.post<BackendScreeningRun>(`/api/v1/screening/jobs/${encodeURIComponent(jobId)}/screen`, body),
  getRun: (runId: string) =>
    api.get<BackendScreeningRun>(`/api/v1/screening/runs/${encodeURIComponent(runId)}`),
  getResults: (runId: string) =>
    api.get<{ screening_run_id: string; job_id: string; results: BackendScreeningResult[] }>(
      `/api/v1/screening/runs/${encodeURIComponent(runId)}/results`,
    ),
  getBiasReport: (runId: string) =>
    api.get<BackendBiasReport>(`/api/v1/screening/runs/${encodeURIComponent(runId)}/bias-report`),
};

// ── Analytics (Phase 2.5) ─────────────────────────────────────────────────

export interface BackendAnalyticsSummary {
  org_id: string;
  period_days: number;
  total_active_jobs: number;
  total_applications: number;
  total_screening_runs: number;
  total_candidates_screened: number;
  total_shortlisted: number;
  event_counts: { event_type: string; count: number }[];
  pipeline_funnel: { stage: string; count: number }[];
  generated_at: string;
}

export interface BackendBiasSummary {
  org_id: string;
  period_days: number;
  total_runs_checked: number;
  runs_with_flags: number;
  total_flags: number;
  attributes: {
    attribute_name: string;
    total_groups_checked: number;
    groups_flagged: number;
    min_disparate_impact_ratio: number | null;
    avg_disparate_impact_ratio: number | null;
  }[];
  generated_at: string;
}

export const analyticsApi = {
  summary: (days = 30) =>
    api.get<BackendAnalyticsSummary>(`/api/v1/analytics/summary?days=${days}`),
  biasSummary: (days = 30) =>
    api.get<BackendBiasSummary>(`/api/v1/analytics/bias-summary?days=${days}`),
};

// ── Agent Runs (Phase 2 completion / Phase 3) ──────────────────────────────

export interface BackendAgentRun {
  run_id: string;
  run_type: string;
  status: "queued" | "running" | "completed" | "failed";
  current_node: string | null;
  entity_type: string | null;
  entity_id: string | null;
  result_ref: Record<string, unknown> | null;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export const agentRunsApi = {
  get: (runId: string) =>
    api.get<BackendAgentRun>(`/api/v1/agent-runs/${encodeURIComponent(runId)}`),
  list: (orgId: string, params?: { run_type?: string; status?: string; limit?: number }) => {
    const qs = new URLSearchParams({ org_id: orgId });
    if (params?.run_type) qs.set("run_type", params.run_type);
    if (params?.status) qs.set("status", params.status);
    if (params?.limit) qs.set("limit", String(params.limit));
    return api.get<BackendAgentRun[]>(`/api/v1/agent-runs?${qs.toString()}`);
  },
};

// ── Sourcing Agent (Phase 3) ───────────────────────────────────────────────

export interface BackendPoolRun {
  pool_run_id: string;
  job_id: string;
  status: string;
  candidates_found: number;
  created_at: string;
}

export const sourcingAgentApi = {
  buildPool: (
    jobId: string,
    body: {
      organization_id: string;
      top_k?: number;
      min_score?: number;
      provider?: string;
      location_filter?: string | null;
      workplace_filter?: string[];
    },
  ) =>
    api.post<{ run_id: string; agent_run_id: string; message: string }>(
      `/api/v1/jobs/${encodeURIComponent(jobId)}/candidate-pool/build`,
      body,
    ),
  getPoolRuns: (jobId: string, orgId: string, limit = 10) =>
    api.get<BackendPoolRun[]>(
      `/api/v1/jobs/${encodeURIComponent(jobId)}/candidate-pool/runs?org_id=${orgId}&limit=${limit}`,
    ),
  recomputeDecision: (
    jobId: string,
    body: { organization_id: string; candidate_id: string; application_id?: string },
  ) =>
    api.post<{ agent_run_id: string; message: string }>(
      `/api/v1/jobs/${encodeURIComponent(jobId)}/decisions/recompute`,
      body,
    ),
};

// ── Billing types ──────────────────────────────────────────────────────────

export interface BackendPlan {
  id: string;
  name: string;
  code: string;
  price_monthly_cents: number;
  price_annual_cents: number;
  currency: string;
  limits: Record<string, number>;
  features: string[];
  is_public: boolean;
  stripe_price_id_monthly: string | null;
  stripe_price_id_annual: string | null;
}

export interface BackendSubscription {
  id: string;
  org_id: string;
  plan: BackendPlan | null;
  billing_cycle: string;
  status: string;
  trial_ends_at: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
}

export interface BackendInvoice {
  id: string;
  amount_cents: number;
  currency: string;
  status: string;
  pdf_url: string | null;
  period_start: string | null;
  period_end: string | null;
  paid_at: string | null;
  stripe_invoice_id: string | null;
}

export interface BackendUsage {
  org_id: string;
  period_start: string | null;
  period_end: string | null;
  cvs_processed: number;
  jobs_active: number;
  agent_runs: number;
  seats_used: number;
}

export const billingApi = {
  getPlans: () => api.get<BackendPlan[]>("/api/v1/billing/plans"),
  getSubscription: (orgId: string) =>
    api.get<BackendSubscription | null>(`/api/v1/billing/subscription?org_id=${orgId}`),
  getInvoices: (orgId: string) =>
    api.get<BackendInvoice[]>(`/api/v1/billing/invoices?org_id=${orgId}`),
  getUsage: (orgId: string) =>
    api.get<BackendUsage>(`/api/v1/billing/usage?org_id=${orgId}`),
  createCheckoutSession: (orgId: string, planCode: string, billingCycle: "monthly" | "annual") =>
    api.post<{ checkout_url: string }>(
      `/api/v1/billing/checkout-session?org_id=${orgId}`,
      { plan_code: planCode, billing_cycle: billingCycle },
    ),
  getCustomerPortalUrl: (orgId: string) =>
    api.post<{ portal_url: string }>(`/api/v1/billing/customer-portal?org_id=${orgId}`, {}),
};

// ── Public API types ────────────────────────────────────────────────────────

export interface BackendPublicPlan {
  id: string;
  name: string;
  code: string;
  price_monthly_cents: number;
  price_annual_cents: number;
  currency: string;
  limits: Record<string, number>;
  features: string[];
}

export interface BackendPlatformStats {
  orgs_count: number;
  cvs_processed: number;
  active_jobs: number;
  placements: number;
}

export interface BackendPublicJob {
  id: string;
  slug: string;
  title: string;
  company: string;
  location: string;
  work_mode: string | null;
  employment_type: string | null;
  salary_min: number | null;
  salary_max: number | null;
  currency: string | null;
  level: string | null;
  description_preview: string | null;
  date_posted: string | null;
  valid_through: string | null;
}

export interface BackendPublicJobDetail extends BackendPublicJob {
  description_full: string | null;
  required_skills: string[];
  preferred_skills: string[];
}

export const publicApi = {
  getPlatformStats: () => api.get<BackendPlatformStats>("/api/v1/public/platform-stats"),
  getPublicPlans: () => api.get<BackendPublicPlan[]>("/api/v1/public/plans"),
  getPublicJobs: (params?: { q?: string; location?: string; work_mode?: string; page?: number }) => {
    const qs = new URLSearchParams();
    if (params?.q) qs.set("q", params.q);
    if (params?.location) qs.set("location", params.location);
    if (params?.work_mode) qs.set("work_mode", params.work_mode);
    if (params?.page) qs.set("page", String(params.page));
    return api.get<BackendPublicJob[]>(`/api/v1/public/jobs?${qs}`);
  },
  getPublicJob: (slug: string) =>
    api.get<BackendPublicJobDetail>(`/api/v1/public/jobs/${encodeURIComponent(slug)}`),
};

// ── Auth (forgot/reset password) ────────────────────────────────────────────

export const authExtApi = {
  forgotPassword: (email: string) =>
    api.post<{ detail: string }>("/api/v1/auth/forgot-password", { email }),
  resetPassword: (token: string, newPassword: string) =>
    api.post<{ detail: string }>("/api/v1/auth/reset-password", {
      token,
      new_password: newPassword,
    }),
};

// ── Preparation Agent (fix3.md §5) ─────────────────────────────────────────

export type PreparationOutputType =
  | "pre_analysis"
  | "technical_questions"
  | "hr_questions"
  | "assessment";

export interface PreparationGenerateResponse {
  candidate_id: string;
  job_id: string | null;
  output_type: PreparationOutputType;
  content: Record<string, unknown>;
}

export interface PreparationSavedDraft {
  content: Record<string, unknown>;
  updated_at: string | null;
  job_id: string | null;
}

export interface PreparationListResponse {
  candidate_id: string;
  drafts: Partial<Record<PreparationOutputType, PreparationSavedDraft>>;
}

export const preparationApi = {
  generate: (
    candidateId: string,
    output_type: PreparationOutputType,
    job_id?: string,
  ) =>
    api.post<PreparationGenerateResponse>(
      `/api/v1/candidates/${candidateId}/preparation/generate`,
      { output_type, job_id: job_id ?? null },
    ),
  /** Saved drafts (persisted) for a candidate — shown on load. */
  list: (candidateId: string, job_id?: string) =>
    api.get<PreparationListResponse>(
      `/api/v1/candidates/${candidateId}/preparation${job_id ? `?job_id=${encodeURIComponent(job_id)}` : ""}`,
    ),
};

// ── Candidate CSV import + Incomplete profiles (fix2.md §3, §5, §7) ────────

export interface CandidateCsvImportResult {
  ok: boolean;
  import_id: string;
  source_type: string;
  total_rows: number;
  valid_rows: number;
  imported: number;
  updated: number;
  failed: number;
  candidate_ids: string[];
}

export interface IncompleteProfileItem {
  candidate_id: string;
  name: string;
  email: string;
  source: string | null;
  current_title: string;
  missing: string[];
  completion: number;
}

export interface IncompleteProfilesList {
  items: IncompleteProfileItem[];
  total: number;
}

export const candidateImportApi = {
  /** Upload a CSV that contains candidate rows (optionally with `cv_url`).
   *  `sourceType` lets the caller distinguish `job_fair` imports from
   *  generic `company_uploaded` ones — the backend tags the imported
   *  candidate records with this value so the UI can show a badge. */
  importCsv: async (
    csv: File,
    sourceType: "company_uploaded" | "job_fair" = "company_uploaded",
  ): Promise<CandidateCsvImportResult> => {
    const fd = new FormData();
    fd.append("csv_file", csv);
    fd.append("source_type", sourceType);
    return api.postForm<CandidateCsvImportResult>(
      "/api/v1/candidates/import-csv",
      fd,
    );
  },
  /** Candidates with missing important fields (for the Incomplete Profiles
   *  section under /candidates/sources). */
  listIncomplete: (limit = 100) =>
    api.get<IncompleteProfilesList>(`/api/v1/candidates/incomplete?limit=${limit}`),
};

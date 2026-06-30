/**
 * PATHS — TanStack Query hooks.
 *
 * All hooks return frontend types (camelCase). Backend responses are adapted
 * through the adapters layer so pages never see snake_case or backend shapes.
 *
 * Org/recruiter data: always call the real API. The client defaults
 * NEXT_PUBLIC_API_URL to http://localhost:8001; unreachable backends surface
 * via TanStack Query error states (no silent empty fallbacks).
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import {
  billingApi,
  publicApi,
  authExtApi,
  type BackendPlan,
  type BackendSubscription,
  type BackendInvoice,
  type BackendUsage,
  type BackendPublicPlan,
  type BackendPublicJob,
  type BackendPublicJobDetail,
  type BackendPlatformStats,
  jobsApi,
  type JobsListFilters,
  applicationsApi,
  approvalsApi,
  membersApi,
  auditApi as backendAuditApi,
  dashboardApi as backendDashboardApi,
  evidenceApi,
  biasFairnessApi,
  candidatePortalApi,
  publicJobsApi,
  cvIngestionApi,
  organizationApi,
  recruitCandidatesApi,
  dssApi,
  interviewsApi,
  orgMatchingApi,
  outreachSearchApi,
  type OutreachSearchRequest,
  matchingWorkspaceApi,
  type SemanticSearchRequest,
  type RagTestRequest,
  candidateJdAnalysisApi,
  candidateMatchingApi,
  sourcingApi,
  type SourcedListFilters,
  type SourcedMatchFilters,
  googleIntegrationApi,
  outreachAgentApi,
  publicSchedulingApi,
  assessmentsApi,
  type BackendOutreachCreateBody,
  interviewRuntimeApi,
  type BackendCreateInterviewSessionBody,
  sourceCandidateApi,
  type FindTalentRequest,
  contactEnrichmentApi,
  kbApi,
  type BackendQdrantCollection,
  getApiHealth,
  type BackendJob,
  type BackendJobWriteBody,
} from "@/lib/api";

import type {
  BackendDSSPacket,
  BackendDSSEmail,
  BackendDSSDevPlan,
  BackendInterviewAnalysis,
  BackendMatchingRun,
  BackendRoadmap,
} from "@/lib/api";

import {
  adaptJobs,
  adaptJob,
  adaptApplications,
  adaptShortlist,
  adaptApprovals,
  adaptApproval,
  adaptDashboardStats,
  adaptFunnel,
  adaptAgents,
  adaptAuditEvents,
  adaptMembers,
  adaptOrganizationFromBackend,
  adaptRecruiterCandidateDetail,
} from "@/lib/api/adapters";

import type { CandidateProfile } from "@/types/candidate-profile.types";
import { adaptBackendCandidateProfileOut } from "@/lib/candidate/portal-profile";

import { useAuthStore } from "@/lib/stores/auth.store";

/** Recruiter/org routes: always call the API. */
async function orgEntityQuery<T>(real: () => Promise<T>): Promise<T> {
  return real();
}

/** Candidate portal: always call the API. */
async function portalQuery<T>(real: () => Promise<T>): Promise<T> {
  return real();
}

type PortalApplicationRow = {
  id: string;
  jobTitle: string;
  companyName: string;
  location: string;
  workMode: "remote" | "hybrid" | "onsite";
  status: "applied" | "screening" | "interview" | "offered" | "rejected" | "withdrawn";
  appliedAt: string;
  matchScore?: number;
  stage: string;
  hasAssessment: boolean;
  assessmentStatus: "not_started" | "submitted" | "none";
  assessmentScorePercent: number | null;
  roadmap?: BackendRoadmap;
};

function normalizeWorkMode(v: string | null | undefined): "remote" | "hybrid" | "onsite" {
  const x = (v ?? "onsite").toLowerCase();
  if (x === "remote" || x === "hybrid" || x === "onsite") return x;
  return "onsite";
}

function normalizeAppStatus(raw: string): PortalApplicationRow["status"] {
  const s = raw.toLowerCase().replace(/[\s-]+/g, "_");
  const allowed = new Set<PortalApplicationRow["status"]>([
    "applied",
    "screening",
    "interview",
    "offered",
    "rejected",
    "withdrawn",
  ]);
  return allowed.has(s as PortalApplicationRow["status"])
    ? (s as PortalApplicationRow["status"])
    : "applied";
}

// ── Candidate hooks ────────────────────────────────────────────────────────

export const useCandidates = () =>
  useQuery({
    queryKey: ["candidates"],
    queryFn: () => orgEntityQuery(async () => []),
  });

export const useCandidate = (id: string) =>
  useQuery({
    queryKey: ["candidates", id],
    queryFn: async () =>
      adaptRecruiterCandidateDetail(
        (await recruitCandidatesApi.get(id)) as unknown as Parameters<
          typeof adaptRecruiterCandidateDetail
        >[0],
      ),
    enabled: Boolean(id),
  });

export const useCandidateSearch = (query: string) =>
  useQuery({
    queryKey: ["candidates", "search", query],
    queryFn: async () => [],
    enabled: query.length > 1,
    staleTime: 10_000,
  });

// ── Job hooks ─────────────────────────────────────────────────────────────

export type { JobsListFilters };

export const useJobs = (filters: JobsListFilters = {}) =>
  useQuery({
    queryKey: [
      "jobs",
      filters.activeOnly ?? false,
      filters.keyword ?? "",
      filters.location ?? "",
      filters.source ?? "",
      filters.company ?? "",
      filters.status ?? "",
      filters.remote ?? null,
      filters.employmentType ?? "",
      filters.limit ?? null,
      filters.offset ?? null,
    ],
    queryFn: () =>
      orgEntityQuery(async () => adaptJobs(await jobsApi.list(filters))),
  });

export const useJobImportStatus = () =>
  useQuery({
    queryKey: ["jobs", "import-status"],
    queryFn: () => orgEntityQuery(() => jobsApi.importStatus()),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });

export const useRunJobImport = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      keyword?: string;
      location?: string;
      limit?: number;
      source?: string;
    }) => jobsApi.runImport(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["jobs", "import-status"] });
    },
  });
};

export const useJob = (id: string) =>
  useQuery({
    queryKey: ["jobs", id],
    queryFn: async () => adaptJob(await jobsApi.get(id)),
    enabled: Boolean(id),
  });

// ── Application hooks ─────────────────────────────────────────────────────

export const useApplications = () =>
  useQuery({
    queryKey: ["applications"],
    queryFn: () =>
      orgEntityQuery(async () =>
        adaptApplications(await applicationsApi.list()),
      ),
  });

export const useApplicationsByJob = (jobId: string) =>
  useQuery({
    queryKey: ["applications", "job", jobId],
    queryFn: () =>
      orgEntityQuery(async () =>
        adaptApplications(await applicationsApi.listByJob(jobId)),
      ),
    enabled: Boolean(jobId),
  });

export const useShortlist = (jobId: string) =>
  useQuery({
    queryKey: ["shortlist", jobId],
    queryFn: () =>
      orgEntityQuery(async () =>
        adaptShortlist(await applicationsApi.shortlist(jobId), jobId),
      ),
    enabled: Boolean(jobId),
  });

export const useApplication = (id: string) =>
  useQuery({
    queryKey: ["applications", id],
    queryFn: async () => adaptApplications([await applicationsApi.get(id)])[0],
    enabled: Boolean(id),
  });

export const useAdvanceStage = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, stage, reason }: { id: string; stage: string; reason?: string }) =>
      applicationsApi.advanceStage(id, stage, reason),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["applications"] });
      qc.invalidateQueries({ queryKey: ["shortlist"] });
    },
  });
};

// ── Approval hooks ────────────────────────────────────────────────────────

export const useApprovals = (statusFilter?: string) =>
  useQuery({
    queryKey: ["approvals", statusFilter ?? "all"],
    queryFn: () =>
      orgEntityQuery(async () =>
        adaptApprovals(await approvalsApi.list(statusFilter)),
      ),
  });

export const usePendingApprovals = () =>
  useQuery({
    queryKey: ["approvals", "pending"],
    queryFn: () =>
      orgEntityQuery(async () =>
        adaptApprovals(await approvalsApi.pending()),
      ),
    refetchInterval: 30_000,
  });

export const useDecideApproval = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      decision,
      reason,
    }: {
      id: string;
      decision: "approved" | "rejected";
      reason?: string;
    }) => approvalsApi.decide(id, decision, reason).then(adaptApproval),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["approvals"] });
    },
  });
};

// ── Member hooks ──────────────────────────────────────────────────────────

export const useMembers = () =>
  useQuery({
    queryKey: ["members"],
    queryFn: () =>
      orgEntityQuery(async () => adaptMembers(await membersApi.list())),
  });

export const useInviteMember = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      orgId: string;
      full_name: string;
      email: string;
      password: string;
      role_code: string;
    }) =>
      membersApi.invite(data.orgId, {
        full_name: data.full_name,
        email: data.email,
        password: data.password,
        role_code: data.role_code,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["members"] });
    },
  });
};

// fix8&9 — resend invitation email for a pending member
export const useResendInvite = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: {
      orgId: string;
      membershipId: string;
      temporaryPassword?: string;
    }) =>
      membersApi.resendInvite(vars.orgId, vars.membershipId, {
        temporary_password: vars.temporaryPassword ?? null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["members"] });
    },
  });
};

// fix8&9 — remove a member from the org
export const useRemoveMember = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { orgId: string; membershipId: string }) =>
      membersApi.remove(vars.orgId, vars.membershipId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["members"] });
    },
  });
};

// ── Organization hook ─────────────────────────────────────────────────────

export const useOrganization = () =>
  useQuery({
    queryKey: ["organization"],
    queryFn: () =>
      orgEntityQuery(async () =>
        adaptOrganizationFromBackend(await organizationApi.getMe()),
      ),
  });

// ── Audit hooks ───────────────────────────────────────────────────────────

export const useAuditEvents = (search?: string) =>
  useQuery({
    queryKey: ["audit", search ?? ""],
    queryFn: () =>
      orgEntityQuery(async () =>
        adaptAuditEvents(await backendAuditApi.list(search)),
      ),
  });

// ── Dashboard hooks ───────────────────────────────────────────────────────

export const useDashboardStats = () =>
  useQuery({
    queryKey: ["dashboard", "stats"],
    queryFn: () =>
      orgEntityQuery(async () =>
        adaptDashboardStats(await backendDashboardApi.stats()),
      ),
  });

export const useFunnelData = () =>
  useQuery({
    queryKey: ["dashboard", "funnel"],
    queryFn: () =>
      orgEntityQuery(async () =>
        adaptFunnel(await backendDashboardApi.funnel()),
      ),
  });

export const useWeeklyApplications = () =>
  useQuery({
    queryKey: ["dashboard", "weekly"],
    queryFn: () =>
      orgEntityQuery(async () => backendDashboardApi.weekly()),
  });

export const useAgentStatus = () =>
  useQuery({
    queryKey: ["agents"],
    queryFn: () =>
      orgEntityQuery(async () =>
        adaptAgents(await backendDashboardApi.agents()),
      ),
    refetchInterval: 15_000,
  });

/** GET /api/v1/health — connectivity check (no auth). */
export const useApiHealth = () =>
  useQuery({
    queryKey: ["health", "api"],
    queryFn: () => getApiHealth(),
    staleTime: 0,
    retry: 2,
  });

// ── Evidence hooks ────────────────────────────────────────────────────────

export const useEvidenceItems = (candidateId: string, type?: string) =>
  useQuery({
    queryKey: ["evidence", candidateId, type ?? "all"],
    queryFn: () => evidenceApi.listItems(candidateId, type),
    enabled: Boolean(candidateId),
    retry: 1,
  });

export const useCandidateSources = (candidateId: string) =>
  useQuery({
    queryKey: ["candidate-sources", candidateId],
    queryFn: () => evidenceApi.listSources(candidateId),
    enabled: Boolean(candidateId),
    retry: 1,
  });

// ── Bias & Fairness hooks ─────────────────────────────────────────────────

export const useDeanonStatus = (candidateId: string) =>
  useQuery({
    queryKey: ["deanon-status", candidateId],
    queryFn: () => biasFairnessApi.getDeanonStatus(candidateId),
    enabled: Boolean(candidateId),
    retry: 1,
    staleTime: 60_000,
  });

export const useRequestDeanon = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      candidateId,
      purpose,
    }: {
      candidateId: string;
      purpose?: string;
    }) => biasFairnessApi.requestDeanon(candidateId, purpose),
    onSuccess: (_data, { candidateId }) => {
      qc.invalidateQueries({ queryKey: ["deanon-status", candidateId] });
      qc.invalidateQueries({ queryKey: ["approvals"] });
    },
  });
};

export const useProposeShortlist = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => biasFairnessApi.proposeShortlist(jobId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["approvals"] });
    },
  });
};

export const useBiasFlags = (params?: { status?: string; scope?: string; limit?: number }) =>
  useQuery({
    queryKey: ["bias-flags", params],
    queryFn: () => biasFairnessApi.listBiasFlags(params),
  });

export const useBiasAudit = (params?: { event_type?: string; candidate_id?: string; limit?: number }) =>
  useQuery({
    queryKey: ["bias-audit", params],
    queryFn: () => biasFairnessApi.readBiasAudit(params),
  });

export const useAnonymizedView = (candidateId: string) =>
  useQuery({
    queryKey: ["anonymized-view", candidateId],
    queryFn: () => biasFairnessApi.getAnonymizedView(candidateId),
    enabled: Boolean(candidateId),
  });

// ── Candidate Portal hooks ────────────────────────────────────────────────

export const useCandidateProfile = () =>
  useQuery({
    queryKey: ["candidate-profile"],
    queryFn: () =>
      portalQuery(async () =>
        adaptBackendCandidateProfileOut(await candidatePortalApi.getProfile()),
      ),
    staleTime: 60_000,
  });

export const useUpdateCandidateProfile = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Parameters<typeof candidatePortalApi.updateProfile>[0]) =>
      candidatePortalApi.updateProfile(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["candidate-profile"] });
      // Skills / role changed → Learning Hub recommendations + scores are stale.
      qc.invalidateQueries({ queryKey: ["candidate", "learning-hub"] });
    },
  });
};

export const useMyDevelopmentPlan = () =>
  useQuery({
    queryKey: ["candidate", "development-plan"],
    queryFn: () => candidatePortalApi.getDevelopmentPlan(),
    staleTime: 30_000,
  });

export const useUpdateMyDevelopmentProgress = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      plan_id: string;
      item_id: string;
      status: "todo" | "in_progress" | "done";
    }) => candidatePortalApi.updateDevelopmentProgress(body),
    onSuccess: (data) => {
      qc.setQueryData(["candidate", "development-plan"], data);
    },
  });
};

export const useApplicationInterview = (
  appId: string,
  enabled: boolean,
  kind?: string,
) =>
  useQuery({
    queryKey: ["candidate", "app-interview", appId, kind ?? "any"],
    queryFn: () => candidatePortalApi.getApplicationInterview(appId, kind),
    enabled: Boolean(appId) && enabled,
  });

export const useApplicationRanking = (appId: string, enabled: boolean) =>
  useQuery({
    queryKey: ["candidate", "app-ranking", appId],
    queryFn: () => candidatePortalApi.getApplicationRanking(appId),
    enabled: Boolean(appId) && enabled,
  });

export const useApplicationFit = (appId: string, enabled: boolean) =>
  useQuery({
    queryKey: ["candidate", "app-fit", appId],
    queryFn: () => candidatePortalApi.getApplicationFit(appId),
    enabled: Boolean(appId) && enabled,
    staleTime: 60_000,
  });

export const useApplicationJourney = (appId: string, enabled: boolean) =>
  useQuery({
    queryKey: ["candidate", "app-journey", appId],
    queryFn: () => candidatePortalApi.getApplicationJourney(appId),
    enabled: Boolean(appId) && enabled,
  });

export const useCandidateApplications = () =>
  useQuery({
    queryKey: ["candidate-applications"],
    queryFn: () =>
      portalQuery(async () => {
        const apps = await candidatePortalApi.getApplications();
        return apps.map(
          (app): PortalApplicationRow => ({
            id: app.id,
            jobTitle: app.job_title ?? "Unknown Position",
            companyName: app.company_name ?? "",
            location: app.location_text ?? "",
            workMode: normalizeWorkMode(app.workplace_type),
            status: normalizeAppStatus(app.overall_status ?? app.current_stage_code),
            appliedAt: app.created_at,
            matchScore: app.match_score ?? undefined,
            stage:
              app.current_stage_code.charAt(0).toUpperCase() +
              app.current_stage_code.slice(1).replace(/_/g, " "),
            hasAssessment: Boolean(app.has_assessment),
            assessmentStatus: app.assessment_status ?? "none",
            assessmentScorePercent: app.assessment_score_percent ?? null,
            roadmap: app.roadmap,
          }),
        );
      }),
  });

// ── Candidate assessment (take + report) ───────────────────────────────────

export const useApplicationAssessment = (appId: string, enabled = true) =>
  useQuery({
    queryKey: ["candidate-assessment", appId],
    queryFn: () => candidatePortalApi.getApplicationAssessment(appId),
    enabled: Boolean(appId) && enabled,
  });

export const useSubmitApplicationAssessment = (appId: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (answers: Record<string, string>) =>
      candidatePortalApi.submitApplicationAssessment(appId, answers),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["candidate-assessment", appId] });
      qc.invalidateQueries({ queryKey: ["candidate-applications"] });
    },
  });
};

/**
 * Submit a job application as the current candidate.
 * Handles 409 (already applied) — the caller should inspect the error status.
 */
export const useApplyToJob = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => candidatePortalApi.applyToJob(jobId),
    onSuccess: (_data, jobId) => {
      // Invalidate both the global list and the per-job status
      qc.invalidateQueries({ queryKey: ["candidate-applications"] });
      qc.invalidateQueries({ queryKey: ["job-application-status", jobId] });
    },
  });
};

/**
 * Check whether the current authenticated candidate has already applied to
 * a specific job. Disabled automatically when no jobId / not authenticated.
 */
export const useJobApplicationStatus = (
  jobId: string | null | undefined,
  options?: { enabled?: boolean },
) => {
  const { isAuthenticated, user } = useAuthStore();
  const isCandidate =
    user?.accountType === "candidate" || user?.role === "candidate";
  return useQuery({
    queryKey: ["job-application-status", jobId],
    queryFn: () => candidatePortalApi.getApplicationStatus(jobId!),
    enabled:
      !!jobId &&
      isAuthenticated &&
      isCandidate &&
      (options?.enabled !== false),
    staleTime: 60_000,
    retry: false,
  });
};

export const useCVUpload = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ file, candidateId }: { file: File; candidateId?: string }) => {
      const fromCache = qc.getQueryData<CandidateProfile>(["candidate-profile"]);
      const cid = candidateId ?? fromCache?.id;
      if (!cid) throw new Error("Your candidate profile is not loaded. Refresh and try again.");
      return cvIngestionApi.upload(file, cid);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["candidate-profile"] });
    },
  });
};

export const usePublicJobs = () =>
  useQuery({
    queryKey: ["public-jobs"],
    queryFn: async () => {
      const jobs = await publicJobsApi.list();
      return jobs.map((j) => ({
        id: String(j.id),
        title: j.title,
        company: j.company_name ?? "Unknown Company",
        location: j.location_text ?? "Remote",
        workMode: j.workplace_type ?? "onsite",
        salary: j.salary_min && j.salary_max
          ? `${j.salary_currency ?? "USD"} ${j.salary_min.toLocaleString()} – ${j.salary_max.toLocaleString()} / mo`
          : "Competitive",
        skills: [] as string[],
        level: j.seniority_level ?? "Mid",
        postedAt: new Date().toISOString().split("T")[0],
        applicants: j.applicant_count ?? 0,
        applicationMode: j.application_mode ?? "internal_apply",
        externalApplyUrl: j.external_apply_url ?? null,
        sourceUrl: j.source_url ?? j.job_url ?? null,
        source: j.source_platform ?? j.source ?? null,
      }));
    },
    staleTime: 120_000,
  });

// ── Decision Support System hooks ─────────────────────────────────────────

export const useDSSLatestPacket = (applicationId: string, orgId: string) =>
  useQuery({
    queryKey: ["dss-packet", "latest", applicationId],
    queryFn: () => dssApi.getLatestForApplication(applicationId, orgId),
    enabled: Boolean(applicationId) && Boolean(orgId),
    retry: 1,
  });

export const useDSSPacket = (packetId: string, orgId: string) =>
  useQuery({
    queryKey: ["dss-packet", packetId],
    queryFn: () => dssApi.getPacket(packetId, orgId),
    enabled: Boolean(packetId) && Boolean(orgId),
  });

export const useDSSDevPlan = (packetId: string, orgId: string, enabled = true) =>
  useQuery({
    queryKey: ["dss-devplan", packetId],
    queryFn: () => dssApi.getDevPlan(packetId, orgId),
    enabled: Boolean(packetId) && Boolean(orgId) && enabled,
    retry: 1,
  });

export const useDSSEmail = (packetId: string, orgId: string, enabled = true) =>
  useQuery({
    queryKey: ["dss-email", packetId],
    queryFn: () => dssApi.getEmail(packetId, orgId),
    enabled: Boolean(packetId) && Boolean(orgId) && enabled,
    retry: 1,
  });

export const useGenerateDSSPacket = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      orgId,
      applicationId,
      candidateId,
      jobId,
    }: {
      orgId: string;
      applicationId: string;
      candidateId: string;
      jobId: string;
    }) =>
      dssApi.generate(orgId, {
        application_id: applicationId,
        candidate_id: candidateId,
        job_id: jobId,
      }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["dss-packet", "latest", vars.applicationId] });
    },
  });
};

export const useHrDecision = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      packetId,
      orgId,
      finalDecision,
      hrNotes,
      overrideReason,
    }: {
      packetId: string;
      orgId: string;
      finalDecision: string;
      hrNotes?: string;
      overrideReason?: string;
    }) =>
      dssApi.hrDecision(packetId, orgId, {
        final_decision: finalDecision,
        hr_notes: hrNotes,
        override_reason: overrideReason,
      }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["dss-packet", vars.packetId] });
      // Refresh the decision report so the IDSS "Next action" box flips to
      // Accepted/Rejected and the page's decision-locked state updates at once.
      qc.invalidateQueries({ queryKey: ["decision-report", vars.packetId] });
    },
  });
};

export const useGenerateDevPlan = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ packetId, orgId }: { packetId: string; orgId: string }) =>
      dssApi.generateDevPlan(packetId, orgId),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["dss-devplan", vars.packetId] });
    },
  });
};

export const useGenerateDSSEmail = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      packetId,
      orgId,
      emailType,
    }: {
      packetId: string;
      orgId: string;
      emailType: "acceptance" | "rejection";
    }) => dssApi.generateEmail(packetId, orgId, emailType),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["dss-email", vars.packetId] });
    },
  });
};

export const useApproveDSSEmail = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ packetId, orgId }: { packetId: string; orgId: string }) =>
      dssApi.approveEmail(packetId, orgId),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["dss-email", vars.packetId] });
    },
  });
};

export const useSendDSSEmail = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ packetId, orgId }: { packetId: string; orgId: string }) =>
      dssApi.sendEmail(packetId, orgId),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["dss-email", vars.packetId] });
    },
  });
};

// ── Interview Intelligence hooks ───────────────────────────────────────────

export const useInterviews = (orgId: string) =>
  useQuery({
    queryKey: ["interviews", orgId],
    queryFn: async () => {
      const rows = await orgEntityQuery(() => interviewsApi.list(orgId));
      return rows.map((row) => ({
        id: row.interview_id,
        applicationId: row.application_id,
        candidateName: row.candidate_name,
        jobTitle: row.job_title,
        interviewType: row.interview_type,
        status: row.status,
        scheduledStart: row.scheduled_start,
        meetingUrl: row.meeting_url,
      }));
    },
    enabled: Boolean(orgId),
  });

export const useScheduleInterview = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Parameters<typeof interviewsApi.schedule>[0]) =>
      interviewsApi.schedule(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["interviews"] });
    },
  });
};

export const useInterviewQuestions = (interviewId: string, orgId: string) =>
  useQuery({
    queryKey: ["interview-questions", interviewId],
    queryFn: () => interviewsApi.getQuestions(interviewId, orgId),
    enabled: Boolean(interviewId) && Boolean(orgId),
  });

export const useGenerateInterviewQuestions = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      interviewId,
      orgId,
      includeHr = true,
      includeTechnical = true,
      regenerate = false,
    }: {
      interviewId: string;
      orgId: string;
      includeHr?: boolean;
      includeTechnical?: boolean;
      regenerate?: boolean;
    }) =>
      interviewsApi.generateQuestions(interviewId, orgId, {
        include_hr: includeHr,
        include_technical: includeTechnical,
        regenerate,
      }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["interview-questions", vars.interviewId] });
    },
  });
};

export const useApproveInterviewQuestions = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      interviewId,
      orgId,
      approved,
    }: {
      interviewId: string;
      orgId: string;
      approved: boolean;
    }) => interviewsApi.approveQuestions(interviewId, orgId, { approved }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["interview-questions", vars.interviewId] });
    },
  });
};

export const useUploadTranscript = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      interviewId,
      orgId,
      transcriptText,
      transcriptSource,
    }: {
      interviewId: string;
      orgId: string;
      transcriptText: string;
      transcriptSource?: string;
    }) =>
      interviewsApi.uploadTranscript(interviewId, orgId, {
        transcript_text: transcriptText,
        transcript_source: transcriptSource ?? "manual",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["interview-analysis"] });
    },
  });
};

export const useAnalyzeInterview = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      interviewId,
      orgId,
    }: {
      interviewId: string;
      orgId: string;
    }) => interviewsApi.analyze(interviewId, orgId),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["interview-analysis", vars.interviewId] });
    },
  });
};

export const useInterviewHumanDecision = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      interviewId,
      orgId,
      finalDecision,
      hrNotes,
      overrideReason,
    }: {
      interviewId: string;
      orgId: string;
      finalDecision: string;
      hrNotes?: string;
      overrideReason?: string;
    }) =>
      interviewsApi.humanDecision(interviewId, orgId, {
        final_decision: finalDecision,
        hr_notes: hrNotes,
        override_reason: overrideReason,
      }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["interview-analysis", vars.interviewId] });
    },
  });
};

export const useInterviewList = (orgId: string) =>
  useQuery({
    queryKey: ["interviews", orgId],
    queryFn: () => interviewsApi.list(orgId),
    enabled: !!orgId,
    staleTime: 30_000,
  });

export const useInterviewDetail = (interviewId: string | null | undefined, orgId: string) =>
  useQuery({
    queryKey: ["interview-session", interviewId],
    queryFn: () => interviewRuntimeApi.getSession(interviewId as string),
    enabled: !!interviewId,
    staleTime: 30_000,
  });

export const useInterviewAnalysis = (interviewId: string | null | undefined, orgId: string) =>
  useQuery({
    queryKey: ["interview-analysis", interviewId],
    queryFn: async () => {
      const a = await interviewsApi.getSummary(interviewId as string, orgId);
      return a;
    },
    enabled: !!interviewId && !!orgId,
    staleTime: 30_000,
  });

export const useHumanDecision = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      interviewId,
      orgId,
      finalDecision,
      hrNotes,
    }: {
      interviewId: string;
      orgId: string;
      finalDecision: string;
      hrNotes?: string;
    }) =>
      interviewsApi.humanDecision(interviewId, orgId, {
        final_decision: finalDecision,
        hr_notes: hrNotes,
      }),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ["interview-analysis", vars.interviewId] });
    },
  });
};

// ── Per-skill evidence hooks ──────────────────────────────────────────────
//
// Reads + refreshes per-skill evidence drawn from three MCP-style tools
// (CV / GitHub / LinkedIn). The refresh call is slow (can hit OpenRouter
// for each skill) so it's a mutation rather than a query — the UI shows
// a clear spinner during the run.

import { skillEvidenceApi } from "@/lib/api";

export const useSkillEvidence = (candidateId: string, enabled = true) =>
  useQuery({
    queryKey: ["skill-evidence", candidateId],
    queryFn: () => skillEvidenceApi.list(candidateId),
    enabled: Boolean(candidateId) && enabled,
    staleTime: 60_000,
  });

export const useRefreshSkillEvidence = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { candidateId: string; skills?: string[]; maxSkills?: number }) =>
      skillEvidenceApi.refresh(vars.candidateId, {
        skills: vars.skills,
        max_skills: vars.maxSkills,
      }),
    onSuccess: (data, vars) => {
      qc.setQueryData(["skill-evidence", vars.candidateId], data);
    },
  });
};

export const useCandidateProfileUrls = (candidateId: string, enabled = true) =>
  useQuery({
    queryKey: ["candidate-profile-urls", candidateId],
    queryFn: () => skillEvidenceApi.getProfileUrls(candidateId),
    enabled: Boolean(candidateId) && enabled,
  });

export const useSetCandidateProfileUrls = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: {
      candidateId: string;
      github?: string | null;
      linkedin?: string | null;
      portfolio?: string | null;
    }) =>
      skillEvidenceApi.setProfileUrls(vars.candidateId, {
        github: vars.github,
        linkedin: vars.linkedin,
        portfolio: vars.portfolio,
      }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["candidate-profile-urls", vars.candidateId] });
    },
  });
};

// ── Recall.ai notetaker bot hooks ─────────────────────────────────────────

import { recallApi } from "@/lib/api";
import type { RecallRecordingMode } from "@/lib/api";
import { useEffect, useState } from "react";

export const useRecallState = (interviewId: string) =>
  useQuery({
    queryKey: ["recall-state", interviewId],
    queryFn: () => recallApi.getState(interviewId),
    enabled: Boolean(interviewId),
    // Poll every 5s while a bot is in flight so the dashboard reflects
    // status changes even without webhooks.
    refetchInterval: (q) => {
      const s = (q.state.data as { status?: string | null } | undefined)?.status;
      const live = s === "joining" || s === "in_call" || s === "recording" || s === "in_waiting_room";
      return live ? 5_000 : false;
    },
  });

export const useSetRecallMode = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { interviewId: string; mode: RecallRecordingMode }) =>
      recallApi.setMode(vars.interviewId, vars.mode),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ["recall-state", vars.interviewId] });
    },
  });
};

export const useStartRecallBot = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (interviewId: string) => recallApi.start(interviewId),
    onSuccess: (_d, interviewId) => {
      qc.invalidateQueries({ queryKey: ["recall-state", interviewId] });
    },
  });
};

export const useStopRecallBot = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (interviewId: string) => recallApi.stop(interviewId),
    onSuccess: (_d, interviewId) => {
      qc.invalidateQueries({ queryKey: ["recall-state", interviewId] });
      qc.invalidateQueries({ queryKey: ["recall-transcript", interviewId] });
    },
  });
};

/**
 * Manually pull the latest bot / recording / transcript from Recall.ai and
 * persist it on the interview row.  Use this when RECALL_PUBLIC_WEBHOOK_URL
 * is blank — after the meeting ends click "Sync transcript" to fetch the result.
 */
export const useSyncRecallBot = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (interviewId: string) => recallApi.sync(interviewId),
    onSuccess: (_d, interviewId) => {
      qc.invalidateQueries({ queryKey: ["recall-state", interviewId] });
      qc.invalidateQueries({ queryKey: ["recall-transcript", interviewId] });
    },
  });
};

export const useRecallTranscript = (interviewId: string, enabled = true) =>
  useQuery({
    queryKey: ["recall-transcript", interviewId],
    queryFn: () => recallApi.getTranscript(interviewId),
    enabled: Boolean(interviewId) && enabled,
    // Keep polling until transcript_text is non-empty (handles async processing lag).
    refetchInterval: (query) => {
      const data = query.state.data as { transcript_text?: string } | undefined;
      return data?.transcript_text ? false : 15_000;
    },
  });

/**
 * Subscribe to the SSE stream of real-time transcript chunks. Buffers
 * chunks into local state and re-renders on each new chunk. Closes the
 * connection automatically on unmount or when ``enabled`` flips to false.
 */
export function useRecallTranscriptStream(
  interviewId: string,
  enabled: boolean,
) {
  const token = useAuthStore((s) => s.token) ?? "";
  const [chunks, setChunks] = useState<unknown[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!enabled || !interviewId || !token) {
      setConnected(false);
      return;
    }
    let es: EventSource | null = null;
    try {
      es = new EventSource(recallApi.streamUrl(interviewId, token));
    } catch {
      setConnected(false);
      return;
    }
    setConnected(true);
    es.addEventListener("replay", (e) => {
      try {
        const arr = JSON.parse((e as MessageEvent).data);
        if (Array.isArray(arr)) setChunks(arr);
      } catch {
        /* tolerate malformed replay */
      }
    });
    es.addEventListener("transcript", (e) => {
      try {
        const chunk = JSON.parse((e as MessageEvent).data);
        setChunks((prev) => [...prev, chunk]);
      } catch {
        /* drop malformed chunks rather than crash */
      }
    });
    es.addEventListener("error", () => setConnected(false));
    return () => {
      es?.close();
      setConnected(false);
    };
  }, [interviewId, enabled, token]);

  return { chunks, connected };
}

// ── Organization Matching / Outreach hooks ────────────────────────────────

export const useOrgDatabaseSearch = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Parameters<typeof orgMatchingApi.databaseSearch>[0]) =>
      orgMatchingApi.databaseSearch(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["org-matching"] });
    },
  });
};

export const useMatchingRun = (runId: string) =>
  useQuery({
    queryKey: ["org-matching-run", runId],
    queryFn: () => orgMatchingApi.getRun(runId),
    enabled: Boolean(runId),
  });

export const useMatchingShortlist = (runId: string) =>
  useQuery({
    queryKey: ["org-matching-shortlist", runId],
    queryFn: () => orgMatchingApi.getShortlist(runId),
    enabled: Boolean(runId),
  });

export const useApproveOutreach = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      runId,
      rankingId,
      bookingLink,
      deadlineDays,
    }: {
      runId: string;
      rankingId: string;
      bookingLink?: string;
      deadlineDays?: number;
    }) =>
      orgMatchingApi.approveOutreach(runId, rankingId, {
        booking_link: bookingLink,
        deadline_days: deadlineDays,
      }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["org-matching-shortlist", vars.runId] });
    },
  });
};

export const useGenerateOutreachDraft = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      runId,
      rankingId,
      bookingLink,
      deadlineDays,
    }: {
      runId: string;
      rankingId: string;
      bookingLink?: string;
      deadlineDays?: number;
    }) =>
      orgMatchingApi.generateDraft(runId, rankingId, {
        booking_link: bookingLink,
        deadline_days: deadlineDays,
      }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["org-matching-shortlist", vars.runId] });
    },
  });
};

export const useSendOutreach = () =>
  useMutation({
    mutationFn: ({
      messageId,
      recipientEmail,
    }: {
      messageId: string;
      recipientEmail: string;
    }) => orgMatchingApi.sendOutreach(messageId, { recipient_email: recipientEmail }),
  });

// fix4.md — anonymized outreach search with agent-generated explanations
export const useOutreachSearch = () =>
  useMutation({
    mutationFn: (body: OutreachSearchRequest) => outreachSearchApi.search(body),
  });

// fix7.md — semantic candidate search via Qdrant + agent explanation
export const useSemanticCandidateSearch = () =>
  useMutation({
    mutationFn: (body: SemanticSearchRequest) =>
      matchingWorkspaceApi.semanticSearch(body),
  });

// fix7.md — RAG candidate-vs-requirement test with structured rubric
export const useRagCandidateTest = () =>
  useMutation({
    mutationFn: (body: RagTestRequest) => matchingWorkspaceApi.ragTest(body),
  });

// fix8&9 Update 1 — candidate-side JD analysis
export const useCandidateJdAnalysis = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { job_description_text: string }) =>
      candidateJdAnalysisApi.analyze(body),
    // The analysis is saved server-side — refresh the history so the new one
    // appears at the top of the list.
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["candidate-jd-analyses"] });
    },
  });
};

export const useCandidateJdAnalyses = () =>
  useQuery({
    queryKey: ["candidate-jd-analyses"],
    queryFn: () => candidateJdAnalysisApi.list(),
    staleTime: 30_000,
  });

// Candidate dashboard — top matching jobs (vector similarity ≥ threshold)
export const useCandidateMatchingJobs = (params?: {
  minScore?: number;
  limit?: number;
  enabled?: boolean;
}) =>
  useQuery({
    queryKey: ["candidate-matching-jobs", params?.minScore ?? 50, params?.limit ?? 5],
    queryFn: () =>
      candidateMatchingApi.topJobs({
        minScore: params?.minScore ?? 50,
        limit: params?.limit ?? 5,
      }),
    enabled: params?.enabled !== false,
    staleTime: 120_000,
  });

// Candidate dashboard — explain why a specific job matches (LLM, ~1-5 min)
export const useExplainJobMatch = () =>
  useMutation({
    mutationFn: (jobId: string) => candidateMatchingApi.explain(jobId),
  });

// Candidate dashboard — the candidate's scheduled interview invites
export const useCandidateInterviews = () =>
  useQuery({
    queryKey: ["candidate-interviews"],
    queryFn: () => candidateMatchingApi.myInterviews(),
    staleTime: 60_000,
  });

// Open Jobs — import 5 fresh jobs (live scrape + sample fallback)
export const useImportFreshJobs = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => candidateMatchingApi.importFreshJobs(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["public-jobs"] });
      qc.invalidateQueries({ queryKey: ["candidate-matching-jobs"] });
    },
  });
};

// ── Interview Intelligence runtime hooks ──────────────────────────────────

export const useCreateInterviewSession = () =>
  useMutation({
    mutationFn: (body: BackendCreateInterviewSessionBody) =>
      interviewRuntimeApi.createSession(body),
  });

export const useInterviewSession = (sessionId: string) =>
  useQuery({
    queryKey: ["interview-session", sessionId],
    queryFn: () => interviewRuntimeApi.getSession(sessionId),
    enabled: Boolean(sessionId),
  });

export const useGenerateInterviewQuestionsRuntime = () =>
  useMutation({
    mutationFn: (vars: {
      interviewId: string;
      orgId: string;
      regenerate?: boolean;
    }) =>
      interviewRuntimeApi.generateQuestions(vars.interviewId, vars.orgId, {
        include_hr: true,
        include_technical: true,
        regenerate: !!vars.regenerate,
      }),
  });

export const useRecordInterviewAnswer = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: {
      sessionId: string;
      question: string;
      answer: string;
      is_followup?: boolean;
      parent_index?: number | null;
    }) =>
      interviewRuntimeApi.recordAnswer(vars.sessionId, {
        question: vars.question,
        answer: vars.answer,
        is_followup: vars.is_followup ?? false,
        parent_index: vars.parent_index ?? null,
      }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["interview-session", vars.sessionId] });
    },
  });
};

export const useGenerateInterviewFollowUp = () =>
  useMutation({
    mutationFn: (vars: { sessionId: string; parentIndex: number }) =>
      interviewRuntimeApi.generateFollowUp(vars.sessionId, vars.parentIndex),
  });

export const useFinishInterviewSession = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) => interviewRuntimeApi.finish(sessionId),
    onSuccess: (_data, sessionId) => {
      qc.invalidateQueries({ queryKey: ["interview-session", sessionId] });
      qc.invalidateQueries({ queryKey: ["interview-report", sessionId] });
    },
  });
};

export const useEvaluateInterviewSession = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) => interviewRuntimeApi.evaluate(sessionId),
    onSuccess: (_data, sessionId) => {
      qc.invalidateQueries({ queryKey: ["interview-report", sessionId] });
    },
  });
};

// ── Find Talent (LinkedIn outbound sourcing) ───────────────────────────────

export const useFindTalent = () =>
  useMutation({
    mutationFn: (body: FindTalentRequest) => sourceCandidateApi.findTalent(body),
  });

export const useImportExternalCandidate = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (externalCandidateId: string) =>
      sourceCandidateApi.importExternal(externalCandidateId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["candidates"] });
    },
  });
};

export const useInterviewReport = (sessionId: string, enabled = true) =>
  useQuery({
    queryKey: ["interview-report", sessionId],
    queryFn: () => interviewRuntimeApi.getReport(sessionId),
    enabled: Boolean(sessionId) && enabled,
  });

// ── Open-to-Work Candidate Sourcing hooks ─────────────────────────────────

export const useSourcingStatus = () =>
  useQuery({
    queryKey: ["sourcing", "status"],
    queryFn: () => orgEntityQuery(() => sourcingApi.status()),
    staleTime: 30_000,
  });

export const useSourcedCandidates = (filters: SourcedListFilters = {}) =>
  useQuery({
    queryKey: [
      "sourcing",
      "candidates",
      filters.title ?? "",
      (filters.skills ?? []).join(","),
      filters.location ?? "",
      filters.workplace ?? "",
      filters.employmentType ?? "",
      filters.minYearsExperience ?? null,
      filters.maxYearsExperience ?? null,
      filters.limit ?? null,
      filters.offset ?? null,
    ],
    queryFn: () => orgEntityQuery(() => sourcingApi.list(filters)),
  });

export const useSourcedMatchForJob = (
  jobId: string,
  filters: SourcedMatchFilters = {},
  enabled = true,
) =>
  useQuery({
    queryKey: [
      "sourcing",
      "match",
      jobId,
      filters.topK ?? null,
      filters.location ?? "",
      (filters.workplace ?? []).join(","),
      (filters.employmentType ?? []).join(","),
      filters.minScore ?? null,
    ],
    queryFn: () =>
      orgEntityQuery(() => sourcingApi.matchForJob(jobId, filters)),
    enabled: Boolean(jobId) && enabled,
  });

export const useExplainSourcedMatch = () =>
  useMutation({
    mutationFn: ({ jobId, candidateId }: { jobId: string; candidateId: string }) =>
      sourcingApi.explain(jobId, candidateId),
  });

export const useRunSourcingImport = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      limit?: number;
      provider?: string;
      keywords?: string[];
      location?: string;
    }) => sourcingApi.runImport(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sourcing"] });
    },
  });
};

// ── Outreach Agent hooks ──────────────────────────────────────────────────

export const useGoogleIntegrationStatus = () =>
  useQuery({
    queryKey: ["google-integration", "status"],
    queryFn: () => orgEntityQuery(() => googleIntegrationApi.status()),
    refetchInterval: 30_000,
  });

export const useGoogleIntegrationConnect = () =>
  useMutation({
    mutationFn: () => googleIntegrationApi.connect(),
  });

export const useGoogleIntegrationDisconnect = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => googleIntegrationApi.disconnect(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["google-integration"] });
    },
  });
};

export const useGenerateOutreachEmail = () =>
  useMutation({
    mutationFn: (body: {
      candidate_id: string;
      job_id?: string | null;
      interview_type?: string;
      is_final_offer?: boolean;
      extra_instructions?: string;
    }) => outreachAgentApi.generateEmail(body),
  });

export const useSaveOutreachDraft = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: BackendOutreachCreateBody) => outreachAgentApi.saveDraft(body),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["outreach-history", vars.candidate_id] });
    },
  });
};

export const useSendOutreachAgent = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: BackendOutreachCreateBody) => outreachAgentApi.send(body),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["outreach-history", vars.candidate_id] });
    },
  });
};

export const useOutreachHistory = (candidateId: string) =>
  useQuery({
    queryKey: ["outreach-history", candidateId],
    queryFn: () =>
      orgEntityQuery(() => outreachAgentApi.history(candidateId)),
    enabled: Boolean(candidateId),
  });

export const usePublicSchedule = (token: string) =>
  useQuery({
    queryKey: ["public-schedule", token],
    queryFn: () => publicSchedulingApi.view(token),
    enabled: Boolean(token),
    retry: 0,
  });

export const useBookPublicSlot = () =>
  useMutation({
    mutationFn: ({
      token,
      start,
      end,
    }: {
      token: string;
      start: string;
      end: string;
    }) =>
      publicSchedulingApi.book(token, {
        selected_start_time: start,
        selected_end_time: end,
      }),
  });

// ── IDSS / Development Plan hooks ─────────────────────────────────────────

import { developmentPlansApi as _devPlansApi } from "@/lib/api";

export const useDecisionReport = (packetId: string, orgId: string, enabled = true) =>
  useQuery({
    queryKey: ["decision-report", packetId],
    queryFn: () => dssApi.decisionReport(packetId, orgId),
    enabled: Boolean(packetId) && Boolean(orgId) && enabled,
  });

export const useManagerDecision = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: {
      packetId: string;
      orgId: string;
      decision:
        | "accepted"
        | "rejected"
        | "request_more_interview"
        | "request_more_evidence";
      managerNotes?: string;
    }) =>
      dssApi.managerDecision(vars.packetId, vars.orgId, {
        decision: vars.decision,
        manager_notes: vars.managerNotes,
      }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["decision-report", vars.packetId] });
      qc.invalidateQueries({ queryKey: ["dss-packet"] });
    },
  });
};

export const useGenerateDevelopmentPlan = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: {
      orgId: string;
      candidateId: string;
      jobId: string;
      decisionId: string;
    }) =>
      _devPlansApi.generate(vars.orgId, {
        candidate_id: vars.candidateId,
        job_id: vars.jobId,
        decision_id: vars.decisionId,
      }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["decision-report", vars.decisionId] });
      qc.invalidateQueries({ queryKey: ["candidate-plans", vars.candidateId] });
    },
  });
};

export const useDevelopmentPlan = (planId: string, orgId: string, enabled = true) =>
  useQuery({
    queryKey: ["development-plan", planId],
    queryFn: () => _devPlansApi.get(planId, orgId),
    enabled: Boolean(planId) && Boolean(orgId) && enabled,
  });

export const useApprovePlan = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { planId: string; orgId: string; notes?: string }) =>
      _devPlansApi.approve(vars.planId, vars.orgId, { notes: vars.notes }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["development-plan", vars.planId] });
      qc.invalidateQueries({ queryKey: ["decision-report"] });
    },
  });
};

export const useRevisePlan = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { planId: string; orgId: string; notes?: string }) =>
      _devPlansApi.revise(vars.planId, vars.orgId, { notes: vars.notes }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["development-plan", vars.planId] });
    },
  });
};

export const useUpdateCandidateFeedback = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: {
      planId: string;
      orgId: string;
      candidateFacingMessage: string;
    }) =>
      _devPlansApi.setCandidateFeedback(vars.planId, vars.orgId, {
        candidate_facing_message: vars.candidateFacingMessage,
      }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["development-plan", vars.planId] });
    },
  });
};

export const useSendPlanFeedback = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { planId: string; orgId: string; recipientEmail?: string }) =>
      _devPlansApi.sendFeedback(vars.planId, vars.orgId, {
        recipient_email: vars.recipientEmail,
      }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["development-plan", vars.planId] });
    },
  });
};

export const useShortlistSourcedCandidate = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      jobId,
      candidateId,
      stageCode,
      note,
    }: {
      jobId: string;
      candidateId: string;
      stageCode?: string;
      note?: string;
    }) =>
      sourcingApi.shortlist(jobId, {
        candidate_id: candidateId,
        job_id: jobId,
        stage_code: stageCode,
        note,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["applications"] });
      qc.invalidateQueries({ queryKey: ["shortlist"] });
    },
  });
};

// ── Identity Resolution hooks ─────────────────────────────────────────────

import { identityResolutionApi } from "@/lib/api";

export const useScanDuplicates = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => identityResolutionApi.scan(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["identity-resolution", "duplicates"] });
    },
  });
};

export const useDuplicates = (status?: string) =>
  useQuery({
    queryKey: ["identity-resolution", "duplicates", status ?? "all"],
    queryFn: () => identityResolutionApi.listDuplicates(status),
  });

export const useApproveMerge = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string }) =>
      identityResolutionApi.approveMerge(id, notes),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["identity-resolution"] });
      qc.invalidateQueries({ queryKey: ["merge-history"] });
    },
  });
};

export const useRejectMerge = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string }) =>
      identityResolutionApi.rejectMerge(id, notes),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["identity-resolution", "duplicates"] });
    },
  });
};

export const useMergeHistory = () =>
  useQuery({
    queryKey: ["merge-history"],
    queryFn: () => identityResolutionApi.getMergeHistory(),
  });

// ── Assessment Agent hooks ──────────────────────────────────────────────────

export const useAssessments = (params?: {
  application_id?: string;
  candidate_id?: string;
  job_id?: string;
  status?: string;
  assessment_type?: string;
  limit?: number;
}) =>
  useQuery({
    queryKey: ["assessments", params],
    queryFn: () => assessmentsApi.list(params),
  });

// fix5.md — job-scoped listing for the new Assessment workspace
export const useJobAssessments = (jobId: string | null | undefined) =>
  useQuery({
    queryKey: ["assessments", "by-job", jobId ?? ""],
    queryFn: () => assessmentsApi.listByJob(jobId as string),
    enabled: Boolean(jobId),
  });

export const useJobAssessmentResults = (jobId: string | null | undefined) =>
  useQuery({
    queryKey: ["assessments", "results", jobId ?? ""],
    queryFn: () => assessmentsApi.resultsByJob(jobId as string),
    enabled: Boolean(jobId),
    staleTime: 15_000,
  });

export const useAssessment = (id: string) =>
  useQuery({
    queryKey: ["assessments", id],
    queryFn: () => assessmentsApi.get(id),
    enabled: Boolean(id),
  });

export const useCreateAssessment = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Parameters<typeof assessmentsApi.create>[0]) =>
      assessmentsApi.create(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assessments"] });
    },
  });
};

export const useUpdateAssessment = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      ...body
    }: { id: string } & Parameters<typeof assessmentsApi.update>[1]) =>
      assessmentsApi.update(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assessments"] });
    },
  });
};

export const useDeleteAssessment = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => assessmentsApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assessments"] });
    },
  });
};

// fix5.md — generate draft via the OpenRouter-backed agent
export const useGenerateAssessmentDraft = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Parameters<typeof assessmentsApi.generateDraft>[0]) =>
      assessmentsApi.generateDraft(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assessments"] });
    },
  });
};

// fix5.md — flip draft → published
export const useApproveAssessment = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, publish }: { id: string; publish?: boolean }) =>
      assessmentsApi.approve(id, publish ?? true),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assessments"] });
    },
  });
};

// fix5.md — upload a reference file used as agent context
export const useUploadAssessmentSourceFile = () =>
  useMutation({
    mutationFn: (file: File) => assessmentsApi.uploadSourceFile(file),
  });

// ── Knowledge Base hooks ───────────────────────────────────────────────────

async function enrichCollection(
  name: string,
): Promise<BackendQdrantCollection> {
  try {
    return await kbApi.getCollection(name);
  } catch {
    return { name, status: "unknown", vectors_count: null, dimension: null };
  }
}

export function useCollections() {
  return useQuery<BackendQdrantCollection[]>({
    queryKey: ["kb", "collections"],
    queryFn: async () => {
      const { collections: names } = await kbApi.listCollections();
      const detailed = await Promise.all(names.map(enrichCollection));
      return detailed;
    },
    staleTime: 30_000,
  });
}

export function useSearchCollection() {
  return useMutation({
    mutationFn: ({
      collectionName,
      query,
      limit,
    }: {
      collectionName: string;
      query: string;
      limit?: number;
    }) => kbApi.search(collectionName, query, limit),
  });
}

// ── Contact Enrichment hooks ────────────────────────────────────────────────

export const useContactEnrichmentStatus = () =>
  useQuery({
    queryKey: ["contact-enrichment", "status"],
    queryFn: () => contactEnrichmentApi.status(),
  });

export const useEnrichedContacts = (params?: {
  status?: string;
  contact_type?: string;
}) =>
  useQuery({
    queryKey: ["contact-enrichment", "contacts", params],
    queryFn: () => contactEnrichmentApi.list(params),
  });

export const useApproveContact = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      reviewer_name,
    }: {
      id: string;
      reviewer_name?: string;
    }) => contactEnrichmentApi.approve(id, { reviewer_name }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["contact-enrichment"] });
    },
  });
};

export const useRejectContact = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      reviewer_name,
    }: {
      id: string;
      reviewer_name?: string;
    }) => contactEnrichmentApi.reject(id, { reviewer_name }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["contact-enrichment"] });
    },
  });
};

// ── Contact Finder — interview candidates + enrichment ─────────────────────

export const useInterviewContactCandidates = () =>
  useQuery({
    queryKey: ["contact-finder", "interview-candidates"],
    queryFn: () => contactEnrichmentApi.interviewCandidates(),
    staleTime: 30_000,
  });

export const useEnrichCandidate = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (candidateId: string) =>
      contactEnrichmentApi.enrichCandidate(candidateId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["contact-finder"] });
      qc.invalidateQueries({ queryKey: ["contact-enrichment"] });
    },
  });
};


// ── Candidate Sourcing & Pool ─────────────────────────────────────────────
//
// All hooks here return real backend data from the candidate-sourcing API.
// There is no mock fallback — when the backend is unreachable, these queries
// surface the error and the UI is responsible for showing an honest state.

import {
  candidateSourcingApi,
  type OrgSourceSettingsUpdate,
  type JobPoolConfigUpdate,
} from "@/lib/api";

export const useSourceCatalog = () =>
  useQuery({
    queryKey: ["candidate-source-catalog"],
    queryFn: candidateSourcingApi.catalog,
    staleTime: 5 * 60_000, // catalog is static-ish
  });

export const useOrgSourceSettings = () =>
  useQuery({
    queryKey: ["candidate-source-settings"],
    queryFn: candidateSourcingApi.getSettings,
    retry: false,
  });

export const useUpdateOrgSourceSettings = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: OrgSourceSettingsUpdate) =>
      candidateSourcingApi.updateSettings(body),
    onSuccess: (data) => {
      qc.setQueryData(["candidate-source-settings"], data);
      qc.invalidateQueries({ queryKey: ["candidate-source-counts"] });
    },
  });
};

export const useSourceCounts = () =>
  useQuery({
    queryKey: ["candidate-source-counts"],
    queryFn: candidateSourcingApi.counts,
    retry: false,
  });

export const useJobPoolConfig = (jobId: string | null | undefined) =>
  useQuery({
    queryKey: ["job-pool-config", jobId],
    queryFn: () => candidateSourcingApi.getJobPoolConfig(jobId as string),
    enabled: !!jobId,
    retry: false,
  });

export const useUpdateJobPoolConfig = (jobId: string | null | undefined) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: JobPoolConfigUpdate) =>
      candidateSourcingApi.updateJobPoolConfig(jobId as string, body),
    onSuccess: (data) => {
      qc.setQueryData(["job-pool-config", jobId], data);
    },
  });
};

export const usePreviewJobPool = (jobId: string | null | undefined) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => candidateSourcingApi.previewJobPool(jobId as string),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["job-pool-preview", jobId] });
    },
  });
};

export const useBuildJobPool = (jobId: string | null | undefined) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => candidateSourcingApi.buildJobPool(jobId as string),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["job-pool-runs", jobId] });
    },
  });
};

export const useJobPoolRuns = (jobId: string | null | undefined) =>
  useQuery({
    queryKey: ["job-pool-runs", jobId],
    queryFn: () => candidateSourcingApi.listPoolRuns(jobId as string),
    enabled: !!jobId,
    retry: false,
  });

// ── Phase 1: Job Detail Hub hooks ─────────────────────────────────────────

import {
  getJobDetail,
  getJobPipelineStages,
  getJobCandidates,
  moveApplicationStage,
  putFairnessRubric,
  getCandidateDetail,
  type JobCandidatesQuery,
  type FairnessRubricInput,
  type PipelineStage as ApiPipelineStage,
} from "@/lib/api/index";
import {
  adaptJobDetail,
  adaptPipelineStages,
  adaptCandidateList,
  adaptCandidateDetail,
} from "@/lib/api/adapters";

export const useJobDetail = (id: string | null | undefined) =>
  useQuery({
    queryKey: ["job", id],
    queryFn: async () => adaptJobDetail(await getJobDetail(id as string)),
    enabled: !!id,
    staleTime: 30_000,
  });

// Run Screening → top source-database candidates scored for this job.
export const useScreeningSourceCandidates = (
  jobId: string | null | undefined,
  enabled = true,
) =>
  useQuery({
    queryKey: ["screening-source-candidates", jobId],
    queryFn: () => jobsApi.screeningSourceCandidates(jobId as string, 10),
    enabled: Boolean(jobId) && enabled,
    staleTime: 30_000,
  });

export const useAddCandidateToJob = (jobId: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (candidateId: string) => jobsApi.addCandidateToJob(jobId, candidateId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["screening-source-candidates", jobId] });
      qc.invalidateQueries({ queryKey: ["jobCandidates", jobId] });
      qc.invalidateQueries({ queryKey: ["job", jobId] });
    },
  });
};

// Update a job (used by the job header "Archive" action and the edit page).
export const useUpdateJob = (jobId: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: BackendJobWriteBody) => jobsApi.update(jobId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["job", jobId] });
      qc.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
};

// Permanently delete a job. On success the caller navigates back to /jobs.
export const useDeleteJob = (jobId: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => jobsApi.delete(jobId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.removeQueries({ queryKey: ["job", jobId] });
    },
  });
};

export const useJobPipelineStages = (id: string | null | undefined) =>
  useQuery({
    queryKey: ["jobPipelineStages", id],
    queryFn: async () => adaptPipelineStages(await getJobPipelineStages(id as string)),
    enabled: !!id,
    staleTime: 15_000,
  });

export const useJobCandidates = (id: string | null | undefined, q: JobCandidatesQuery = {}) =>
  useQuery({
    queryKey: ["jobCandidates", id, q],
    queryFn: async () => adaptCandidateList(await getJobCandidates(id as string, q)),
    enabled: !!id,
    staleTime: 15_000,
  });

export const useMoveApplicationStage = (jobId: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ appId, stage }: { appId: string; stage: ApiPipelineStage }) =>
      moveApplicationStage(appId, stage),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["job", jobId] });
      qc.invalidateQueries({ queryKey: ["jobPipelineStages", jobId] });
      qc.invalidateQueries({ queryKey: ["jobCandidates", jobId] });
    },
  });
};

export const useUpdateFairnessRubric = (jobId: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (rubric: FairnessRubricInput) => putFairnessRubric(jobId, rubric),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["job", jobId] });
    },
  });
};

export const useCandidateDetail = (candidateId: string | null | undefined, jobId?: string) =>
  useQuery({
    queryKey: ["candidateDetail", candidateId, jobId],
    queryFn: async () =>
      adaptCandidateDetail(await getCandidateDetail(candidateId as string, jobId)),
    enabled: !!candidateId,
    staleTime: 30_000,
  });

export const useCreateJob = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: BackendJobWriteBody) => jobsApi.create(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
};

// ── Screening (Phase 2) ────────────────────────────────────────────────────

import {
  analyticsApi,
  screeningApi,
  agentRunsApi,
  sourcingAgentApi,
  type BackendAnalyticsSummary,
  type BackendAgentRun,
  type BackendBiasReport,
  type BackendBiasSummary,
  type BackendPoolRun,
  type BackendScreeningRun,
} from "@/lib/api";

export const useRunScreening = (jobId: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { organization_id: string; top_k?: number }) =>
      screeningApi.run(jobId, vars),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["screeningRuns", jobId] });
    },
  });
};

export const useScreeningRun = (runId: string | null | undefined) =>
  useQuery({
    queryKey: ["screeningRun", runId],
    queryFn: () => screeningApi.getRun(runId as string),
    enabled: !!runId,
    staleTime: 10_000,
  });

export const useBiasReport = (runId: string | null | undefined) =>
  useQuery({
    queryKey: ["biasReport", runId],
    queryFn: () => screeningApi.getBiasReport(runId as string),
    enabled: !!runId,
    staleTime: 60_000,
  });

// ── Analytics (Phase 2.5) ─────────────────────────────────────────────────

export const useAnalyticsSummary = (days = 30) =>
  useQuery({
    queryKey: ["analyticsSummary", days],
    queryFn: () => analyticsApi.summary(days),
    staleTime: 60_000,
  });

export const useAnalyticsBiasSummary = (days = 30) =>
  useQuery({
    queryKey: ["analyticsBiasSummary", days],
    queryFn: () => analyticsApi.biasSummary(days),
    staleTime: 60_000,
  });

// ── Agent Runs (Phase 2/3) ─────────────────────────────────────────────────

/** Poll a single agent run — 2s interval while queued/running, then stops. */
export const useAgentRun = (runId: string | null | undefined) =>
  useQuery({
    queryKey: ["agentRun", runId],
    queryFn: () => agentRunsApi.get(runId as string),
    enabled: !!runId,
    staleTime: 0,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 2_000 : false;
    },
  });

/** List recent agent runs for an org — used by the global AgentRunsListener. */
export const useOrgAgentRuns = (
  orgId: string,
  params?: { run_type?: string; status?: string; limit?: number },
) =>
  useQuery({
    queryKey: ["agentRuns", orgId, params],
    queryFn: () => agentRunsApi.list(orgId, params),
    enabled: !!orgId,
    staleTime: 5_000,
    refetchInterval: 5_000,   // poll every 5 s to detect completions
  });

// ── Sourcing Agent hooks (Phase 3) ────────────────────────────────────────────

export const useBuildCandidatePool = (jobId: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      organization_id: string;
      top_k?: number;
      min_score?: number;
      provider?: string;
      location_filter?: string | null;
      workplace_filter?: string[];
    }) => sourcingAgentApi.buildPool(jobId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["poolRuns", jobId] });
    },
  });
};

export const usePoolRuns = (jobId: string | null | undefined, orgId: string) =>
  useQuery({
    queryKey: ["poolRuns", jobId, orgId],
    queryFn: () => sourcingAgentApi.getPoolRuns(jobId as string, orgId),
    enabled: !!jobId && !!orgId,
    staleTime: 15_000,
  });

export const useRecomputeDecision = (jobId: string) =>
  useMutation({
    mutationFn: (body: { organization_id: string; candidate_id: string; application_id?: string }) =>
      sourcingAgentApi.recomputeDecision(jobId, body),
  });

// ── Phase 6 — Billing hooks ──────────────────────────────────────────────────

/** Fetch all public plans (for /pricing and /billing). */
export const usePublicPlans = () =>
  useQuery({
    queryKey: ["publicPlans"],
    queryFn: () => publicApi.getPublicPlans(),
    staleTime: 5 * 60_000,
  });

/** Fetch the org's active subscription. */
export const useOrgSubscription = (orgId: string | null | undefined) =>
  useQuery({
    queryKey: ["orgSubscription", orgId],
    queryFn: () => billingApi.getSubscription(orgId as string),
    enabled: !!orgId,
    staleTime: 30_000,
  });

/** Fetch the org's invoice history. */
export const useOrgInvoices = (orgId: string | null | undefined) =>
  useQuery({
    queryKey: ["orgInvoices", orgId],
    queryFn: () => billingApi.getInvoices(orgId as string),
    enabled: !!orgId,
    staleTime: 60_000,
  });

/** Fetch the org's current-period usage counters. */
export const useUsage = (orgId: string | null | undefined) =>
  useQuery({
    queryKey: ["orgUsage", orgId],
    queryFn: () => billingApi.getUsage(orgId as string),
    enabled: !!orgId,
    staleTime: 30_000,
  });

/** Start a Stripe Checkout Session — redirects to Stripe. */
export const useUpgradePlan = (orgId: string) =>
  useMutation({
    mutationFn: ({
      planCode,
      billingCycle,
    }: {
      planCode: string;
      billingCycle: "monthly" | "annual";
    }) => billingApi.createCheckoutSession(orgId, planCode, billingCycle),
    onSuccess: (data) => {
      if (data.checkout_url) window.location.assign(data.checkout_url);
    },
  });

/** Open the Stripe Customer Portal — redirects to Stripe. */
export const useCustomerPortalLink = (orgId: string) =>
  useMutation({
    mutationFn: () => billingApi.getCustomerPortalUrl(orgId),
    onSuccess: (data) => {
      if (data.portal_url) window.location.assign(data.portal_url);
    },
  });

// ── Phase 6 — Public site hooks ─────────────────────────────────────────────

export const usePlatformStats = () =>
  useQuery({
    queryKey: ["platformStats"],
    queryFn: () => publicApi.getPlatformStats(),
    staleTime: 60_000,
  });

export const usePublicJobsList = (params?: {
  q?: string;
  location?: string;
  work_mode?: string;
  page?: number;
}) =>
  useQuery({
    queryKey: ["publicJobs", params],
    queryFn: () => publicApi.getPublicJobs(params),
    staleTime: 30_000,
  });

export const usePublicJobDetail = (slug: string | null | undefined) =>
  useQuery({
    queryKey: ["publicJob", slug],
    queryFn: () => publicApi.getPublicJob(slug as string),
    enabled: !!slug,
    staleTime: 60_000,
  });

// ── Phase 6 — Auth (forgot/reset password) ──────────────────────────────────

export const useForgotPassword = () =>
  useMutation({
    mutationFn: (email: string) => authExtApi.forgotPassword(email),
  });

export const useResetPassword = () =>
  useMutation({
    mutationFn: ({ token, newPassword }: { token: string; newPassword: string }) =>
      authExtApi.resetPassword(token, newPassword),
  });

// ── Phase 7 — Admin hooks ────────────────────────────────────────────────────

import {
  platformAdminApi,
  type AdminAgentRun,
  type AdminFeatureFlag,
  type AdminOrgDossier,
  type AdminPlatformSettings,
  type AdminPlatformStats,
  type AdminSystemHealth,
} from "@/lib/api/platform-admin.api";

export const useAdminPlatformStats = () =>
  useQuery({
    queryKey: ["adminPlatformStats"],
    queryFn: () => platformAdminApi.platformStats(),
    staleTime: 30_000,
  });

export const useAdminOrgDossier = (id: string | null | undefined) =>
  useQuery({
    queryKey: ["adminOrgDossier", id],
    queryFn: () => platformAdminApi.getOrgDossier(id as string),
    enabled: !!id,
    staleTime: 15_000,
  });

export const useImpersonateOrg = () => {
  return useMutation({
    mutationFn: ({ orgId, reason }: { orgId: string; reason: string }) =>
      platformAdminApi.impersonateOrg(orgId, reason),
  });
};

export const useImpersonateUser = () => {
  return useMutation({
    mutationFn: ({ userId, reason }: { userId: string; reason: string }) =>
      platformAdminApi.impersonateUser(userId, reason),
  });
};

export const useSuspendUser = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, suspended }: { userId: string; suspended: boolean }) =>
      platformAdminApi.suspendUser(userId, suspended),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["adminUsers"] }),
  });
};

export const useAdminAgentRuns = (params?: {
  run_type?: string;
  status?: string;
  org_id?: string;
  limit?: number;
}) =>
  useQuery({
    queryKey: ["adminAgentRuns", params],
    queryFn: () => platformAdminApi.listAgentRuns(params),
    staleTime: 10_000,
    refetchInterval: 15_000,
  });

export const useRetryAgentRun = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => platformAdminApi.retryAgentRun(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["adminAgentRuns"] }),
  });
};

export const useAdminSystemHealth = () =>
  useQuery({
    queryKey: ["adminSystemHealth"],
    queryFn: () => platformAdminApi.systemHealth(),
    staleTime: 10_000,
    refetchInterval: 30_000,
  });

export const useAdminFeatureFlags = () =>
  useQuery({
    queryKey: ["adminFeatureFlags"],
    queryFn: () => platformAdminApi.listFeatureFlags(),
    staleTime: 30_000,
  });

export const useToggleFeatureFlag = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      platformAdminApi.updateFeatureFlag(id, { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["adminFeatureFlags"] }),
  });
};

export const useCreateFeatureFlag = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { code: string; description?: string; enabled?: boolean }) =>
      platformAdminApi.createFeatureFlag(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["adminFeatureFlags"] }),
  });
};

export const useAdminPlatformSettings = () =>
  useQuery({
    queryKey: ["adminPlatformSettings"],
    queryFn: () => platformAdminApi.getPlatformSettings(),
    staleTime: 30_000,
  });

export const useUpdatePlatformSettings = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<AdminPlatformSettings>) =>
      platformAdminApi.updatePlatformSettings(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["adminPlatformSettings"] }),
  });
};

// ── Phase 7 — Owner hooks ────────────────────────────────────────────────────

import {
  ownerApi,
  type OwnerRevenueSummary,
  type OwnerCustomer,
  type OwnerOrg,
  type OwnerPlan,
  type OwnerRevenuePoint,
  type OwnerAnnouncement,
} from "@/lib/api/owner.api";

export const useRevenueSummary = () =>
  useQuery({
    queryKey: ["revenueSummary"],
    queryFn: () => ownerApi.revenueSummary(),
    staleTime: 30_000,
  });

export const useRevenueAnalytics = (params?: { from?: string; to?: string }) =>
  useQuery({
    queryKey: ["revenueAnalytics", params],
    queryFn: () => ownerApi.revenueAnalytics(params),
    staleTime: 60_000,
  });

export const useOwnerCustomers = (params?: { health?: string; plan?: string }) =>
  useQuery({
    queryKey: ["ownerCustomers", params],
    queryFn: () => ownerApi.listCustomers(params),
    staleTime: 30_000,
  });

export const useOwnerOrgs = (params?: { q?: string; plan?: string }) =>
  useQuery({
    queryKey: ["ownerOrgs", params],
    queryFn: () => ownerApi.listOrgs(params),
    staleTime: 30_000,
  });

export const useOwnerPlans = () =>
  useQuery({
    queryKey: ["ownerPlans"],
    queryFn: () => ownerApi.listPlans(),
    staleTime: 60_000,
  });

export const useUpsertPlan = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Omit<OwnerPlan, "id"> & { id?: string }) =>
      data.id
        ? ownerApi.updatePlan(data.id, data)
        : ownerApi.createPlan(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ownerPlans"] }),
  });
};

export const useOwnerPlatformConfig = () =>
  useQuery({
    queryKey: ["ownerPlatformConfig"],
    queryFn: () => ownerApi.getPlatformConfig(),
    staleTime: 30_000,
  });

export const useUpdateOwnerPlatformConfig = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ownerApi.updatePlatformConfig,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ownerPlatformConfig"] }),
  });
};

export const useMarketingAnalytics = () =>
  useQuery({
    queryKey: ["marketingAnalytics"],
    queryFn: () => ownerApi.marketingAnalytics(),
    staleTime: 60_000,
  });

export const useOwnerAnnouncements = () =>
  useQuery({
    queryKey: ["ownerAnnouncements"],
    queryFn: () => ownerApi.listAnnouncements(),
    staleTime: 30_000,
  });

export const useCreateAnnouncement = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ownerApi.createAnnouncement,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ownerAnnouncements"] }),
  });
};

/**
 * PATHS API Adapters — convert backend snake_case shapes → frontend camelCase types.
 * Pages only import frontend types; adapters are applied inside hooks.
 */

import type {
  Application,
  HITLApproval,
  HITLActionType,
  HITLStatus,
  DashboardStats,
  AgentStatus,
  AuditEvent,
  AuditAction,
  FunnelSnapshot,
  ApplicationStatus,
  Member,
  UserRole,
  Job,
  JobStatus,
  SkillProficiency,
  WorkMode,
  Candidate,
  CandidateSkill,
  Organization,
  OrgSettings,
  JobDetail,
  FairnessRubricConfig,
  CandidateDetail,
  CandidateInPipeline,
  CandidateListPage,
  PipelineColumn,
  KanbanStage,
} from "@/types";
import { KANBAN_STAGE_LABELS } from "@/types";

import type {
  BackendApplication,
  BackendApproval,
  BackendDashboardStats,
  BackendAgentStatus,
  BackendAuditEvent,
  BackendFunnelItem,
  BackendMember,
  BackendJob,
  BackendShortlistItem,
  BackendOrgProfile,
  BackendJobDetail,
  BackendCandidateDetail,
  BackendCandidateList,
  BackendPipelineStages,
} from "./index";

const APPLICATION_STAGES: ApplicationStatus[] = [
  "applied",
  "sourced",
  "screening",
  "assessment",
  "hr_interview",
  "tech_interview",
  "decision",
  "hired",
  "rejected",
  "withdrawn",
];

export function normalizeApplicationStage(raw: string): ApplicationStatus {
  const s = (raw || "applied").toLowerCase();
  return APPLICATION_STAGES.includes(s as ApplicationStatus)
    ? (s as ApplicationStatus)
    : "applied";
}

// ── Applications ──────────────────────────────────────────────────────────

export function adaptApplication(a: BackendApplication): Application {
  const stage = normalizeApplicationStage(a.current_stage_code);
  const skillNames = a.candidate_skills ?? [];
  const skills: CandidateSkill[] = skillNames.map((name, i) => ({
    id: `sk-${i}-${name}`,
    skill: name,
    proficiency: "intermediate",
    evidenceCount: 0,
    lastVerified: a.updated_at ?? a.created_at,
    verified: false,
  }));
  const matchScore =
    a.match_final_score != null && !Number.isNaN(a.match_final_score)
      ? Math.round(Number(a.match_final_score))
      : undefined;
  const matchConfidence =
    a.match_confidence != null && !Number.isNaN(a.match_confidence)
      ? Number(a.match_confidence)
      : undefined;
  return {
    id: a.id,
    candidateId: a.candidate_id,
    candidate: {
      id: a.candidate_id,
      name: a.candidate_name ?? "Unknown",
      title: a.candidate_current_title ?? "",
      email: a.candidate_email ?? "",
      location: "",
      experienceYears: 0,
      status: "active" as const,
      isAnonymized: false,
      alias: `Candidate ${a.candidate_id.replace(/-/g, "").slice(0, 6)}`,
      avatar: `https://api.dicebear.com/9.x/avataaars/svg?seed=${encodeURIComponent(a.candidate_id)}`,
      skills,
      evidenceItems: [],
      sources: [],
      createdAt: a.created_at,
      updatedAt: a.updated_at ?? a.created_at,
    },
    jobId: a.job_id,
    job: { id: a.job_id, title: a.job_title ?? "Unknown Job", level: "", department: "" },
    applyDate: a.created_at,
    sourcePlatform: a.source_channel ?? "direct",
    status: stage,
    matchScore,
    matchConfidence,
    isAnonymized: false,
    biasFlags: [],
    roadmap: a.roadmap,
  };
}

export function adaptApplications(items: BackendApplication[]): Application[] {
  return items.map(adaptApplication);
}

// ── Shortlist — adapted to Application shape for the screening page ────────

export function adaptShortlistItem(
  item: BackendShortlistItem,
  jobId: string,
): Application {
  return {
    id: item.application_id,
    candidateId: item.candidate_id,
    candidate: {
      id: item.candidate_id,
      name: item.candidate_name ?? "Unknown",
      title: "",
      email: "",
      location: "",
      experienceYears: 0,
      status: "active" as const,
      isAnonymized: false,
      alias: `Candidate ${item.candidate_id.slice(0, 6)}`,
      avatar: `https://api.dicebear.com/9.x/avataaars/svg?seed=${item.candidate_id}`,
      skills: (item.matched_skills ?? []).map((s, i) => ({
        id: `sk_${i}`,
        skill: s,
        proficiency: "intermediate" as const,
        verified: true,
        evidenceCount: 1,
        lastVerified: new Date().toISOString(),
      })),
      evidenceItems: [],
      sources: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    },
    jobId,
    job: { id: jobId, title: "", level: "", department: "" },
    applyDate: new Date().toISOString(),
    sourcePlatform: "system",
    status: normalizeApplicationStage(item.current_stage_code),
    matchScore:
      item.final_score != null && !Number.isNaN(item.final_score)
        ? Math.round(item.final_score)
        : undefined,
    matchConfidence:
      item.confidence != null && !Number.isNaN(item.confidence)
        ? Number(item.confidence)
        : undefined,
    shortlistRank: item.rank,
    isAnonymized: false,
    explanation: item.explanation ?? undefined,
    matchScores: item.criteria_breakdown
      ? Object.entries(item.criteria_breakdown).map(([dimension, val]) => ({
          dimension,
          raw: typeof val === "number" ? val : (val as Record<string, number>)?.score ?? 0,
          weighted: typeof val === "number" ? val : (val as Record<string, number>)?.weighted ?? 0,
          evidenceCount: 1,
          confidence: item.confidence ?? 0.8,
        }))
      : [],
    biasFlags: [],
  };
}

export function adaptShortlist(items: BackendShortlistItem[], jobId: string): Application[] {
  return items.map((i) => adaptShortlistItem(i, jobId));
}

// ── HITL Approvals ────────────────────────────────────────────────────────

export function adaptApproval(a: BackendApproval): HITLApproval {
  return {
    id: a.id,
    actionType: a.action_type as HITLActionType,
    status: a.status as HITLStatus,
    priority: a.priority as HITLApproval["priority"],
    requestedBy: a.requested_by_name,
    requestedByName: a.requested_by_name,
    requestedAt: a.requested_at,
    decidedBy: a.reviewed_by_name ?? undefined,
    decidedByName: a.reviewed_by_name ?? undefined,
    decidedAt: a.reviewed_at ?? undefined,
    reason: a.reason ?? undefined,
    targetId: a.entity_id,
    targetLabel: a.entity_label,
    jobId: a.entity_type === "job" ? a.entity_id : undefined,
    meta: (a.meta_json ?? {}) as Record<string, unknown>,
  };
}

export function adaptApprovals(items: BackendApproval[]): HITLApproval[] {
  return items.map(adaptApproval);
}

// ── Dashboard Stats ───────────────────────────────────────────────────────

export function adaptDashboardStats(s: BackendDashboardStats): DashboardStats {
  return {
    activeJobs: s.active_jobs,
    totalCandidates: s.total_candidates,
    pendingApprovals: s.pending_approvals,
    avgTimeToHire: s.avg_time_to_hire_days,
    thisWeekApplications: s.applications_this_week,
    shortlistedToday: s.shortlisted_today,
    interviewsScheduled: s.interviews_scheduled,
    hiredThisMonth: s.hired_this_month,
  };
}

// ── Funnel ────────────────────────────────────────────────────────────────

const stageLabelOverride: Record<string, string> = {
  applied: "Applied",
  sourced: "Sourced",
  screening: "Screening",
  assessment: "Assessment",
  hr_interview: "HR Interview",
  tech_interview: "Tech Interview",
  decision: "Decision",
  hired: "Hired",
};

export function adaptFunnel(items: BackendFunnelItem[]): FunnelSnapshot[] {
  return items.map((f) => ({
    stage: f.stage as ApplicationStatus,
    label: stageLabelOverride[f.stage] ?? f.stage,
    count: f.count,
    conversionRate: f.conversionRate,
  }));
}

// ── Agent Status ──────────────────────────────────────────────────────────

export function adaptAgentStatus(a: BackendAgentStatus): AgentStatus {
  return {
    id: a.id,
    name: a.name,
    status: a.status as AgentStatus["status"],
    progress: a.progress,
    currentTask: a.current_task ?? undefined,
    lastRun: a.last_run ?? undefined,
  };
}

export function adaptAgents(items: BackendAgentStatus[]): AgentStatus[] {
  return items.map(adaptAgentStatus);
}

// ── Audit Events ──────────────────────────────────────────────────────────

export function adaptAuditEvent(e: BackendAuditEvent): AuditEvent {
  return {
    id: String(e.id),
    actor: e.actor_id,
    actorName: e.actor_id,
    actorRole: "recruiter" as UserRole,
    action: e.action as AuditAction,
    targetId: e.entity_id,
    targetType: e.entity_type,
    targetLabel: `${e.entity_type}:${e.entity_id}`,
    timestamp: e.created_at,
    ip: "—",
    requestId: String(e.id),
    orgId: "",
    before: e.before_jsonb ?? undefined,
    after: e.after_jsonb ?? undefined,
  };
}

export function adaptAuditEvents(items: BackendAuditEvent[]): AuditEvent[] {
  return items.map(adaptAuditEvent);
}

// ── Members ───────────────────────────────────────────────────────────────

const roleMap: Record<string, UserRole> = {
  org_admin: "admin",
  recruiter: "recruiter",
  hr: "recruiter",
  hr_manager: "hiring_manager",
  hiring_manager: "hiring_manager",
  interviewer: "interviewer",
  candidate: "candidate",
};

export function adaptMember(m: BackendMember): Member {
  // fix8&9 — surface the backend lifecycle status. Fall back to legacy
  // is_active behaviour only when the new field is missing.
  let status: Member["status"];
  if (m.status === "pending") status = "pending";
  else if (m.status === "suspended") status = "suspended";
  else if (m.status === "active") status = "active";
  else status = m.is_active ? "active" : "pending";

  return {
    id: m.id,
    userId: m.user_id,
    name: m.full_name ?? m.email ?? "Unknown",
    email: m.email ?? "",
    role: roleMap[m.role_code] ?? "recruiter",
    status,
    joinedAt: m.joined_at,
    invitedAt: m.invited_at ?? null,
    activatedAt: m.activated_at ?? null,
    firstLoginAt: m.first_login_at ?? null,
    lastActive: m.first_login_at ?? m.activated_at ?? m.joined_at,
    jobsAssigned: 0,
    avatar: `https://api.dicebear.com/9.x/avataaars/svg?seed=${m.email ?? m.id}`,
  };
}

export function adaptMembers(items: BackendMember[]): Member[] {
  return items.map(adaptMember);
}

// ── Jobs ──────────────────────────────────────────────────────────────────

const JOB_STATUS_MAP: Record<string, JobStatus> = {
  draft:     "draft",
  published: "published",
  active:    "published",
  open:      "published",
  live:      "published",
  closed:    "closed",
  filled:    "closed",
  expired:   "closed",
  archived:  "archived",
  paused:    "archived",
};

function normalizeJobStatus(raw: string | undefined | null): JobStatus {
  if (!raw) return "published";
  return JOB_STATUS_MAP[raw.toLowerCase()] ?? "published";
}

export function adaptJob(j: BackendJob): Job {
  const company =
    j.company_name ?? j.company ?? undefined;
  const extUrl = j.job_url ?? j.source_url ?? undefined;
  const srcPlat = j.source_platform ?? j.source_type ?? undefined;
  const created = j.created_at ? new Date(j.created_at).toISOString() : new Date().toISOString();
  const updated = j.updated_at ? new Date(j.updated_at).toISOString() : created;
  return {
    id: j.id,
    orgId: "",
    title: j.title,
    level: j.seniority_level ?? "",
    department: j.role_family ?? "",
    location: j.location_text ?? "",
    workMode: (j.workplace_type ?? j.location_mode ?? "onsite") as WorkMode,
    mode: "inbound" as const,
    status: normalizeJobStatus(j.status),
    salaryMin: j.salary_min ?? undefined,
    salaryMax: j.salary_max ?? undefined,
    currency: j.salary_currency ?? "USD",
    headcount: 1,
    skills: (j.skills ?? []).map((s) => ({
      skill: s.name,
      required: s.required,
      weight: 1,
      minProficiency: "intermediate" as SkillProficiency,
    })),
    rubric: [],
    pipeline: (j.pipeline_breakdown ?? []).map((s, i) => ({
      stage: s.stage as ApplicationStatus,
      label: s.label,
      order: i,
      hitlRequired: false,
      count: s.count,
    })),
    collaborators: [],
    createdAt: created,
    updatedAt: updated,
    applicantCount: j.applicant_count ?? 0,
    shortlistedCount: 0,
    companyName: company,
    sourcePlatform: srcPlat ?? undefined,
    externalJobUrl: extUrl ?? undefined,
  };
}

export function adaptJobs(items: BackendJob[]): Job[] {
  return items.map(adaptJob);
}

// ── Recruiter candidate detail (GET /candidates/{id}) ─────────────────────

export interface BackendRecruiterCandidateBundle {
  candidate: {
    id: string;
    full_name: string;
    email?: string | null;
    phone?: string | null;
    location_text?: string | null;
    current_title?: string | null;
    headline?: string | null;
    summary?: string | null;
    years_experience?: number | null;
    career_level?: string | null;
    skills?: string[];
  };
  skills?: { skill_id: string; score: number }[];
  experiences?: { company: string; title: string }[];
  education?: { institution: string; degree: string }[];
  certifications?: { name: string; issuer: string }[];
}

export function adaptRecruiterCandidateDetail(raw: BackendRecruiterCandidateBundle): Candidate {
  const c = raw.candidate;
  const id = String(c.id);
  const fromProfile = (c.skills ?? []).map((name, i) => ({
    id: `sk-p-${i}-${name}`,
    skill: name,
    proficiency: "intermediate" as const,
    evidenceCount: 0,
    lastVerified: new Date().toISOString(),
    verified: false,
  }));
  const fromScored = (raw.skills ?? []).map((s, i) => ({
    id: `sk-s-${i}-${s.skill_id}`,
    skill: s.skill_id,
    proficiency: "intermediate" as const,
    evidenceCount: 0,
    lastVerified: new Date().toISOString(),
    verified: false,
  }));
  const skills = fromProfile.length > 0 ? fromProfile : fromScored;
  const title = (c.current_title || c.headline || "").trim();
  return {
    id,
    alias: `Candidate ${id.replace(/-/g, "").slice(0, 6)}`,
    name: c.full_name ?? "Unknown",
    email: c.email ?? "",
    phone: c.phone ?? undefined,
    title,
    location: c.location_text ?? "",
    experienceYears: c.years_experience ?? 0,
    status: "active",
    skills,
    evidenceItems: [],
    sources: [],
    isAnonymized: false,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
}

// ── Organization (settings page) — backend only exposes a subset ──────────

const DEFAULT_ORG_SETTINGS: OrgSettings = {
  scoringWeights: {},
  defaultTopK: 10,
  anonymizationLevel: "standard",
  outboundSourcingEnabled: false,
  assessmentEnabled: false,
  retentionDays: 365,
};

export function adaptOrganizationFromBackend(o: BackendOrgProfile): Organization {
  return {
    id: o.id,
    name: o.name,
    plan: "starter",
    region: "",
    locale: "en",
    industry: o.industry ?? "",
    // Real company size from its own column (was hardcoded to "1-10").
    headcount: o.companySize ?? "",
    // Was hardcoded to "" — meant Save → refetch always restored a
    // blank value, so the recruiter thought the website wasn't saving.
    website: o.website ?? "",
    createdAt: new Date().toISOString(),
    memberCount: 0,
    activeJobCount: 0,
    settings: { ...DEFAULT_ORG_SETTINGS },
  };
}

// ── Phase 1 adapters ──────────────────────────────────────────────────────

export function adaptJobDetail(b: BackendJobDetail): JobDetail {
  return {
    id: b.id,
    title: b.title,
    department: b.department,
    location: b.location,
    employmentType: b.employment_type,
    salaryMin: b.salary_min,
    salaryMax: b.salary_max,
    description: b.description,
    requiredSkills: b.required_skills,
    optionalSkills: b.optional_skills,
    status: b.status,
    postedAt: b.posted_at,
    createdAt: b.created_at,
    updatedAt: b.updated_at,
    stats: {
      totalCandidates: b.stats.total_candidates,
      byStage: b.stats.by_stage,
    },
    fairnessRubric: b.fairness_rubric
      ? {
          protectedAttrs: b.fairness_rubric.protected_attrs,
          disparateImpactThreshold: b.fairness_rubric.disparate_impact_threshold,
          enabled: b.fairness_rubric.enabled,
        }
      : null,
    hiringPipeline: (b.hiring_pipeline ?? []).map((s) => ({
      key: s.key,
      kind: s.kind,
      label: s.label,
      group: s.group ?? "interview",
    })),
  };
}

export function adaptPipelineStages(b: BackendPipelineStages): PipelineColumn[] {
  return b.stages.map((s) => ({
    key: s.key as KanbanStage,
    label: KANBAN_STAGE_LABELS[s.key as KanbanStage] ?? s.key,
    count: s.count,
    preview: s.preview,
  }));
}

export function adaptCandidateList(b: BackendCandidateList): CandidateListPage {
  return {
    items: b.items.map((item) => ({
      id: item.id,
      applicationId: item.application_id,
      name: item.name,
      headline: item.headline,
      overallScore: item.overall_score,
      matchScore: item.match_score ?? null,
      interviewScore: item.interview_score ?? null,
      decisionScore: item.decision_score ?? null,
      matchedSkills: item.matched_skills ?? [],
      pipelineStage: item.pipeline_stage as KanbanStage,
      sourceChannel: item.source_channel,
      createdAt: item.created_at,
    })),
    total: b.total,
    page: b.page,
    pageSize: b.page_size,
  };
}

export function adaptCandidateDetail(b: BackendCandidateDetail): CandidateDetail {
  return {
    id: b.id,
    name: b.name,
    headline: b.headline,
    location: b.location,
    emailMasked: b.email_masked,
    phoneMasked: b.phone_masked,
    currentRole: b.current_role,
    yearsExperience: b.years_experience,
    overallScore: b.overall_score,
    pipelineStage: b.pipeline_stage as KanbanStage | null,
    cv: {
      experience: b.cv.experience.map((e) => ({
        company: e.company,
        title: e.title,
        startDate: e.start_date,
        endDate: e.end_date,
        description: e.description,
      })),
      education: b.cv.education.map((e) => ({
        institution: e.institution,
        degree: e.degree,
        field: e.field,
        graduationYear: e.graduation_year,
      })),
      skills: b.cv.skills.map((s) => ({ skillId: s.skill_id, proficiency: s.proficiency })),
      certifications: b.cv.certifications,
    },
    scores: b.scores,
    activity: b.activity,
  };
}

import type { BackendRoadmap } from "@/lib/api";

// ─── Core Enums ──────────────────────────────────────────────────────────────

export type UserRole =
  | "recruiter"
  | "hiring_manager"
  | "interviewer"
  | "admin"
  | "super_admin"
  | "candidate";

export type CandidateStatus =
  | "active"
  | "passive"
  | "hired"
  | "rejected"
  | "withdrawn";

export type ApplicationStatus =
  | "applied"
  | "sourced"
  | "screening"
  | "assessment"
  | "hr_interview"
  | "tech_interview"
  | "decision"
  | "hired"
  | "rejected"
  | "withdrawn";

export type JobStatus = "draft" | "published" | "closed" | "archived";

export type JobMode = "inbound" | "outbound" | "hybrid";

export type WorkMode = "remote" | "onsite" | "hybrid";

export type HITLActionType =
  | "shortlist_approve"
  | "outreach_approve"
  | "assessment_decision"
  | "interview_finalize"
  | "decision_finalize"
  | "deanonymize"
  | "merge_candidates";

export type HITLStatus = "pending" | "approved" | "rejected" | "expired";

export type EvidenceType =
  | "cv_claim"
  | "github_repo"
  | "portfolio_artifact"
  | "assessment"
  | "interview";

export type SkillProficiency = "beginner" | "intermediate" | "advanced" | "expert";

// ─── User & Auth ─────────────────────────────────────────────────────────────

export type OrganizationStatus =
  | "pending_approval"
  | "active"
  | "rejected"
  | "suspended";

export interface User {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  role: UserRole;
  /** Backend ``account_type``: ``candidate`` | ``organization_member`` | ``platform_admin`` */
  accountType?: string;
  orgId: string;
  orgName: string;
  /** Lifecycle status of the user's organisation. ``null`` for candidates / platform admins. */
  organizationStatus?: OrganizationStatus | null;
  /** True iff the user has ``account_type='platform_admin'``. */
  isPlatformAdmin?: boolean;
  /** Frontend-side permission strings the backend sends in /auth/me. */
  permissions?: string[];
  createdAt: string;
  lastLogin: string;
  mfaEnabled: boolean;
  status: "active" | "invited" | "suspended";
}

// ─── Candidate ────────────────────────────────────────────────────────────────

export interface CandidateSkill {
  id: string;
  skill: string;
  proficiency: SkillProficiency;
  evidenceCount: number;
  lastVerified: string;
  verified: boolean;
}

export interface EvidenceItem {
  id: string;
  candidateId: string;
  type: EvidenceType;
  sourceUri: string;
  extractedText: string;
  confidence: number;
  timestamp: string;
  source: string;
}

export interface Candidate {
  id: string;
  alias: string;
  name: string;
  email: string;
  phone?: string;
  avatar?: string;
  title: string;
  location: string;
  experienceYears: number;
  status: CandidateStatus;
  skills: CandidateSkill[];
  evidenceItems: EvidenceItem[];
  sources: string[];
  linkedinUrl?: string;
  githubLogin?: string;
  portfolioUrl?: string;
  isAnonymized: boolean;
  createdAt: string;
  updatedAt: string;
}

// ─── Job ─────────────────────────────────────────────────────────────────────

export interface JobSkill {
  skill: string;
  required: boolean;
  weight: number;
  minProficiency: SkillProficiency;
}

export interface JobRubricDimension {
  dimension: string;
  weight: number;
  threshold: number;
}

export interface Job {
  id: string;
  orgId: string;
  title: string;
  level: string;
  department: string;
  location: string;
  workMode: WorkMode;
  mode: JobMode;
  status: JobStatus;
  salaryMin?: number;
  salaryMax?: number;
  currency: string;
  headcount: number;
  skills: JobSkill[];
  rubric: JobRubricDimension[];
  pipeline: PipelineStage[];
  collaborators: string[];
  openedAt?: string;
  closedAt?: string;
  createdAt: string;
  updatedAt: string;
  applicantCount: number;
  shortlistedCount: number;
  /** Present for scraped / external listings */
  companyName?: string;
  sourcePlatform?: string;
  externalJobUrl?: string;
}

export interface PipelineStage {
  stage: ApplicationStatus;
  label: string;
  order: number;
  hitlRequired: boolean;
  count: number;
}

// ─── Application ─────────────────────────────────────────────────────────────

export interface MatchScore {
  dimension: string;
  raw: number;
  weighted: number;
  evidenceCount: number;
  confidence: number;
}

export interface BiasFlag {
  rule: string;
  severity: "low" | "medium" | "high";
  description: string;
}

export interface Application {
  id: string;
  candidateId: string;
  candidate: Candidate;
  jobId: string;
  job: Pick<Job, "id" | "title" | "level" | "department">;
  status: ApplicationStatus;
  sourcePlatform: string;
  shortlistRank?: number;
  applyDate: string;
  matchScore?: number;
  matchConfidence?: number;
  matchScores?: MatchScore[];
  explanation?: string;
  evidenceIds?: string[];
  biasFlags?: BiasFlag[];
  isAnonymized: boolean;
  /** Progress against the job's configured hiring pipeline (Applied → custom
   *  stages → Offer → Hired), as computed by the backend. */
  roadmap?: BackendRoadmap;
}

// ─── HITL Approval ───────────────────────────────────────────────────────────

export interface HITLApproval {
  id: string;
  actionType: HITLActionType;
  targetId: string;
  targetLabel: string;
  requestedBy: string;
  requestedByName: string;
  requestedAt: string;
  status: HITLStatus;
  decidedBy?: string;
  decidedByName?: string;
  decidedAt?: string;
  reason?: string;
  priority: "low" | "medium" | "high" | "critical";
  jobId?: string;
  jobTitle?: string;
  candidateAlias?: string;
  meta?: Record<string, unknown>;
}

// ─── Assessment ──────────────────────────────────────────────────────────────

export interface Assessment {
  id: string;
  applicationId: string;
  candidateAlias: string;
  type: "mcq" | "coding" | "case" | "take_home";
  status: "pending" | "delivered" | "submitted" | "graded" | "decided";
  score?: number;
  maxScore: number;
  dueAt: string;
  submittedAt?: string;
  gradedAt?: string;
  pass?: boolean;
  rationale?: string;
}

// ─── Interview ───────────────────────────────────────────────────────────────

export interface Interview {
  id: string;
  applicationId: string;
  type: "hr" | "technical" | "final";
  status: "scheduled" | "in_progress" | "completed" | "cancelled";
  scheduledAt: string;
  mode: "video" | "onsite" | "phone";
  interviewers: string[];
  scorecard?: {
    overall: number;
    dimensions: Array<{ dimension: string; score: number; rationale: string }>;
  };
}

// ─── Member / Org ─────────────────────────────────────────────────────────────

export interface Member {
  id: string;
  userId: string;
  name: string;
  email: string;
  avatar?: string;
  role: UserRole;
  // fix8&9 Update 2 — "pending" appears for invited members who haven't
  // logged in yet; "active" once they sign in; "inactive" once a pending
  // invite expires (no sign-in within the grace window).
  status: "active" | "pending" | "invited" | "suspended" | "inactive";
  joinedAt: string;
  invitedAt?: string | null;
  activatedAt?: string | null;
  firstLoginAt?: string | null;
  lastActive: string;
  jobsAssigned: number;
}

export interface Organization {
  id: string;
  name: string;
  logoUrl?: string;
  plan: "starter" | "growth" | "enterprise";
  region: string;
  locale: string;
  industry: string;
  headcount: string;
  website?: string;
  createdAt: string;
  memberCount: number;
  activeJobCount: number;
  settings: OrgSettings;
}

export interface OrgSettings {
  scoringWeights: Record<string, number>;
  defaultTopK: number;
  anonymizationLevel: "strict" | "standard" | "minimal";
  outboundSourcingEnabled: boolean;
  assessmentEnabled: boolean;
  retentionDays: number;
}

// ─── Audit ───────────────────────────────────────────────────────────────────

export type AuditAction =
  | "candidate.created"
  | "candidate.updated"
  | "candidate.merged"
  | "candidate.deanonymized"
  | "job.created"
  | "job.published"
  | "job.closed"
  | "application.created"
  | "application.status_changed"
  | "shortlist.proposed"
  | "shortlist.approved"
  | "shortlist.rejected"
  | "outreach.sent"
  | "assessment.generated"
  | "assessment.decided"
  | "interview.scheduled"
  | "interview.finalized"
  | "decision.finalized"
  | "member.invited"
  | "member.role_changed"
  | "member.removed"
  | "org.settings_updated";

export interface AuditEvent {
  id: string;
  actor: string;
  actorName: string;
  actorRole: UserRole;
  action: AuditAction;
  targetId: string;
  targetType: string;
  targetLabel: string;
  before?: Record<string, unknown>;
  after?: Record<string, unknown>;
  ip: string;
  requestId: string;
  timestamp: string;
  orgId: string;
}

// ─── Analytics ───────────────────────────────────────────────────────────────

export interface FunnelSnapshot {
  stage: ApplicationStatus;
  label: string;
  count: number;
  conversionRate: number;
}

export interface DashboardStats {
  activeJobs: number;
  totalCandidates: number;
  pendingApprovals: number;
  avgTimeToHire: number;
  thisWeekApplications: number;
  shortlistedToday: number;
  interviewsScheduled: number;
  hiredThisMonth: number;
}

// ─── Sourcing ─────────────────────────────────────────────────────────────────

export interface SourcingRun {
  id: string;
  jobId: string;
  jobTitle: string;
  query: string;
  sources: string[];
  status: "running" | "completed" | "failed" | "paused";
  startedAt: string;
  finishedAt?: string;
  resultCount: number;
  addedCount: number;
  agentId: string;
}

// ─── Phase 1: Job Detail Hub & Pipeline Board ────────────────────────────────

export type KanbanStage =
  | "define" | "source" | "screen" | "shortlist"
  | "reveal" | "outreach" | "interview" | "evaluate" | "decide";

export const KANBAN_STAGE_LABELS: Record<KanbanStage, string> = {
  define: "Define",
  source: "Source",
  screen: "Screen",
  shortlist: "Shortlist",
  reveal: "Reveal",
  outreach: "Outreach",
  interview: "Interview",
  evaluate: "Evaluate",
  decide: "Decide",
};

export const KANBAN_STAGES: KanbanStage[] = [
  "define", "source", "screen", "shortlist",
  "reveal", "outreach", "interview", "evaluate", "decide",
];

export interface FairnessRubricConfig {
  protectedAttrs: Record<string, boolean>;
  disparateImpactThreshold: number;
  enabled: boolean;
}

export interface SkillWeight { name: string; weight: number; }

export interface StageStats {
  define: number; source: number; screen: number; shortlist: number;
  reveal: number; outreach: number; interview: number; evaluate: number; decide: number;
}

export interface JobDetailStats {
  totalCandidates: number;
  byStage: StageStats;
}

export interface JobDetail {
  id: string;
  title: string;
  department: string | null;
  location: string | null;
  employmentType: string | null;
  salaryMin: number | null;
  salaryMax: number | null;
  description: string | null;
  requiredSkills: SkillWeight[];
  optionalSkills: SkillWeight[];
  status: string;
  postedAt: string | null;
  createdAt: string | null;
  updatedAt: string | null;
  stats: JobDetailStats;
  fairnessRubric: FairnessRubricConfig | null;
  hiringPipeline: { key: string; kind: string; label: string; group: string }[];
}

export interface CandidateCardPreview {
  id: string;
  name: string;
  score: number | null;
}

export interface PipelineColumn {
  key: KanbanStage;
  label: string;
  count: number;
  preview: CandidateCardPreview[];
}

export interface CandidateInPipeline {
  id: string;
  applicationId: string;
  name: string;
  headline: string | null;
  overallScore: number | null;
  matchScore: number | null;
  interviewScore: number | null;
  decisionScore: number | null;
  matchedSkills: string[];
  pipelineStage: KanbanStage;
  sourceChannel: string | null;
  createdAt: string | null;
}

export interface CandidateListPage {
  items: CandidateInPipeline[];
  total: number;
  page: number;
  pageSize: number;
}

export interface ScoreCriterion {
  criterion: string;
  score: number | null;
  weight: number | null;
  reasoning: string | null;
}

export interface ActivityEvent {
  type: string;
  at: string;
  actor: string;
  payload: Record<string, unknown>;
}

export interface CvExperience {
  company: string;
  title: string;
  startDate: string | null;
  endDate: string | null;
  description: string | null;
}

export interface CvEducation {
  institution: string;
  degree: string | null;
  field: string | null;
  graduationYear: number | null;
}

export interface CandidateDetail {
  id: string;
  name: string;
  headline: string | null;
  location: string | null;
  emailMasked: string | null;
  phoneMasked: string | null;
  currentRole: string | null;
  yearsExperience: number | null;
  overallScore: number | null;
  pipelineStage: KanbanStage | null;
  cv: {
    experience: CvExperience[];
    education: CvEducation[];
    skills: { skillId: string; proficiency: number | null }[];
    certifications: { name: string; issuer: string | null }[];
  };
  scores: ScoreCriterion[];
  activity: ActivityEvent[];
}

// ─── Agent ───────────────────────────────────────────────────────────────────

export interface AgentStatus {
  id: string;
  name: string;
  status: "idle" | "running" | "completed" | "failed";
  lastRun?: string;
  currentTask?: string;
  progress?: number;
}

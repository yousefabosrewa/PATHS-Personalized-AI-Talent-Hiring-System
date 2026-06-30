# PATHS Backend — DB models package

from app.db.models.base import Base
from app.db.models.organization import (
    Organization,
    OrganizationStatus,
    OrganizationAccessRequest,
    OrganizationAccessRequestStatus,
)
from app.db.models.user import User
from app.db.models.candidate import Candidate
from app.db.models.job import Job
from app.db.models.application import Application
from app.db.models.ingestion import IngestionJob, OutboxEvent
from app.db.models.cv_entities import CandidateDocument, Skill, CandidateSkill, CandidateExperience, CandidateEducation, CandidateCertification
from app.db.models.job_ingestion import JobSourceRun, JobRawItem, JobSkillRequirement, IngestionError, JobVectorProjectionStatus
from app.db.models.reference import Company, Location
from app.db.models.candidate_extras import CandidateContact, CandidateProject, CandidateLink
from app.db.models.sync import DBSyncStatus, AuditLog, CandidateJobMatch
from app.db.models.job_scraper import (
    JobSkillLink,
    JobRequirementText,
    JobResponsibility,
    JobImportRun,
    JobImportError,
    JobScraperState,
)
from app.db.models.scoring import (
    CandidateJobScore,
    ScoringRun,
    ScoringError,
    ScoringCriteriaConfig,
)
from app.db.models.organization_matching import (
    OrganizationJobRequest,
    OrganizationMatchingRun,
    OrganizationCandidateImport,
    OrganizationCandidateImportError,
    OrganizationBlindCandidateMap,
    OrganizationCandidateRanking,
    OrganizationOutreachMessage,
)
from app.db.models.interview import (
    Interview,
    InterviewParticipant,
    InterviewQuestionPack,
    InterviewTranscript,
    InterviewSummary,
    InterviewEvaluation,
    InterviewDecisionPacket,
    InterviewHumanDecision,
)
from app.db.models.decision_support import (
    DecisionEmail,
    DecisionScoreBreakdown,
    DecisionSupportPacket,
    DevelopmentPlan,
    HrFinalDecision,
)
from app.db.models.screening import (
    ScreeningRun,
    ScreeningResult,
)
from app.db.models.outreach_agent import (
    GoogleIntegration,
    OutreachSession,
    OutreachAvailabilityWindow,
    InterviewBooking,
)
from app.db.models.assessment import Assessment
from app.db.models.bias_fairness import (
    AnonymizedView,
    BiasFlag,
    DeAnonEvent,
    BiasAuditLog,
)
from app.db.models.fairness_rubric import FairnessRubric
from app.db.models.evidence import EvidenceItem, CandidateSource
from app.db.models.hitl import HITLApproval
from app.db.models.contact_enrichment import EnrichedContact
from app.db.models.identity_resolution import CandidateDuplicate, MergeHistory
from app.db.models.candidate_sourcing import (
    OrganizationCandidateSourceSettings,
    JobCandidatePoolConfig,
    CandidatePoolRun,
    CandidatePoolMember,
)
from app.db.models.external_candidate import (
    ExternalCandidate,
    ExternalCandidateBatch,
)
from app.db.models.company_knowledge import CompanyKnowledgeFile
from app.db.models.candidate_merge import CandidateMergeAudit
from app.db.models.bias_reports import BiasReport
from app.db.models.analytics_events import AnalyticsEvent
from app.db.models.agent_runs import AgentRun
from app.db.models.growth_plans import GrowthPlan
from app.db.models.billing import (
    Plan,
    Subscription,
    Invoice,
    UsageCounter,
    StripeProcessedEvent,
    PasswordResetToken,
)
from app.db.models.admin_platform import (
    FeatureFlag,
    FeatureFlagOverride,
    PlatformSettings,
    Announcement,
    ImpersonationSession,
)

__all__ = [
    "Base",
    "Organization",
    "OrganizationStatus",
    "OrganizationAccessRequest",
    "OrganizationAccessRequestStatus",
    "User",
    "Candidate",
    "Job",
    "Application",
    "IngestionJob",
    "OutboxEvent",
    "CandidateDocument",
    "Skill",
    "CandidateSkill",
    "CandidateExperience",
    "CandidateEducation",
    "CandidateCertification",
    "JobSourceRun",
    "JobRawItem",
    "JobSkillRequirement",
    "IngestionError",
    "JobVectorProjectionStatus",
    # New unified-integration entities
    "Company",
    "Location",
    "CandidateContact",
    "CandidateProject",
    "CandidateLink",
    "DBSyncStatus",
    "AuditLog",
    "CandidateJobMatch",
    # Job-scraper-specific entities
    "JobSkillLink",
    "JobRequirementText",
    "JobResponsibility",
    "JobImportRun",
    "JobImportError",
    "JobScraperState",
    # Candidate-Job scoring
    "CandidateJobScore",
    "ScoringRun",
    "ScoringError",
    "ScoringCriteriaConfig",
    # Organization-side matching + outreach
    "OrganizationJobRequest",
    "OrganizationMatchingRun",
    "OrganizationCandidateImport",
    "OrganizationCandidateImportError",
    "OrganizationBlindCandidateMap",
    "OrganizationCandidateRanking",
    "OrganizationOutreachMessage",
    # Interview intelligence
    "Interview",
    "InterviewParticipant",
    "InterviewQuestionPack",
    "InterviewTranscript",
    "InterviewSummary",
    "InterviewEvaluation",
    "InterviewDecisionPacket",
    "InterviewHumanDecision",
    "DecisionSupportPacket",
    "DecisionScoreBreakdown",
    "HrFinalDecision",
    "DevelopmentPlan",
    "DecisionEmail",
    # Screening agent
    "ScreeningRun",
    "ScreeningResult",
    # Outreach Agent
    "GoogleIntegration",
    "OutreachSession",
    "OutreachAvailabilityWindow",
    "InterviewBooking",
    # Assessment Agent
    "Assessment",
    # Bias & Fairness
    "AnonymizedView",
    "BiasFlag",
    "DeAnonEvent",
    "BiasAuditLog",
    "FairnessRubric",
    # Evidence
    "EvidenceItem",
    "CandidateSource",
    # HITL
    "HITLApproval",
    # Contact Enrichment
    "EnrichedContact",
    # Identity Resolution
    "CandidateDuplicate",
    "MergeHistory",
    # Candidate Sourcing & Pool
    "OrganizationCandidateSourceSettings",
    "JobCandidatePoolConfig",
    "CandidatePoolRun",
    "CandidatePoolMember",
    # fix6.md — External candidate sourcing (preview before import)
    "ExternalCandidate",
    "ExternalCandidateBatch",
    # fix2_1.md — Company knowledge files + candidate merge
    "CompanyKnowledgeFile",
    "CandidateMergeAudit",
    # Phase 2 — Bias Reports & Analytics
    "BiasReport",
    "AnalyticsEvent",
    # Phase 2/3 — Agent Runs & Growth Plans
    "AgentRun",
    "GrowthPlan",
    # Phase 6 — Billing & Commercial Launch
    "Plan",
    "Subscription",
    "Invoice",
    "UsageCounter",
    "StripeProcessedEvent",
    "PasswordResetToken",
    # Phase 7 — Admin & Owner Portals
    "FeatureFlag",
    "FeatureFlagOverride",
    "PlatformSettings",
    "Announcement",
    "ImpersonationSession",
]

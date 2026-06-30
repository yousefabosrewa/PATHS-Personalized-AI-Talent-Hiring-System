"use client";

import { use, useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import {
  ArrowLeft, Shield, ShieldOff, GitFork, Link2, Globe,
  Star, CheckCircle2, AlertCircle, Clock, MapPin, Briefcase,
  BookOpen, ExternalLink, ChevronRight, Brain, Send,
} from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useCandidate, useApplications, useEvidenceItems, useCandidateSources, useDeanonStatus, useRequestDeanon, useBiasFlags, useContactEnrichmentStatus } from "@/lib/hooks";
import { OutreachModal } from "@/components/outreach/outreach-modal";
import { SkillEvidencePanel } from "@/components/features/candidates/SkillEvidencePanel";
import { PreparationPanel } from "@/components/features/candidates/PreparationPanel";
import { useAuthStore } from "@/lib/stores/auth.store";
import { cn } from "@/lib/utils/cn";
import { shortDate, initials, confidenceLabel, confidenceColor, relativeTime } from "@/lib/utils/format";
import type { EvidenceType } from "@/types";
import type { BackendRoadmap } from "@/lib/api";

/**
 * Candidate progress against ONE job's *configured hiring pipeline* — the exact
 * workflow the recruiter set up when creating the job (Applied → their custom
 * stages → Offer → Hired). Uses the backend-computed roadmap so this view is
 * identical to what the candidate sees, and highlights the current stage.
 */
function ApplicationPipeline({ roadmap }: { roadmap: BackendRoadmap | undefined }) {
  if (!roadmap || !roadmap.steps?.length) return null;
  const steps = roadmap.steps;
  const currentLabel = steps.find((s) => s.state === "current")?.label;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          Pipeline progress
        </p>
        <p className="text-[10px] text-muted-foreground/70">
          {roadmap.terminal ? (
            <span className="font-medium text-rose-400">{roadmap.terminal_label ?? "Closed"}</span>
          ) : (
            <>Currently: <span className="text-primary font-medium">{currentLabel ?? "—"}</span></>
          )}
        </p>
      </div>
      <div className="flex items-center gap-1 overflow-x-auto">
        {steps.map((step, i) => {
          const reached = step.state === "done" || step.state === "current";
          const isCur = step.state === "current";
          return (
            <div key={step.key} className="flex items-center gap-1 flex-1 min-w-0">
              <div
                className={cn(
                  "flex h-6 w-full items-center justify-center rounded px-1 text-[9px] font-semibold uppercase tracking-wider whitespace-nowrap",
                  isCur
                    ? "bg-primary text-primary-foreground ring-2 ring-primary/30"
                    : reached
                      ? "bg-primary/15 text-primary"
                      : "bg-muted/30 text-muted-foreground/40",
                )}
                title={step.label}
              >
                {step.label}
              </div>
              {i < steps.length - 1 && (
                <div className={cn(
                  "h-px w-2 shrink-0",
                  !roadmap.terminal && i < roadmap.current_index ? "bg-primary/40" : "bg-border/30",
                )} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

const evidenceIcon: Record<EvidenceType, typeof Star> = {
  cv_claim:           BookOpen,
  github_repo:        GitFork,
  portfolio_artifact: Globe,
  assessment:         CheckCircle2,
  interview:          Star,
};

export default function CandidateProfilePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: candidate, isLoading } = useCandidate(id);
  const { data: apps = [] } = useApplications();
  const candidateApps = apps.filter((a) => a.candidateId === id);

  // Phase 2 — real evidence & sources
  const { data: evidenceItems = [] } = useEvidenceItems(id);
  const { data: candidateSources = [] } = useCandidateSources(id);
  const { data: deanonStatus } = useDeanonStatus(id);
  const requestDeanon = useRequestDeanon();

  const handleRequestDeanon = () => {
    requestDeanon.mutate({ candidateId: id, purpose: "outreach" });
  };

  const [outreachOpen, setOutreachOpen] = useState(false);
  const { user: authUser } = useAuthStore();
  const role = String(authUser?.role ?? authUser?.accountType ?? "").toLowerCase();
  const isHrUser =
    role === "admin" ||
    role === "hr" ||
    role === "hr_manager" ||
    role === "recruiter" ||
    role === "hiring_manager" ||
    role === "manager" ||
    role === "lead";

  const deanonPending = deanonStatus?.granted_at == null && deanonStatus?.denied_at == null && deanonStatus != null;
  const deanonRejected = deanonStatus?.denied_at != null && deanonStatus?.granted_at == null;

  // fix3.md §1 — Fairness-first default.  HR / recruiter / hiring-manager
  // users see the candidate as anonymized until they have an approved
  // de-anon request for this candidate.  We OR with the adapter's
  // `isAnonymized` so anything the backend already masked stays masked.
  const identityApproved = Boolean(deanonStatus?.granted_at);
  const effectiveAnonymized =
    candidate?.isAnonymized === true ||
    (isHrUser && !identityApproved);
  // Helper: the name to render in headers, breadcrumbs and image alts.
  // Always falls back to a deterministic alias so the real name never
  // appears unless approval is granted.
  const displayName = effectiveAnonymized
    ? (candidate?.alias ?? `Candidate ${id.slice(0, 6)}`)
    : (candidate?.name ?? candidate?.alias ?? "Candidate");
  const { data: allFlags = [] } = useBiasFlags({ scope: "candidate" });
  const candidateBiasFlags = allFlags.filter((f) => f.scope_id === id);
  const { data: enrichmentStatus } = useContactEnrichmentStatus();

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="space-y-2 text-center">
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-primary border-t-transparent mx-auto" />
          <p className="text-sm text-muted-foreground">Loading profile…</p>
        </div>
      </div>
    );
  }

  if (!candidate) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-muted-foreground">Candidate not found.</p>
      </div>
    );
  }

  const topApp = candidateApps[0];

  return (
    <div className="h-full overflow-y-auto">
      {/* Header strip */}
      <div className="sticky top-0 z-10 border-b border-border/50 bg-background/80 backdrop-blur-sm px-6 py-3 flex items-center justify-between">
        <Link href="/candidates">
          <Button variant="ghost" size="sm" className="gap-1.5 text-muted-foreground hover:text-foreground -ml-2">
            <ArrowLeft className="h-3.5 w-3.5" /> Back to Pipeline
          </Button>
        </Link>
        <div className="flex items-center gap-2">
          {/* Candidate.md §1 — Decision Support + Outreach kept; "Open
              Preparation" removed (Preparation lives in the tab below). */}
          <Link href={`/candidates/${id}/decision`}>
            <Button size="sm" className="h-8 gap-1.5 text-xs glow-blue">
              <Brain className="h-3 w-3" /> Decision Support
            </Button>
          </Link>
          {isHrUser && (
            <Button
              size="sm"
              variant="secondary"
              className="h-8 gap-1.5 text-xs"
              onClick={() => setOutreachOpen(true)}
            >
              <Send className="h-3 w-3" /> Outreach
            </Button>
          )}
          {/* Candidate.md §1/§2 — single stateful de-anonymization control.
              "Anonymized approval pending" badge removed; the button label
              reflects request status (none / pending / approved / rejected). */}
          {identityApproved ? (
            <Badge variant="outline" className="gap-1.5 border-emerald-500/30 text-emerald-400">
              <Shield className="h-3 w-3" /> Identity Visible
            </Badge>
          ) : deanonPending ? (
            <Button
              size="sm"
              variant="outline"
              className="h-8 gap-1.5 text-xs border-amber-500/40 text-amber-400"
              disabled
            >
              <Clock className="h-3 w-3" /> De-anonymization request pending
            </Button>
          ) : deanonRejected ? (
            <Button
              size="sm"
              variant="outline"
              className="h-8 gap-1.5 text-xs border-rose-500/40 text-rose-400"
              onClick={handleRequestDeanon}
              disabled={requestDeanon.isPending}
              title="Request was rejected — click to request again"
            >
              {requestDeanon.isPending ? (
                <span className="h-3 w-3 animate-spin rounded-full border border-current border-t-transparent" />
              ) : (
                <ShieldOff className="h-3 w-3" />
              )}
              De-anonymization request rejected
            </Button>
          ) : (
            <Button
              size="sm"
              className="h-8 gap-1.5 text-xs"
              onClick={handleRequestDeanon}
              disabled={requestDeanon.isPending}
            >
              {requestDeanon.isPending ? (
                <span className="h-3 w-3 animate-spin rounded-full border border-current border-t-transparent" />
              ) : (
                <ShieldOff className="h-3 w-3" />
              )}
              De-anonymize this candidate
            </Button>
          )}
        </div>
      </div>

      <div className="p-6 space-y-6 max-w-5xl">
        {/* Profile hero */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass gradient-border rounded-2xl p-6"
        >
          <div className="flex flex-col gap-6 md:flex-row md:items-start">
            <div className="flex items-start gap-4">
              <div className="relative">
                <Avatar className="h-20 w-20 ring-2 ring-primary/20">
                  {!effectiveAnonymized && <AvatarImage src={candidate.avatar} alt={displayName} />}
                  <AvatarFallback className="bg-primary/10 text-primary text-2xl font-bold">
                    {effectiveAnonymized ? "?" : initials(displayName)}
                  </AvatarFallback>
                </Avatar>
              </div>
              <div className="space-y-1 min-w-0">
                <h1 className="font-heading text-2xl font-bold tracking-tight text-foreground">
                  {displayName}
                </h1>
                <p className="text-base text-muted-foreground">{candidate.title}</p>
                <div className="flex flex-wrap items-center gap-3 text-[13px] text-muted-foreground">
                  <span className="flex items-center gap-1.5"><MapPin className="h-3.5 w-3.5" />{candidate.location}</span>
                  <span className="flex items-center gap-1.5"><Briefcase className="h-3.5 w-3.5" />{candidate.experienceYears}y experience</span>
                  <span className="flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" />Updated {relativeTime(candidate.updatedAt)}</span>
                </div>
              </div>
            </div>

            {/* External links — hidden until de-anon approval (fix3.md §1). */}
            {!effectiveAnonymized && (
              <div className="flex flex-wrap items-center gap-2 md:ml-auto md:flex-col md:items-end">
                {candidate.githubLogin && (
                  <a href={`https://github.com/${candidate.githubLogin}`} target="_blank" rel="noopener noreferrer"
                    className="flex items-center gap-1.5 rounded-lg border border-border/50 bg-muted/30 px-3 py-1.5 text-[12px] font-medium text-muted-foreground hover:text-foreground transition-colors">
                    <GitFork className="h-3.5 w-3.5" /> GitHub <ExternalLink className="h-3 w-3 opacity-50" />
                  </a>
                )}
                {candidate.linkedinUrl && (
                  <a href={candidate.linkedinUrl} target="_blank" rel="noopener noreferrer"
                    className="flex items-center gap-1.5 rounded-lg border border-border/50 bg-muted/30 px-3 py-1.5 text-[12px] font-medium text-muted-foreground hover:text-foreground transition-colors">
                    <Link2 className="h-3.5 w-3.5" /> LinkedIn <ExternalLink className="h-3 w-3 opacity-50" />
                  </a>
                )}
                {candidate.portfolioUrl && (
                  <a href={candidate.portfolioUrl} target="_blank" rel="noopener noreferrer"
                    className="flex items-center gap-1.5 rounded-lg border border-border/50 bg-muted/30 px-3 py-1.5 text-[12px] font-medium text-muted-foreground hover:text-foreground transition-colors">
                    <Globe className="h-3.5 w-3.5" /> Portfolio <ExternalLink className="h-3 w-3 opacity-50" />
                  </a>
                )}
              </div>
            )}
          </div>

          {/* Source tags — real sources from Phase 2 API, fallback to mock */}
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/60 mr-1">Sources</span>
            {candidateSources.length > 0
              ? candidateSources.map((src) => (
                  <span key={src.id} className="evidence-pill" title={src.url ?? undefined}>{src.source}</span>
                ))
              : candidate.sources.map((src) => (
                  <span key={src} className="evidence-pill">{src}</span>
                ))
            }
          </div>

          {/* Bias flags */}
          {candidateBiasFlags.length > 0 && (
            <div className="mt-3 space-y-1.5">
              {candidateBiasFlags.map((flag) => (
                <div key={flag.id} className="flex items-center gap-2 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-1.5 text-xs text-amber-400">
                  <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                  <span>{flag.rule.replace(/_/g, " ")}</span>
                  <span className="text-[10px] text-amber-500/70 ml-auto">{flag.severity}</span>
                </div>
              ))}
            </div>
          )}

          {/* Contact enrichment status */}
          {enrichmentStatus && enrichmentStatus.total > 0 && (
            <div className="mt-3 flex items-center gap-2">
              {enrichmentStatus.pending > 0 && (
                <span className="inline-flex items-center gap-1 rounded-lg border border-amber-500/20 bg-amber-500/5 px-2.5 py-1 text-[11px] font-medium text-amber-400">
                  <Clock className="h-3 w-3" />
                  {enrichmentStatus.pending} pending contact{enrichmentStatus.pending !== 1 ? "s" : ""}
                </span>
              )}
              {enrichmentStatus.approved > 0 && (
                <span className="inline-flex items-center gap-1 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-2.5 py-1 text-[11px] font-medium text-emerald-400">
                  <CheckCircle2 className="h-3 w-3" />
                  {enrichmentStatus.approved} approved contact{enrichmentStatus.approved !== 1 ? "s" : ""}
                </span>
              )}
            </div>
          )}
        </motion.div>

        {/* Main content tabs */}
        <Tabs defaultValue="skills">
          <TabsList className="bg-muted/30 border border-border/40">
            <TabsTrigger value="skills">Skills</TabsTrigger>
            <TabsTrigger value="evidence">Evidence</TabsTrigger>
            <TabsTrigger value="applications">Applications</TabsTrigger>
            <TabsTrigger value="preparation">Preparation</TabsTrigger>
          </TabsList>

          {/* Skills — Skill Radar removed (uninformative); the evidence
              panel shows every skill with a 0-100 score + per-source
              (CV / GitHub) breakdown. */}
          <TabsContent value="skills" className="mt-4 space-y-4">
            <SkillEvidencePanel candidateId={id} />
          </TabsContent>

          {/* Evidence — Phase 2: real evidence items from API */}
          <TabsContent value="evidence" className="mt-4">
            <div className="space-y-2">
              {evidenceItems.length > 0
                ? evidenceItems.map((ev) => {
                    const typeKey = ev.type as EvidenceType;
                    const Icon = evidenceIcon[typeKey] ?? BookOpen;
                    const conf = (ev.confidence ?? 0);
                    return (
                      <motion.div
                        key={ev.id}
                        initial={{ opacity: 0, x: -8 }}
                        animate={{ opacity: 1, x: 0 }}
                        className="glass rounded-xl p-4 flex items-start gap-4"
                      >
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/8 ring-1 ring-primary/15">
                          <Icon className="h-4 w-4 text-primary" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-2 flex-wrap">
                            <div className="flex items-center gap-2">
                              <span className="text-[11px] font-semibold uppercase tracking-wide text-primary/70">{ev.type}</span>
                              {ev.field_ref && (
                                <span className="evidence-pill text-[10px]">{ev.field_ref}</span>
                              )}
                            </div>
                            <div className="flex items-center gap-2">
                              {ev.confidence != null && (
                                <span className={cn("text-[11px] font-semibold", confidenceColor(conf))}>
                                  {Math.round(conf * 100)}% conf.
                                </span>
                              )}
                              <span className="text-[11px] text-muted-foreground">{shortDate(ev.created_at)}</span>
                            </div>
                          </div>
                          <p className="mt-1 text-[13px] text-foreground leading-relaxed">
                            {ev.extracted_text ?? "—"}
                          </p>
                        </div>
                      </motion.div>
                    );
                  })
                : candidate.evidenceItems.map((ev) => {
                    const Icon = evidenceIcon[ev.type] ?? BookOpen;
                    const conf = confidenceLabel(ev.confidence);
                    return (
                      <motion.div
                        key={ev.id}
                        initial={{ opacity: 0, x: -8 }}
                        animate={{ opacity: 1, x: 0 }}
                        className="glass rounded-xl p-4 flex items-start gap-4"
                      >
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/8 ring-1 ring-primary/15">
                          <Icon className="h-4 w-4 text-primary" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-2 flex-wrap">
                            <span className="text-[11px] font-semibold uppercase tracking-wide text-primary/70">{ev.source}</span>
                            <div className="flex items-center gap-2">
                              <span className={cn("text-[11px] font-semibold", confidenceColor(ev.confidence))}>
                                {Math.round(ev.confidence * 100)}% confidence
                              </span>
                              <span className="text-[11px] text-muted-foreground">{shortDate(ev.timestamp)}</span>
                            </div>
                          </div>
                          <p className="mt-1 text-[13px] text-foreground leading-relaxed">{ev.extractedText}</p>
                        </div>
                      </motion.div>
                    );
                  })
              }
              {evidenceItems.length === 0 && candidate.evidenceItems.length === 0 && (
                <div className="rounded-xl border border-dashed border-border/40 p-12 text-center">
                  <AlertCircle className="mx-auto h-8 w-8 text-muted-foreground/40 mb-2" />
                  <p className="text-sm text-muted-foreground">No evidence items yet.</p>
                  <p className="text-xs text-muted-foreground/60 mt-1">Evidence is created automatically when a CV is ingested.</p>
                </div>
              )}
            </div>
          </TabsContent>

          {/* Applications */}
          <TabsContent value="applications" className="mt-4">
            <div className="space-y-3">
              {candidateApps.map((app) => (
                <div key={app.id} className="glass rounded-xl p-5 space-y-3">
                  <div className="flex items-center justify-between gap-4 flex-wrap">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="text-sm font-semibold text-foreground">{app.job.title}</p>
                        <Badge variant="outline" className="text-[10px]">{app.job.level}</Badge>
                      </div>
                      <p className="text-[12px] text-muted-foreground mt-0.5">
                        Applied {shortDate(app.applyDate)} · via {app.sourcePlatform}
                      </p>
                    </div>
                    <div className="flex items-center gap-4 shrink-0">
                      {app.matchScore && (
                        <div className="text-right">
                          <p className={cn(
                            "font-mono text-lg font-bold",
                            app.matchScore >= 80 ? "text-emerald-400" :
                            app.matchScore >= 60 ? "text-amber-400" : "text-red-400"
                          )}>{app.matchScore}%</p>
                          <p className="text-[10px] text-muted-foreground">match score</p>
                        </div>
                      )}
                      <Link href={`/jobs/${app.jobId}/candidates`}>
                        <Button variant="ghost" size="sm" className="h-8 gap-1 text-xs">
                          View in Job <ChevronRight className="h-3 w-3" />
                        </Button>
                      </Link>
                    </div>
                  </div>
                  {/* Candidate progress against this job's configured hiring pipeline */}
                  <ApplicationPipeline roadmap={app.roadmap} />
                </div>
              ))}
              {candidateApps.length === 0 && (
                <div className="rounded-xl border border-dashed border-border/40 p-12 text-center">
                  <p className="text-sm text-muted-foreground">No applications found for this candidate.</p>
                </div>
              )}
            </div>
          </TabsContent>

          {/* fix3.md §4 / §5 — Preparation tab (replaces "AI Interview").
              AI-assisted artefacts: pre-analysis, technical questions,
              HR questions, assessment draft. */}
          <TabsContent value="preparation" className="mt-4">
            <PreparationPanel candidateId={id} jobId={topApp?.jobId} />
          </TabsContent>
        </Tabs>
      </div>

      {isHrUser && (
        <OutreachModal
          open={outreachOpen}
          onOpenChange={setOutreachOpen}
          candidate={{
            id,
            name: candidate.name ?? candidate.alias ?? null,
            email: (candidate as { email?: string | null }).email ?? null,
            title: candidate.title ?? null,
          }}
          job={
            topApp?.jobId
              ? { id: topApp.jobId, title: topApp.job?.title ?? "Open role" }
              : null
          }
        />
      )}
    </div>
  );
}

"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import {
  Briefcase, Clock, MapPin, Search, X, ArrowRight, ClipboardList, Award,
  MessageSquare, Trophy, ChevronDown, Loader2, CheckCircle2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  useCandidateApplications,
  useApplicationInterview,
  useApplicationRanking,
  useApplicationJourney,
  useApplicationFit,
} from "@/lib/hooks";
import type {
  BackendRankingRow,
  BackendRoadmap,
  BackendRoadmapStep,
  BackendJourneyStage,
} from "@/lib/api";
import { cn } from "@/lib/utils/cn";

const STATUS_LABELS: Record<string, string> = {
  applied:   "Applied",
  screening: "In Screening",
  interview: "Interview",
  offered:   "Offered",
  rejected:  "Not Selected",
  withdrawn: "Withdrawn",
};

const STATUS_COLORS: Record<string, string> = {
  applied:   "border-slate-500/30 bg-slate-500/10 text-slate-400",
  screening: "border-primary/30 bg-primary/10 text-primary",
  interview: "border-amber-500/30 bg-amber-500/10 text-amber-400",
  offered:   "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  rejected:  "border-rose-500/30 bg-rose-500/10 text-rose-400",
  withdrawn: "border-muted/30 bg-muted/10 text-muted-foreground",
};

const WORK_MODE_COLORS: Record<string, string> = {
  remote: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  hybrid: "border-amber-500/30 bg-amber-500/10 text-amber-400",
  onsite: "border-blue-500/30 bg-blue-500/10 text-blue-400",
};

const STAGE_STEPS = ["Applied", "Screening", "Interview", "Offer", "Hired"];

/**
 * Map a real backend stage code (or normalized status) to the 5-step
 * candidate pipeline. Every stage at or before the candidate's current
 * position renders blue ("reached"); the current step also gets a ring.
 */
function pipelineIndex(stage: string, status: string): number {
  const code = stage.toLowerCase().replace(/[\s-]+/g, "_");
  const byStage: Record<string, number> = {
    applied: 0, sourced: 0,
    screening: 1, assessment: 1,
    interview: 2, hr_interview: 2, tech_interview: 2,
    decision: 3, offer: 3, offered: 3,
    hired: 4,
  };
  if (code in byStage) return byStage[code];
  const byStatus: Record<string, number> = {
    applied: 0, screening: 1, interview: 2, offered: 3,
  };
  return byStatus[status] ?? 0;
}

type AppItem = {
  id: string;
  jobTitle: string;
  companyName: string;
  location: string;
  workMode: string;
  status: string;
  appliedAt: string;
  matchScore?: number;
  stage: string;
  hasAssessment: boolean;
  assessmentStatus: "not_started" | "submitted" | "none";
  assessmentScorePercent: number | null;
  roadmap?: BackendRoadmap;
};

/**
 * Use the backend-computed, per-job roadmap when present; otherwise synthesise
 * the legacy 5-step pipeline so older cached data still renders sensibly.
 */
function resolveRoadmap(app: AppItem): BackendRoadmap {
  if (app.roadmap && app.roadmap.steps?.length) return app.roadmap;

  const isTerminal = app.status === "rejected" || app.status === "withdrawn";
  const idx = pipelineIndex(app.stage, app.status);
  const kinds = ["applied", "screening", "interview", "offer", "hired"];
  const steps: BackendRoadmapStep[] = STAGE_STEPS.map((label, i) => ({
    key: kinds[i],
    kind: kinds[i],
    label,
    group: kinds[i],
    state: isTerminal ? "upcoming" : i < idx ? "done" : i === idx ? "current" : "upcoming",
    clickable: !isTerminal && i <= idx && (kinds[i] === "interview" || kinds[i] === "offer"),
  }));
  return {
    steps,
    current_index: isTerminal ? -1 : idx,
    terminal: isTerminal,
    terminal_label: isTerminal ? (app.status === "rejected" ? "Not selected" : "Withdrawn") : null,
  };
}

// Kinds that have a candidate-facing detail panel. Applied + Screening always
// have data (match / CV-fit) so they're clickable as soon as reached; the rest
// open once the candidate has reached them.
const ALWAYS_CLICKABLE_KINDS = new Set(["applied", "screening"]);
const PANEL_KINDS = new Set([
  "applied", "screening", "assessment",
  "interview", "hr_interview", "technical_interview", "mixed_interview", "offer",
]);

function stepClickable(step: BackendRoadmapStep, reached: boolean): boolean {
  if (step.clickable) return true;
  const kind = (step.kind || "").toLowerCase();
  const group = (step.group || "").toLowerCase();
  if (!PANEL_KINDS.has(kind) && group !== "interview") return false;
  if (ALWAYS_CLICKABLE_KINDS.has(kind)) return reached || step.state === "current" || step.state === "done";
  return reached;
}

// Canonical pipeline order — used to decide whether the candidate has reached
// the assessment stage yet.
function stageRank(stage: string, status: string): number {
  const code = (stage || "").toLowerCase().replace(/[\s-]+/g, "_");
  const order: Record<string, number> = {
    applied: 0, sourced: 0,
    screening: 1, screen: 1,
    assessment: 2,
    interview: 3, hr_interview: 3, tech_interview: 3, mixed_interview: 3,
    decision: 4, evaluate: 4, offer: 4, offered: 4,
    hired: 5,
  };
  if (code in order) return order[code];
  const byStatus: Record<string, number> = {
    applied: 0, screening: 1, interview: 3, offered: 4, hired: 5,
  };
  return byStatus[(status || "").toLowerCase()] ?? 0;
}

const ASSESSMENT_RANK = 2;

// Only reveal an assessment once the candidate has actually reached the
// assessment stage (or already submitted it). Prefers the real per-job roadmap
// step state; falls back to the canonical stage order when the pipeline has no
// explicit assessment step.
function reachedAssessmentStage(app: AppItem, roadmap: BackendRoadmap): boolean {
  if (app.assessmentStatus === "submitted") return true;
  const aStep = roadmap.steps?.find(
    (s) => (s.kind || "").toLowerCase() === "assessment",
  );
  if (aStep) return aStep.state === "done" || aStep.state === "current";
  return stageRank(app.stage, app.status) >= ASSESSMENT_RANK;
}

function ApplicationCard({ app }: { app: AppItem }) {
  const roadmap = resolveRoadmap(app);
  const assessmentReached = reachedAssessmentStage(app, roadmap);
  const [openKey, setOpenKey] = useState<string | null>(null);
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const openStep = roadmap.steps.find((s) => s.key === openKey) ?? null;
  const anyClickable = roadmap.steps.some(
    (s) => stepClickable(s, s.state === "done" || s.state === "current"),
  );

  // A finalised application (accepted / rejected) unlocks the full per-stage
  // result analysis so the candidate can see exactly why.
  const st = app.status.toLowerCase();
  const stg = app.stage.toLowerCase();
  const finalized =
    st === "rejected" || st === "accepted" || st === "offered" || st === "hired"
    || stg === "hired" || stg === "decision" || roadmap.terminal;
  const wasRejected = st === "rejected" || roadmap.terminal_label === "Not selected";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass gradient-border rounded-2xl p-6 space-y-5"
    >
      {/* Top row */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <h3 className="font-heading text-[15px] font-bold text-foreground">{app.jobTitle}</h3>
            <Badge variant="outline" className={cn("text-[10px]", STATUS_COLORS[app.status] ?? "")}>
              {STATUS_LABELS[app.status] ?? app.status}
            </Badge>
            <Badge variant="outline" className={cn("text-[10px]", WORK_MODE_COLORS[app.workMode] ?? "")}>
              {app.workMode}
            </Badge>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1"><Briefcase className="h-3 w-3" />{app.companyName}</span>
            <span className="flex items-center gap-1"><MapPin className="h-3 w-3" />{app.location}</span>
            <span className="flex items-center gap-1"><Clock className="h-3 w-3" />Applied {new Date(app.appliedAt).toLocaleDateString()}</span>
          </div>
        </div>
        {app.matchScore && (
          <div className="text-right shrink-0">
            <p className="text-[10px] text-muted-foreground/60 uppercase tracking-wide">Match</p>
            <p className="font-heading text-2xl font-bold text-primary">{app.matchScore}%</p>
          </div>
        )}
      </div>

      {/* Progress pipeline — the company's configured workflow for this job.
          Every stage up to and including the current one is filled blue; the
          current step gets a ring. Interview and Offer steps become clickable
          once reached, revealing a detail panel. */}
      <div className="relative">
        <div className="flex items-start gap-0">
          {roadmap.steps.map((step, i) => {
            const reached = step.state === "done" || step.state === "current";
            const isCurrent = step.state === "current";
            const isOpen = openKey === step.key;
            const clickable = stepClickable(step, reached);

            const dot = (
              <div className="flex flex-col items-center gap-1">
                <div className={cn(
                  "h-3 w-3 rounded-full border transition-all",
                  reached ? "bg-primary border-primary" : "bg-muted/30 border-border/40",
                  isCurrent && "ring-2 ring-primary/30",
                  isOpen && "ring-2 ring-primary scale-125",
                )} />
                <span className={cn(
                  "max-w-[68px] text-center text-[9px] font-medium uppercase leading-tight tracking-wide",
                  isCurrent ? "text-primary font-semibold"
                    : reached ? "text-primary/80"
                    : "text-muted-foreground/40",
                  clickable && "underline decoration-dotted underline-offset-2",
                )}>
                  {step.label}
                </span>
              </div>
            );

            return (
              <div key={step.key} className="flex flex-1 items-start">
                {clickable ? (
                  <button
                    type="button"
                    onClick={() => setOpenKey((cur) => (cur === step.key ? null : step.key))}
                    className="rounded-md transition-opacity hover:opacity-75 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
                    title={`View ${step.label.toLowerCase()} details`}
                  >
                    {dot}
                  </button>
                ) : (
                  dot
                )}
                {i < roadmap.steps.length - 1 && (
                  <div className={cn(
                    "mt-1.5 h-px flex-1",
                    !roadmap.terminal && i < roadmap.current_index ? "bg-primary" : "bg-border/40",
                  )} />
                )}
              </div>
            );
          })}
        </div>
        {roadmap.terminal ? (
          <p className="mt-2 text-center text-[10px] uppercase tracking-wide text-rose-400/80">
            {roadmap.terminal_label ?? "Closed"}
          </p>
        ) : anyClickable && (
          <p className="mt-2 text-center text-[10px] text-muted-foreground/60">
            Tap a highlighted step to see details
          </p>
        )}
      </div>

      {/* Step detail panel */}
      {openStep && openStep.group === "interview" && (
        <div className="rounded-xl border border-border/40 bg-muted/10 p-4">
          <InterviewStepPanel appId={app.id} kind={openStep.kind} title={openStep.label} />
        </div>
      )}
      {openStep && openStep.kind === "offer" && (
        <div className="rounded-xl border border-border/40 bg-muted/10 p-4">
          <OfferStepPanel appId={app.id} />
        </div>
      )}
      {openStep && openStep.kind === "applied" && (
        <div className="rounded-xl border border-border/40 bg-muted/10 p-4">
          <FitStepPanel appId={app.id} mode="match" />
        </div>
      )}
      {openStep && openStep.kind === "screening" && (
        <div className="rounded-xl border border-border/40 bg-muted/10 p-4">
          <FitStepPanel appId={app.id} mode="screening" />
        </div>
      )}
      {openStep && openStep.kind === "assessment" && (
        <div className="rounded-xl border border-border/40 bg-muted/10 p-4">
          <AssessmentStepPanel app={app} />
        </div>
      )}

      {/* Assessment — appears only once the candidate has reached the
          assessment stage (or already submitted it). Before that it stays
          hidden, even if HR has published one for the job. */}
      {app.hasAssessment && !roadmap.terminal && assessmentReached && (
        app.assessmentStatus === "submitted" ? (
          <Link
            href={`/candidate/applications/${app.id}/assessment`}
            className="flex items-center justify-between gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/5 px-4 py-3 transition-colors hover:bg-emerald-500/10"
          >
            <div className="flex items-center gap-2.5">
              <Award className="h-4 w-4 text-emerald-400" />
              <div>
                <p className="text-[13px] font-semibold text-foreground">Assessment completed</p>
                <p className="text-[11px] text-muted-foreground">
                  Score {Math.round(app.assessmentScorePercent ?? 0)}% · View your performance report
                </p>
              </div>
            </div>
            <ArrowRight className="h-4 w-4 text-emerald-400" />
          </Link>
        ) : (
          <Link
            href={`/candidate/applications/${app.id}/assessment`}
            className="flex items-center justify-between gap-3 rounded-xl border border-primary/40 bg-primary/10 px-4 py-3 transition-colors hover:bg-primary/15"
          >
            <div className="flex items-center gap-2.5">
              <ClipboardList className="h-4 w-4 text-primary" />
              <div>
                <p className="text-[13px] font-semibold text-foreground">Assessment ready to take</p>
                <p className="text-[11px] text-muted-foreground">
                  This role requires a skills assessment — complete it to move forward.
                </p>
              </div>
            </div>
            <span className="flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-[12px] font-semibold text-primary-foreground">
              Take assessment <ArrowRight className="h-3.5 w-3.5" />
            </span>
          </Link>
        )
      )}

      {/* Result analysis — unlocks once the application is finalised. */}
      {finalized && (
        <div className="overflow-hidden rounded-xl border border-border/40 bg-muted/10">
          <button
            type="button"
            onClick={() => setAnalysisOpen((v) => !v)}
            className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/20"
          >
            <span className="flex items-center gap-2 text-[13px] font-semibold text-foreground">
              <ClipboardList className="h-4 w-4 text-primary" />
              See your result analysis — why you were {wasRejected ? "not selected" : "selected"}
            </span>
            <ChevronDown
              className={cn(
                "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
                analysisOpen && "rotate-180",
              )}
            />
          </button>
          {analysisOpen && (
            <div className="border-t border-border/30 px-4 py-4">
              <ResultAnalysisPanel appId={app.id} />
            </div>
          )}
        </div>
      )}
    </motion.div>
  );
}

function PanelLoader({ text }: { text: string }) {
  return (
    <p className="flex items-center gap-2 text-[12px] text-muted-foreground">
      <Loader2 className="h-3.5 w-3.5 animate-spin" /> {text}
    </p>
  );
}

/** Applied → your match; Screening → CV fit. Both read the /fit endpoint. */
function FitStepPanel({ appId, mode }: { appId: string; mode: "match" | "screening" }) {
  const { data, isLoading } = useApplicationFit(appId, true);
  if (isLoading) return <PanelLoader text="Loading your analysis…" />;
  if (!data) return <p className="text-[12px] text-muted-foreground">No analysis available yet.</p>;
  const block = mode === "match" ? data.match : data.screening;
  const score = block.score;
  const scoreColor =
    score == null ? "text-muted-foreground"
    : score >= 70 ? "text-emerald-400"
    : score >= 45 ? "text-amber-400"
    : "text-rose-400";
  const strengths = mode === "match" ? data.match.matched_skills : data.screening.strengths;
  const gaps = mode === "match" ? data.match.missing_skills : data.screening.gaps;
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        {mode === "match"
          ? <Briefcase className="h-4 w-4 text-primary" />
          : <ClipboardList className="h-4 w-4 text-primary" />}
        <p className="text-[13px] font-semibold text-foreground">
          {mode === "match" ? "Your match to this role" : "CV screening result"}
        </p>
        {score != null && (
          <span className={cn("ml-auto font-mono text-lg font-bold", scoreColor)}>
            {Math.round(score)}<span className="text-[10px] text-muted-foreground">/100</span>
          </span>
        )}
      </div>
      <p className="text-[12px] leading-relaxed text-foreground/90">{block.explanation}</p>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {strengths.length > 0 && (
          <div className="rounded-md border border-emerald-500/15 bg-emerald-500/5 p-2">
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-emerald-300">
              {mode === "match" ? "Matched skills" : "What stood out"}
            </p>
            <div className="flex flex-wrap gap-1">
              {strengths.map((s, i) => (
                <span key={i} className="rounded-full border border-emerald-500/30 bg-emerald-500/5 px-2 py-0.5 text-[10px] text-emerald-300">{s}</span>
              ))}
            </div>
          </div>
        )}
        {gaps.length > 0 && (
          <div className="rounded-md border border-amber-500/15 bg-amber-500/5 p-2">
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-amber-300">
              Areas to strengthen
            </p>
            <div className="flex flex-wrap gap-1">
              {gaps.map((s, i) => (
                <span key={i} className="rounded-full border border-amber-500/30 bg-amber-500/5 px-2 py-0.5 text-[10px] text-amber-300">{s}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/** Assessment step → score + link to the full report. */
function AssessmentStepPanel({ app }: { app: AppItem }) {
  if (app.assessmentStatus !== "submitted") {
    return (
      <div className="space-y-2">
        <p className="text-[13px] font-semibold text-foreground">Skills assessment</p>
        <p className="text-[12px] text-muted-foreground">
          {app.hasAssessment
            ? "You haven't taken the assessment for this role yet."
            : "This role doesn't include a skills assessment."}
        </p>
        {app.hasAssessment && (
          <Link
            href={`/candidate/applications/${app.id}/assessment`}
            className="inline-flex items-center gap-1 text-[12px] text-primary hover:underline"
          >
            <ArrowRight className="h-3 w-3" /> Take the assessment
          </Link>
        )}
      </div>
    );
  }
  const pct = Math.round(app.assessmentScorePercent ?? 0);
  const color = pct >= 70 ? "text-emerald-400" : pct >= 45 ? "text-amber-400" : "text-rose-400";
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Award className="h-4 w-4 text-emerald-400" />
        <p className="text-[13px] font-semibold text-foreground">Assessment completed</p>
        <span className={cn("ml-auto font-mono text-lg font-bold", color)}>
          {pct}<span className="text-[10px] text-muted-foreground">%</span>
        </span>
      </div>
      <Link
        href={`/candidate/applications/${app.id}/assessment`}
        className="inline-flex items-center gap-1 text-[12px] text-primary hover:underline"
      >
        <ArrowRight className="h-3 w-3" /> View your full performance report
      </Link>
    </div>
  );
}

const INTERVIEW_TYPE_LABEL: Record<string, string> = {
  hr: "HR interview",
  technical: "Technical interview",
  tech: "Technical interview",
  mixed: "Interview",
  behavioral: "Behavioral interview",
};

/** Interview step → summary, key points and what stood out. */
function InterviewStepPanel({
  appId,
  kind,
  title,
}: {
  appId: string;
  kind?: string;
  title?: string;
}) {
  const { data, isLoading } = useApplicationInterview(appId, true, kind);

  if (isLoading) return <PanelLoader text="Loading interview details…" />;
  if (!data?.has_interview) {
    return (
      <div className="flex items-center gap-2 text-[12px] text-muted-foreground">
        <MessageSquare className="h-4 w-4 text-muted-foreground/60" />
        {data?.message ?? "Interview details aren’t available yet."}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <MessageSquare className="h-4 w-4 text-primary" />
        <p className="text-[13px] font-semibold text-foreground">
          {title
            ?? INTERVIEW_TYPE_LABEL[(data.interview_type ?? "").toLowerCase()]
            ?? "Interview"}
        </p>
        {data.status && (
          <Badge variant="outline" className="text-[10px] capitalize">
            {data.status.replace(/_/g, " ")}
          </Badge>
        )}
      </div>

      {data.summary ? (
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">Summary</p>
          <p className="mt-1 text-[13px] leading-relaxed text-foreground/90">{data.summary}</p>
        </div>
      ) : null}

      {(data.key_points?.length ?? 0) > 0 && (
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">Key points</p>
          <ul className="ml-4 mt-1 list-disc space-y-0.5 text-[12px] text-foreground/85">
            {data.key_points!.map((k, i) => <li key={i}>{k}</li>)}
          </ul>
        </div>
      )}

      {(data.strengths?.length ?? 0) > 0 && (
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-emerald-400/80">What stood out</p>
          <ul className="ml-4 mt-1 list-disc space-y-0.5 text-[12px] text-foreground/85">
            {data.strengths!.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </div>
      )}

      {data.analysed === false && (
        <p className="text-[11px] text-amber-300/80">
          Your interview hasn’t been fully analysed yet — more detail will appear once it’s reviewed.
        </p>
      )}
    </div>
  );
}

function ScorePill({ value }: { value: number }) {
  const color = value >= 75 ? "text-emerald-400" : value >= 50 ? "text-amber-400" : "text-rose-400";
  return <span className={cn("font-mono text-sm font-bold tabular-nums", color)}>{Math.round(value)}</span>;
}

/** One anonymized candidate row in the ranking board; expandable for detail. */
function RankRow({ row }: { row: BackendRankingRow }) {
  const [open, setOpen] = useState(row.is_you);
  return (
    <div className={cn(
      "rounded-lg border",
      row.is_you ? "border-primary/40 bg-primary/5 ring-1 ring-primary/20" : "border-border/40 bg-muted/10",
    )}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 px-3 py-2 text-left"
      >
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted/40 text-[11px] font-bold text-foreground">
          {row.rank}
        </span>
        <span className={cn(
          "flex-1 truncate text-[13px] font-medium",
          row.is_you ? "font-semibold text-primary" : "text-foreground",
        )}>
          {row.is_you ? "You" : row.label}
        </span>
        <ScorePill value={row.score} />
        <span className="text-[9px] text-muted-foreground/60">/100</span>
        <ChevronDown className={cn("h-3.5 w-3.5 text-muted-foreground transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="space-y-2 border-t border-border/30 px-3 py-2.5">
          {row.strengths.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {row.strengths.map((s, i) => (
                <span key={i} className="rounded-full border border-emerald-500/30 bg-emerald-500/5 px-2 py-0.5 text-[10px] text-emerald-300">
                  {s}
                </span>
              ))}
            </div>
          )}
          {row.explanation
            ? <p className="text-[12px] leading-relaxed text-muted-foreground">{row.explanation}</p>
            : <p className="text-[11px] italic text-muted-foreground/60">No written rationale recorded.</p>}
        </div>
      )}
    </div>
  );
}

/** Offer step → accept to reveal your anonymized ranking against other candidates. */
function OfferStepPanel({ appId }: { appId: string }) {
  const [accepted, setAccepted] = useState(false);
  const { data, isLoading } = useApplicationRanking(appId, accepted);

  if (!accepted) {
    return (
      <div className="space-y-3 text-center">
        <Trophy className="mx-auto h-8 w-8 text-emerald-400" />
        <p className="text-[14px] font-semibold text-foreground">You’ve reached the offer stage 🎉</p>
        <p className="mx-auto max-w-md text-[12px] leading-relaxed text-muted-foreground">
          Accept your offer to see how you ranked against the other candidates — anonymized,
          with each one’s score and why they stood out, plus your own placement and strengths.
        </p>
        <Button size="sm" className="gap-1.5 glow-blue" onClick={() => setAccepted(true)}>
          <CheckCircle2 className="h-3.5 w-3.5" /> Accept offer &amp; see my ranking
        </Button>
      </div>
    );
  }

  if (isLoading) return <PanelLoader text="Loading your ranking…" />;
  if (!data?.has_ranking) {
    return (
      <div className="space-y-2 text-center">
        <Trophy className="mx-auto h-7 w-7 text-emerald-400" />
        <p className="text-[13px] font-semibold text-foreground">Offer accepted 🎉</p>
        <p className="text-[12px] text-muted-foreground">{data?.message ?? "Candidate ranking isn’t available yet."}</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Trophy className="h-4 w-4 text-amber-400" />
        <p className="text-[13px] font-semibold text-foreground">
          {data.you_in_ranking && data.your_rank
            ? `You ranked #${data.your_rank} of ${data.total}`
            : `${data.total ?? data.results?.length ?? 0} candidates ranked`}
          {data.job_title ? ` · ${data.job_title}` : ""}
        </p>
      </div>
      <p className="text-[11px] leading-relaxed text-muted-foreground">
        Other candidates are anonymized — you see their scores and strengths, not their identities.
        Tap any row to read why they stood out.
      </p>
      <div className="space-y-2">
        {(data.results ?? []).map((r) => <RankRow key={`${r.rank}-${r.label}`} row={r} />)}
      </div>
    </div>
  );
}

function JourneyStageRow({ stage }: { stage: BackendJourneyStage }) {
  const score = stage.score;
  const color =
    score == null ? "text-muted-foreground"
    : score >= 75 ? "text-emerald-400"
    : score >= 50 ? "text-amber-400"
    : "text-rose-400";
  return (
    <div className="rounded-lg border border-border/40 bg-muted/10 p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[13px] font-semibold text-foreground">{stage.label}</span>
        <span className={cn("font-mono text-[13px] font-bold tabular-nums", color)}>
          {score == null ? "Not scored" : `${Math.round(score)}/100`}
        </span>
      </div>
      {stage.ai_explanation && (
        <p className="mt-1.5 text-[12px] leading-relaxed text-muted-foreground">{stage.ai_explanation}</p>
      )}
    </div>
  );
}

/** Per-stage result analysis shown to the candidate once a decision is made. */
function ResultAnalysisPanel({ appId }: { appId: string }) {
  const { data, isLoading } = useApplicationJourney(appId, true);

  if (isLoading) return <PanelLoader text="Loading your result analysis…" />;
  if (!data || !data.finalized) {
    return (
      <p className="text-[12px] text-muted-foreground">
        Your full result analysis will appear here once the hiring team records a final decision.
      </p>
    );
  }
  const accepted = data.decision === "accepted";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge
          variant="outline"
          className={cn(
            "text-[10px]",
            accepted ? "border-emerald-500/40 text-emerald-400" : "border-rose-500/40 text-rose-400",
          )}
        >
          {accepted ? "Accepted" : "Not selected"}
        </Badge>
        {data.overall.score != null && (
          <span className="text-[11px] text-muted-foreground">
            Overall journey score:{" "}
            <span className="font-semibold text-foreground">{Math.round(data.overall.score)}/100</span>
          </span>
        )}
      </div>

      {data.decision_message && (
        <div className="rounded-lg border border-primary/15 bg-primary/5 p-3">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-primary/70">
            Message from the hiring team
          </p>
          <p className="mt-1 whitespace-pre-wrap text-[13px] leading-relaxed text-foreground/90">
            {data.decision_message}
          </p>
        </div>
      )}

      <div className="space-y-2">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
          Your journey — stage by stage
        </p>
        {data.stages.length === 0 ? (
          <p className="text-[12px] text-muted-foreground">
            No stage results were recorded for this application.
          </p>
        ) : (
          data.stages.map((s) => <JourneyStageRow key={s.key} stage={s} />)
        )}
      </div>

      {data.development_plan && (
        <Link
          href="/candidate/growth-plan"
          className="flex items-center justify-between gap-3 rounded-xl border border-primary/30 bg-primary/10 px-4 py-3 transition-colors hover:bg-primary/15"
        >
          <div className="flex items-center gap-2.5">
            <Award className="h-4 w-4 text-primary" />
            <div>
              <p className="text-[13px] font-semibold text-foreground">
                Your {accepted ? "growth" : "improvement"} plan is ready
              </p>
              <p className="text-[11px] text-muted-foreground">
                {data.development_plan.summary ?? "A personalised plan to help you grow."}
              </p>
            </div>
          </div>
          <ArrowRight className="h-4 w-4 text-primary" />
        </Link>
      )}
    </div>
  );
}

export default function ApplicationsPage() {
  const [query, setQuery] = useState("");
  const { data: apps = [] } = useCandidateApplications();

  const filtered = apps.filter((a) => {
    const q = query.toLowerCase();
    return !q || a.jobTitle.toLowerCase().includes(q) || a.companyName.toLowerCase().includes(q);
  });

  return (
    <div className="min-h-screen px-6 py-8">
      <div className="mx-auto max-w-3xl">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
          <h1 className="font-heading text-3xl font-bold text-foreground">My Applications</h1>
          <p className="mt-1 text-sm text-muted-foreground">Track the status of all your job applications.</p>
        </motion.div>

        {/* Search */}
        <div className="relative mb-6">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by job title or company…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="h-11 pl-10 pr-4"
          />
          {query && (
            <button onClick={() => setQuery("")} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Summary */}
        <p className="mb-5 text-sm text-muted-foreground">{filtered.length} {filtered.length === 1 ? "application" : "applications"}</p>

        {/* List */}
        {filtered.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/40 py-16 text-center">
            <Briefcase className="mx-auto mb-3 h-10 w-10 text-muted-foreground/30" />
            <p className="text-sm font-medium text-muted-foreground">
              {query ? "No applications match your search." : "No applications yet."}
            </p>
            {!query && (
              <Button className="mt-5 gap-2 glow-blue" size="sm" asChild>
                <Link href="/candidate/discover">Browse Jobs <ArrowRight className="h-3.5 w-3.5" /></Link>
              </Button>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {filtered.map((app) => <ApplicationCard key={app.id} app={app} />)}
          </div>
        )}

        {/* CTA */}
        <div className="mt-10 glass gradient-border rounded-2xl p-6 text-center">
          <p className="text-sm font-semibold text-foreground">Looking for more opportunities?</p>
          <p className="mt-1 text-xs text-muted-foreground">Browse open positions and apply with your existing profile.</p>
          <Button className="mt-4 gap-2 glow-blue" size="sm" asChild>
            <Link href="/candidate/discover">Browse Jobs <ArrowRight className="h-3.5 w-3.5" /></Link>
          </Button>
        </div>
      </div>
    </div>
  );
}

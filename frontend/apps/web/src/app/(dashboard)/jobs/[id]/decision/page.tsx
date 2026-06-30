"use client";

/**
 * Decision tab for a single job.
 *
 * A ranked leaderboard of the candidates who have reached the decision phase,
 * sorted by their FINAL score (highest first). Each row links straight to that
 * candidate's full Decision Support page (score, rubric, per-stage breakdown,
 * hiring-manager decision, email + development plan).
 *
 * "Final score" = the IDSS decision-packet journey score when a packet exists,
 * else the interview result, else the screening/match score — so every row
 * shows the best available signal.
 */

import { use } from "react";
import Link from "next/link";
import { AlertCircle, ChevronRight, RefreshCw, Scale } from "lucide-react";
import { motion } from "framer-motion";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { useJobCandidates, useJobDetail } from "@/lib/hooks";
import { JobHeader } from "@/components/features/job-detail/JobHeader";
import { JobTabBar } from "@/components/features/job-detail/JobTabBar";
import { JobStatsStrip } from "@/components/features/job-detail/JobStatsStrip";
import { initials } from "@/lib/utils/format";
import type { CandidateInPipeline, KanbanStage } from "@/types";
import { KANBAN_STAGE_LABELS } from "@/types";

interface Props {
  params: Promise<{ id: string }>;
}

// Stages whose candidates belong on the decision leaderboard.
const DECIDE_STAGES: KanbanStage[] = ["interview", "evaluate", "decide", "decision"] as KanbanStage[];

/** Best available "final score" for ranking + display. */
function finalScoreOf(c: CandidateInPipeline): number | null {
  return c.decisionScore ?? c.interviewScore ?? c.overallScore ?? c.matchScore ?? null;
}

function scoreSource(c: CandidateInPipeline): string {
  if (c.decisionScore != null) return "Decision score";
  if (c.interviewScore != null) return "Interview score";
  if (c.overallScore != null) return "Screening score";
  if (c.matchScore != null) return "Match score";
  return "Pending";
}

function ScoreBadge({ score }: { score: number | null }) {
  if (score == null) {
    return (
      <span className="inline-flex items-center rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-[11px] font-medium text-amber-400">
        Score pending
      </span>
    );
  }
  const pct = score > 1 ? Math.round(score) : Math.round(score * 100);
  const tone =
    pct >= 75 ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/10"
    : pct >= 50 ? "text-amber-400 border-amber-500/30 bg-amber-500/10"
    : "text-red-400 border-red-500/30 bg-red-500/10";
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full border px-3 py-1 text-sm font-bold tabular-nums", tone)}>
      {pct}<span className="text-[9px] font-normal opacity-70">/ 100</span>
    </span>
  );
}

export default function DecisionPage({ params }: Props) {
  const { id } = use(params);
  const qc = useQueryClient();

  const { data: job, isLoading: jobLoading, isError: jobError, refetch: refetchJob } = useJobDetail(id);
  const {
    data: candidatePage,
    isLoading: candLoading,
    isError: candError,
    refetch: refetchCandidates,
  } = useJobCandidates(id, {});

  const isLoading = jobLoading || candLoading;
  const isError = jobError || candError;

  // Decision-relevant candidates: those in a decision stage OR anyone who
  // already has an interview / decision score (so decided candidates still show).
  const candidates = (candidatePage?.items ?? [])
    .filter(
      (c) =>
        DECIDE_STAGES.includes(c.pipelineStage as KanbanStage) ||
        c.interviewScore != null ||
        c.decisionScore != null,
    )
    .slice()
    .sort((a, b) => {
      const sa = finalScoreOf(a);
      const sb = finalScoreOf(b);
      if (sa == null && sb == null) return 0;
      if (sa == null) return 1; // nulls last
      if (sb == null) return -1;
      return sb - sa; // highest first
    });

  function refresh() {
    qc.invalidateQueries({ queryKey: ["jobCandidates"] });
    refetchCandidates();
  }

  if (isLoading) {
    return (
      <div className="flex flex-col gap-5 p-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-48 w-full rounded-xl" />
      </div>
    );
  }

  if (isError || !job) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
        <AlertCircle className="h-10 w-10 text-destructive" />
        <p className="font-semibold">Failed to load decision data</p>
        <Button variant="outline" size="sm" onClick={() => { refetchJob(); refetchCandidates(); }} className="gap-2">
          <RefreshCw className="h-3.5 w-3.5" /> Try again
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5 p-6">
      <JobHeader job={job} />
      <JobTabBar jobId={id} />
      <JobStatsStrip stats={job.stats} />

      <div className="flex items-center gap-2 flex-wrap">
        <Scale className="h-5 w-5 text-primary" />
        <h2 className="text-base font-semibold">Decision Support</h2>
        <span className="text-xs text-muted-foreground">· Candidates ranked by final score</span>
        <div className="ml-auto">
          <Button size="sm" variant="ghost" className="h-7 gap-1.5 text-xs" onClick={refresh}>
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </Button>
        </div>
      </div>

      {candidates.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
          <Scale className="h-12 w-12 text-muted-foreground/40" />
          <div>
            <p className="font-semibold">No candidates ready for a final decision</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Advance candidates from the Screening tab into Interview or Evaluate to rank them here.
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          {candidates.map((c, i) => (
            <motion.div
              key={c.applicationId}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.02 }}
            >
              <Link
                href={`/candidates/${c.id}/decision`}
                className="group flex items-center gap-4 rounded-xl border border-border/40 bg-card px-4 py-3 transition-all hover:border-primary/30 hover:bg-muted/30"
                title="Open the full decision support page"
              >
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[12px] font-bold text-primary">
                  {i + 1}
                </span>
                <Avatar className="h-10 w-10 shrink-0">
                  <AvatarFallback className="bg-primary/10 text-primary text-xs font-semibold">
                    {initials(c.name ?? "?")}
                  </AvatarFallback>
                </Avatar>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold text-foreground">{c.name}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {KANBAN_STAGE_LABELS[c.pipelineStage as KanbanStage] ?? c.pipelineStage}
                    {" · "}
                    {scoreSource(c)}
                  </p>
                </div>
                <ScoreBadge score={finalScoreOf(c)} />
                <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
              </Link>
            </motion.div>
          ))}
        </div>
      )}

      <div className="rounded-lg border border-border/30 bg-muted/10 px-3 py-2">
        <p className="text-[11px] text-muted-foreground">
          <Scale className="mr-1 inline h-3 w-3" />
          Ranked by each candidate&apos;s final score. Click a candidate to open the full decision
          support page — rubric, per-stage breakdown, hiring decision, email &amp; development plan.
        </p>
      </div>
    </div>
  );
}

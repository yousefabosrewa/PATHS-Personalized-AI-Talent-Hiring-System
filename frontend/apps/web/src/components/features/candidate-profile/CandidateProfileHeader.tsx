"use client";

import { MapPin, Briefcase, Clock, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { CandidateDetail, KanbanStage } from "@/types";
import { KANBAN_STAGE_LABELS } from "@/types";

interface Props {
  candidate: CandidateDetail;
  jobId: string;
}

const STAGE_COLORS: Record<KanbanStage, string> = {
  define:    "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  source:    "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  screen:    "bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400",
  shortlist: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400",
  reveal:    "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400",
  outreach:  "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
  interview: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  evaluate:  "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
  decide:    "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
};

function ScoreBadge({ score }: { score: number | null }) {
  if (score == null) return null;
  const color =
    score >= 75 ? "bg-green-500"
    : score >= 50 ? "bg-amber-500"
    : "bg-red-500";
  return (
    <div className={`flex h-12 w-12 items-center justify-center rounded-full text-white font-bold text-sm ${color}`}>
      {score.toFixed(0)}
    </div>
  );
}

export function CandidateProfileHeader({ candidate, jobId }: Props) {
  const initials = candidate.name
    .split(" ")
    .map((n) => n[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <div className="space-y-4">
      <Link
        href={`/jobs/${jobId}/candidates`}
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to candidates
      </Link>

      <div className="flex items-start gap-4">
        {/* Avatar */}
        <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-semibold text-lg">
          {initials}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0 space-y-1">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-xl font-bold truncate">{candidate.name}</h1>
            {candidate.pipelineStage && (
              <Badge
                variant="secondary"
                className={STAGE_COLORS[candidate.pipelineStage]}
              >
                {KANBAN_STAGE_LABELS[candidate.pipelineStage]}
              </Badge>
            )}
          </div>

          {candidate.headline && (
            <p className="text-sm text-muted-foreground truncate">{candidate.headline}</p>
          )}

          <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
            {candidate.location && (
              <span className="flex items-center gap-1">
                <MapPin className="h-3.5 w-3.5" />
                {candidate.location}
              </span>
            )}
            {candidate.currentRole && (
              <span className="flex items-center gap-1">
                <Briefcase className="h-3.5 w-3.5" />
                {candidate.currentRole}
              </span>
            )}
            {candidate.yearsExperience != null && (
              <span className="flex items-center gap-1">
                <Clock className="h-3.5 w-3.5" />
                {candidate.yearsExperience} yr{candidate.yearsExperience !== 1 ? "s" : ""} exp
              </span>
            )}
          </div>
        </div>

        {/* Score */}
        <ScoreBadge score={candidate.overallScore} />
      </div>

      {/* Masked contact */}
      {(candidate.emailMasked || candidate.phoneMasked) && (
        <div className="flex gap-4 text-xs text-muted-foreground border-t border-border pt-3">
          {candidate.emailMasked && <span>{candidate.emailMasked}</span>}
          {candidate.phoneMasked && <span>{candidate.phoneMasked}</span>}
        </div>
      )}
    </div>
  );
}

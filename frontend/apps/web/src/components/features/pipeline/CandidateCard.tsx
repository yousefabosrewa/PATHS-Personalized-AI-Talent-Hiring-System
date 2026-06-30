"use client";

import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import type { CandidateInPipeline } from "@/types";

interface Props {
  candidate: CandidateInPipeline;
  jobId: string;
}

function ScoreChip({
  score,
  label,
  title,
}: {
  score: number | null;
  label?: string;
  title?: string;
}) {
  if (score == null) return null;
  const color =
    score >= 75 ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
    : score >= 50 ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
    : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400";
  return (
    <span
      title={title}
      className={cn(
        "rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums",
        color,
      )}
    >
      {label ? <span className="mr-0.5 opacity-70">{label}</span> : null}
      {score.toFixed(0)}
    </span>
  );
}

export function CandidateCard({ candidate, jobId }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: candidate.applicationId });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="group flex items-start gap-2 rounded-lg border border-border bg-card px-3 py-2.5 shadow-sm hover:shadow-md transition-shadow"
    >
      <button
        {...attributes}
        {...listeners}
        aria-roledescription="draggable"
        aria-label={`Drag ${candidate.name}`}
        className="mt-0.5 cursor-grab text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity focus:opacity-100"
      >
        <GripVertical className="h-4 w-4" />
      </button>

      <Link
        href={`/jobs/${jobId}/candidates/${candidate.id}`}
        className="flex-1 min-w-0 hover:underline"
      >
        <p className="truncate text-sm font-medium">{candidate.name}</p>
        {candidate.headline && (
          <p className="truncate text-xs text-muted-foreground">{candidate.headline}</p>
        )}
      </Link>

      <div className="flex flex-col items-end gap-1 shrink-0">
        {/* Interview result (post-interview) — shown distinctly when present. */}
        <ScoreChip score={candidate.interviewScore} label="IV" title="Interview score" />
        {/* Fit score: screening score if available, else the live match %. */}
        <ScoreChip
          score={candidate.overallScore ?? candidate.matchScore}
          title={candidate.overallScore != null ? "Screening score" : "Match score"}
        />
        {candidate.sourceChannel && (
          <span className="text-[10px] text-muted-foreground">{candidate.sourceChannel}</span>
        )}
      </div>
    </div>
  );
}

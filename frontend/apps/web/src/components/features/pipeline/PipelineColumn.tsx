"use client";

import { useDroppable } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { cn } from "@/lib/utils";
import { CandidateCard } from "./CandidateCard";
import type { CandidateInPipeline, KanbanStage } from "@/types";

interface Props {
  stageKey: KanbanStage;
  label: string;
  count: number;
  candidates: CandidateInPipeline[];
  jobId: string;
  /** Optional drag handle (grip) for reordering the column itself. */
  dragHandle?: React.ReactNode;
}

const STAGE_COLORS: Record<KanbanStage, string> = {
  define:    "border-t-gray-400",
  source:    "border-t-blue-400",
  screen:    "border-t-sky-400",
  shortlist: "border-t-indigo-500",
  reveal:    "border-t-violet-500",
  outreach:  "border-t-purple-500",
  interview: "border-t-amber-500",
  evaluate:  "border-t-orange-500",
  decide:    "border-t-green-500",
};

export function PipelineColumn({ stageKey, label, count, candidates, jobId, dragHandle }: Props) {
  const { setNodeRef, isOver } = useDroppable({ id: stageKey });

  return (
    <div
      className={cn(
        "flex h-full min-w-[220px] flex-col rounded-xl border-t-4 border border-border bg-muted/40 shadow-sm",
        STAGE_COLORS[stageKey],
        isOver && "ring-2 ring-primary/40",
      )}
    >
      {/* Column header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border">
        <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider">
          {dragHandle}
          {label}
        </span>
        <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-bold tabular-nums">
          {count}
        </span>
      </div>

      {/* Cards */}
      <div
        ref={setNodeRef}
        className="flex-1 overflow-y-auto p-2 space-y-2 min-h-[120px]"
      >
        <SortableContext
          items={candidates.map((c) => c.applicationId)}
          strategy={verticalListSortingStrategy}
        >
          {candidates.map((c) => (
            <CandidateCard key={c.applicationId} candidate={c} jobId={jobId} />
          ))}
        </SortableContext>

        {candidates.length === 0 && (
          <div className="flex items-center justify-center py-8 text-xs text-muted-foreground">
            Drop candidates here
          </div>
        )}
      </div>
    </div>
  );
}

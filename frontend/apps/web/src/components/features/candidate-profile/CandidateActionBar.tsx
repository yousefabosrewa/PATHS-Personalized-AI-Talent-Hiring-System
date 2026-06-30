"use client";

import { useState } from "react";
import { ChevronDown, MoveRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { toast } from "sonner";
import { useMoveApplicationStage } from "@/lib/hooks";
import { KANBAN_STAGES, KANBAN_STAGE_LABELS } from "@/types";
import type { KanbanStage, CandidateDetail } from "@/types";

interface Props {
  candidate: CandidateDetail;
  applicationId: string;
  jobId: string;
}

export function CandidateActionBar({ candidate, applicationId, jobId }: Props) {
  const { mutateAsync: moveStage, isPending } = useMoveApplicationStage(jobId);
  const [moving, setMoving] = useState(false);

  async function handleMove(stage: KanbanStage) {
    if (stage === candidate.pipelineStage) return;
    setMoving(true);
    try {
      await moveStage({ appId: applicationId, stage });
      toast.success(`Moved to ${KANBAN_STAGE_LABELS[stage]}`);
    } catch {
      toast.error("Failed to move candidate.");
    } finally {
      setMoving(false);
    }
  }

  const currentIdx = candidate.pipelineStage
    ? KANBAN_STAGES.indexOf(candidate.pipelineStage)
    : -1;
  const nextStage = currentIdx < KANBAN_STAGES.length - 1 ? KANBAN_STAGES[currentIdx + 1] : null;

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {nextStage && (
        <Button
          size="sm"
          className="gap-1.5"
          disabled={moving || isPending}
          onClick={() => handleMove(nextStage)}
        >
          <MoveRight className="h-3.5 w-3.5" />
          Move to {KANBAN_STAGE_LABELS[nextStage]}
        </Button>
      )}

      <DropdownMenu>
        <DropdownMenuTrigger
          disabled={moving || isPending}
          className="inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium shadow-sm hover:bg-accent hover:text-accent-foreground disabled:pointer-events-none disabled:opacity-50"
        >
          Move to stage
          <ChevronDown className="h-3.5 w-3.5" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          <DropdownMenuLabel>Pipeline stage</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {KANBAN_STAGES.map((stage) => (
            <DropdownMenuItem
              key={stage}
              disabled={stage === candidate.pipelineStage}
              onSelect={() => handleMove(stage)}
            >
              {KANBAN_STAGE_LABELS[stage]}
              {stage === candidate.pipelineStage && (
                <span className="ml-auto text-xs text-muted-foreground">current</span>
              )}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

"use client";

/**
 * AgentProgressIndicator
 *
 * Shows a 5-step pipeline progress bar for any long-running agent run.
 * Polls GET /api/v1/agent-runs/{runId} every 2 seconds while the run is
 * queued or running, then freezes when completed/failed.
 *
 * Usage:
 *   <AgentProgressIndicator runId={runId} nodes={INTERVIEW_NODES} />
 */

import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAgentRun } from "@/lib/hooks";

export interface NodeDef {
  key: string;   // matches current_node values from backend
  label: string; // human-readable label
}

// ── Pre-built node lists for known agents ────────────────────────────────────

export const INTERVIEW_EVAL_NODES: NodeDef[] = [
  { key: "transcript_capture",   label: "Capture Transcript" },
  { key: "summarize_transcript", label: "Summarise" },
  { key: "hr_evaluation",        label: "HR Evaluation" },
  { key: "technical_evaluation", label: "Technical Evaluation" },
  { key: "decision_support",     label: "Decision Packet" },
];

export const SCREENING_NODES: NodeDef[] = [
  { key: "fetch_candidates",  label: "Fetch Candidates" },
  { key: "score_candidates",  label: "Score" },
  { key: "rank_and_persist",  label: "Rank & Persist" },
  { key: "bias_guardrail",    label: "Bias Guardrail" },
];

export const SOURCING_NODES: NodeDef[] = [
  { key: "search_query",  label: "Search Sources" },
  { key: "filter",        label: "Filter" },
  { key: "deduplicate",   label: "Deduplicate" },
  { key: "enrich",        label: "Enrich" },
  { key: "persist",       label: "Persist" },
];

// ── Component ────────────────────────────────────────────────────────────────

interface Props {
  runId: string;
  nodes?: NodeDef[];
  className?: string;
}

export function AgentProgressIndicator({
  runId,
  nodes = INTERVIEW_EVAL_NODES,
  className,
}: Props) {
  const { data: run, isLoading } = useAgentRun(runId);

  if (isLoading) {
    return (
      <div className={cn("flex items-center gap-2 text-xs text-muted-foreground", className)}>
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Loading run status…
      </div>
    );
  }

  if (!run) {
    return (
      <p className={cn("text-xs text-muted-foreground", className)}>
        Run not found.
      </p>
    );
  }

  const isFailed    = run.status === "failed";
  const isCompleted = run.status === "completed";
  const isActive    = run.status === "queued" || run.status === "running";

  // Determine progress: index of current_node in the nodes array.
  const currentIdx = run.current_node
    ? nodes.findIndex((n) => n.key === run.current_node)
    : -1;

  const completedUpTo = isCompleted ? nodes.length - 1
    : isFailed        ? currentIdx - 1
    : currentIdx - 1;

  return (
    <div className={cn("space-y-3", className)}>
      {/* Status line */}
      <div className="flex items-center gap-2 text-sm">
        {isCompleted ? (
          <>
            <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
            <span className="font-semibold text-green-600 dark:text-green-400">
              Analysis complete
            </span>
          </>
        ) : isFailed ? (
          <>
            <XCircle className="h-4 w-4 text-red-500 shrink-0" />
            <span className="font-semibold text-red-600 dark:text-red-400">
              Run failed
            </span>
            {run.error && (
              <span className="text-xs text-muted-foreground truncate">{run.error}</span>
            )}
          </>
        ) : (
          <>
            <Loader2 className="h-4 w-4 text-primary animate-spin shrink-0" />
            <span className="font-medium">
              {run.status === "queued" ? "Queued…" : "Running…"}
            </span>
          </>
        )}
      </div>

      {/* Node pipeline */}
      <div className="flex items-start gap-1.5">
        {nodes.map((node, i) => {
          const isDone    = i <= completedUpTo;
          const isCurrent = i === currentIdx && isActive;
          const isFail    = isFailed && i === currentIdx;

          return (
            <div key={node.key} className="flex-1 flex flex-col items-center gap-1">
              {/* Circle */}
              <div
                className={cn(
                  "flex h-6 w-6 items-center justify-center rounded-full border-2 text-[10px] font-bold transition-all",
                  isDone && !isFail
                    ? "border-green-500 bg-green-500 text-white"
                    : isCurrent
                    ? "border-primary bg-primary/10 text-primary"
                    : isFail
                    ? "border-red-500 bg-red-50 dark:bg-red-950/20 text-red-500"
                    : "border-muted-foreground/30 bg-muted/20 text-muted-foreground/50",
                )}
              >
                {isDone && !isFail ? (
                  <CheckCircle2 className="h-3.5 w-3.5" />
                ) : isCurrent ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : isFail ? (
                  <XCircle className="h-3.5 w-3.5" />
                ) : (
                  i + 1
                )}
              </div>

              {/* Connector line (not after last) */}
              {i < nodes.length - 1 && (
                <div className="absolute" />
              )}

              {/* Label */}
              <span
                className={cn(
                  "text-center text-[9px] leading-tight",
                  isDone && !isFail
                    ? "text-green-600 dark:text-green-400 font-medium"
                    : isCurrent
                    ? "text-primary font-semibold"
                    : "text-muted-foreground/60",
                )}
              >
                {node.label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Connector track between circles */}
      <div className="relative -mt-9 mb-3 flex items-center px-3">
        {nodes.slice(0, -1).map((_, i) => (
          <div
            key={i}
            className={cn(
              "flex-1 h-0.5 rounded-full mx-1",
              i < completedUpTo
                ? "bg-green-500"
                : i === currentIdx - 1 && isActive
                ? "bg-primary/40"
                : "bg-muted/30",
            )}
          />
        ))}
      </div>
    </div>
  );
}

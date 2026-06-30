"use client";

/**
 * AgentRunsListener
 *
 * Mounts in the dashboard layout and polls GET /api/v1/agent-runs every 5
 * seconds.  Emits a toast notification whenever an agent run transitions to
 * "completed" or "failed" — giving the recruiter live feedback without having
 * to navigate to the specific page that triggered the run.
 *
 * Tracks which run IDs have already been notified in a local Set to avoid
 * duplicate toasts across re-renders.
 */

import { useEffect, useRef } from "react";
import { toast } from "sonner";
import { CheckCircle2, XCircle } from "lucide-react";
import { useOrgAgentRuns } from "@/lib/hooks";

const RUN_TYPE_LABELS: Record<string, string> = {
  screening:        "Screening",
  interview_eval:   "Interview Evaluation",
  sourcing:         "Candidate Sourcing",
  outreach:         "Outreach",
  decision_support: "Decision Support",
  cv_ingestion:     "CV Ingestion",
};

function getLabel(runType: string): string {
  return RUN_TYPE_LABELS[runType] ?? runType;
}

interface Props {
  orgId: string;
}

export function AgentRunsListener({ orgId }: Props) {
  // Ref to track which run IDs we've already notified
  const notifiedRef = useRef<Set<string>>(new Set());

  const { data: runs } = useOrgAgentRuns(orgId, { limit: 30 });

  useEffect(() => {
    if (!runs) return;

    for (const run of runs) {
      if (notifiedRef.current.has(run.run_id)) continue;
      if (run.status !== "completed" && run.status !== "failed") continue;

      // Mark as notified before showing toast (prevents duplicates on re-render)
      notifiedRef.current.add(run.run_id);

      const label = getLabel(run.run_type);

      if (run.status === "completed") {
        toast.success(`${label} completed`, {
          description: run.entity_id
            ? `Entity: ${run.entity_id.slice(0, 8)}…`
            : "The agent run finished successfully.",
          icon: <CheckCircle2 className="h-4 w-4 text-green-500" />,
          duration: 5_000,
        });
      } else {
        toast.error(`${label} failed`, {
          description: run.error ?? "An error occurred during the agent run.",
          icon: <XCircle className="h-4 w-4 text-red-500" />,
          duration: 8_000,
        });
      }
    }
  }, [runs]);

  // This component renders nothing — it's a side-effect only listener.
  return null;
}

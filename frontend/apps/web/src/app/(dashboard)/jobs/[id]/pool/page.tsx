"use client";

import { use, useState } from "react";
import {
  AlertCircle,
  BarChart2,
  CheckCircle2,
  Clock,
  Loader2,
  Play,
  RefreshCw,
  Search,
  Settings2,
  Users,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import {
  useJobDetail,
  usePoolRuns,
  useBuildCandidatePool,
  useAgentRun,
} from "@/lib/hooks";
import { useAuthStore } from "@/lib/stores/auth.store";
import { JobHeader } from "@/components/features/job-detail/JobHeader";
import { JobTabBar } from "@/components/features/job-detail/JobTabBar";
import { JobStatsStrip } from "@/components/features/job-detail/JobStatsStrip";
import {
  AgentProgressIndicator,
  SOURCING_NODES,
} from "@/components/features/interviews/AgentProgressIndicator";
import type { BackendPoolRun } from "@/lib/api";

interface Props {
  params: Promise<{ id: string }>;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function PoolRunRow({ run }: { run: BackendPoolRun }) {
  const statusStyles: Record<string, string> = {
    completed: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    running:   "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
    failed:    "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  };

  return (
    <div className="flex items-center gap-4 px-4 py-3 rounded-lg border border-border bg-card hover:bg-muted/30 transition-colors">
      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
        <Users className="h-4 w-4 text-primary" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">
          {run.candidates_found} candidates found
        </p>
        <p className="text-xs text-muted-foreground">
          Run {run.pool_run_id.slice(0, 8)}… ·{" "}
          {new Date(run.created_at).toLocaleString()}
        </p>
      </div>
      <span
        className={cn(
          "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize",
          statusStyles[run.status] ?? statusStyles.completed,
        )}
      >
        {run.status}
      </span>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PoolPage({ params }: Props) {
  const { id } = use(params);

  // Source the org from the auth store (the legacy `paths_org` localStorage key
  // was never written, so reading it left orgId empty — the pool-runs query
  // stayed disabled and "Build Pool" always errored "Organisation not found").
  const { user } = useAuthStore();
  const orgId = user?.orgId ?? "";

  const { data: job, isLoading: jobLoading } = useJobDetail(id);
  const {
    data: poolRuns = [],
    isLoading: runsLoading,
    refetch: refetchRuns,
  } = usePoolRuns(id, orgId);

  const { mutateAsync: buildPool, isPending: building } = useBuildCandidatePool(id);

  // Config state
  const [topK, setTopK] = useState(20);
  const [minScore, setMinScore] = useState(0.6);
  const [locationFilter, setLocationFilter] = useState("");
  const [latestRunId, setLatestRunId] = useState<string | null>(null);

  const { data: activeRun } = useAgentRun(latestRunId);
  const isRunning =
    activeRun?.status === "queued" || activeRun?.status === "running";

  async function handleBuild() {
    if (!orgId) {
      toast.error("Organisation not found — please log in again.");
      return;
    }
    try {
      const result = await buildPool({
        organization_id: orgId,
        top_k: topK,
        min_score: minScore,
        provider: "mock",
        location_filter: locationFilter || null,
      });
      setLatestRunId(result.agent_run_id);
      toast.success("Sourcing agent started — watch progress below.");
    } catch {
      toast.error("Failed to start sourcing run");
    }
  }

  if (jobLoading) {
    return (
      <div className="flex flex-col gap-5 p-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-48 w-full rounded-xl" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5 p-6">
      {job && (
        <>
          <JobHeader job={job} />
          <JobTabBar jobId={id} />
          <JobStatsStrip stats={job.stats} />
        </>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* ── Config panel ──────────────────────────────────────────────── */}
        <div className="lg:col-span-1 rounded-xl border border-border bg-card p-5 space-y-5">
          <div className="flex items-center gap-2">
            <Settings2 className="h-4 w-4 text-primary" />
            <h3 className="text-sm font-semibold">Pool Configuration</h3>
          </div>

          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>Top-K candidates</Label>
              <Input
                type="number"
                min={5}
                max={200}
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                className="text-sm"
              />
              <p className="text-xs text-muted-foreground">
                Maximum candidates to source per run.
              </p>
            </div>

            <div className="space-y-1.5">
              <Label>Min. match score ({Math.round(minScore * 100)}%)</Label>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={minScore}
                onChange={(e) => setMinScore(Number(e.target.value))}
                className="w-full accent-primary"
              />
            </div>

            <div className="space-y-1.5">
              <Label>Location filter</Label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                <Input
                  className="pl-8 text-sm"
                  placeholder="e.g. London, Remote…"
                  value={locationFilter}
                  onChange={(e) => setLocationFilter(e.target.value)}
                />
              </div>
            </div>

            <Separator />

            <Button
              className="w-full gap-2"
              onClick={handleBuild}
              disabled={building || isRunning || !orgId}
            >
              {building || isRunning ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              {building ? "Starting…" : isRunning ? "Running…" : "Build Pool"}
            </Button>
          </div>
        </div>

        {/* ── Right column: progress + history ──────────────────────────── */}
        <div className="lg:col-span-2 space-y-4">
          {/* Progress indicator */}
          {latestRunId && (
            <div className="rounded-xl border border-border bg-card p-5 space-y-3">
              <div className="flex items-center gap-2">
                <BarChart2 className="h-4 w-4 text-primary" />
                <h3 className="text-sm font-semibold">Sourcing Progress</h3>
              </div>
              <AgentProgressIndicator
                runId={latestRunId}
                nodes={SOURCING_NODES}
              />
              {activeRun?.status === "completed" && (
                <div className="flex items-center gap-2 text-sm text-green-600 dark:text-green-400">
                  <CheckCircle2 className="h-4 w-4" />
                  {(activeRun.result_ref as Record<string, unknown>)?.persisted_count
                    ? `${(activeRun.result_ref as Record<string, unknown>).persisted_count} new candidates added to pool.`
                    : "Pool build complete."}
                </div>
              )}
            </div>
          )}

          {/* Run history */}
          <div className="rounded-xl border border-border bg-card p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-primary" />
                <h3 className="text-sm font-semibold">Run History</h3>
              </div>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 gap-1 text-xs"
                onClick={() => refetchRuns()}
                disabled={runsLoading}
              >
                <RefreshCw className={cn("h-3.5 w-3.5", runsLoading && "animate-spin")} />
                Refresh
              </Button>
            </div>

            {runsLoading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-14 w-full rounded-lg" />
                ))}
              </div>
            ) : poolRuns.length === 0 ? (
              <div className="flex flex-col items-center gap-3 py-12 text-center">
                <Users className="h-10 w-10 text-muted-foreground/30" />
                <p className="text-sm text-muted-foreground">
                  No sourcing runs yet. Configure and click &quot;Build Pool&quot;.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {poolRuns.map((run) => (
                  <PoolRunRow key={run.pool_run_id} run={run} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

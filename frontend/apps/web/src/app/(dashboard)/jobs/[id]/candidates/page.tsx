"use client";

import { use, useState } from "react";
import { AlertCircle, RefreshCw, Users, Search } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useJobDetail, useJobCandidates } from "@/lib/hooks";
import { JobHeader } from "@/components/features/job-detail/JobHeader";
import { JobTabBar } from "@/components/features/job-detail/JobTabBar";
import { JobStatsStrip } from "@/components/features/job-detail/JobStatsStrip";
import { KANBAN_STAGES, KANBAN_STAGE_LABELS } from "@/types";
import type { KanbanStage } from "@/types";
import { cn } from "@/lib/utils";

interface Props {
  params: Promise<{ id: string }>;
}

/** Candidate↔job fit % — the same matching score the candidate sees. */
function MatchChip({ score, skills }: { score: number | null; skills: string[] }) {
  if (score == null) return <span className="text-xs text-muted-foreground">—</span>;
  const color =
    score >= 75 ? "text-emerald-600 dark:text-emerald-400"
    : score >= 60 ? "text-primary"
    : "text-amber-600 dark:text-amber-400";
  return (
    <span
      className={cn("text-sm font-bold tabular-nums", color)}
      title={skills.length ? `Matches: ${skills.join(", ")}` : undefined}
    >
      {score}%
    </span>
  );
}

export default function CandidatesListPage({ params }: Props) {
  const { id } = use(params);
  const [search, setSearch] = useState("");
  const [stage, setStage] = useState<string>("all");

  const { data: job, isLoading: jobLoading, isError: jobError, error: jobErr, refetch: refetchJob } = useJobDetail(id);
  const {
    data: candidatePage,
    isLoading: candLoading,
    isError: candError,
    refetch: refetchCandidates,
  } = useJobCandidates(id, {
    q: search || undefined,
    stage: (stage !== "all" ? stage : undefined) as KanbanStage | undefined,
  });

  const isLoading = jobLoading || candLoading;
  const isError = jobError || candError;

  // ── Loading ─────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="flex flex-col gap-5 p-6">
        <div className="flex flex-col gap-2">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-4 w-48" />
        </div>
        <Skeleton className="h-10 w-full" />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20 rounded-xl" />
          ))}
        </div>
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  // ── Error ────────────────────────────────────────────────────────────
  if (isError || !job) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
        <AlertCircle className="h-10 w-10 text-destructive" />
        <div>
          <p className="font-semibold">Failed to load candidates</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {jobErr instanceof Error ? jobErr.message : "An unexpected error occurred."}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => { refetchJob(); refetchCandidates(); }}
          className="gap-2"
        >
          <RefreshCw className="h-3.5 w-3.5" /> Try again
        </Button>
      </div>
    );
  }

  const candidates = candidatePage?.items ?? [];

  return (
    <div className="flex flex-col gap-5 p-6">
      <JobHeader job={job} />
      <JobTabBar jobId={id} />
      <JobStatsStrip stats={job.stats} />

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder="Search by name…"
            className="pl-9 h-8 text-sm"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select value={stage} onValueChange={(v) => setStage(v ?? "all")}>
          <SelectTrigger className="h-8 w-[160px] text-sm">
            <SelectValue placeholder="All stages" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All stages</SelectItem>
            {KANBAN_STAGES.map((s) => (
              <SelectItem key={s} value={s}>
                {KANBAN_STAGE_LABELS[s]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* ── Empty ───────────────────────────────────────────────────── */}
      {candidates.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
          <Users className="h-12 w-12 text-muted-foreground/40" />
          <div>
            <p className="font-semibold">No candidates found</p>
            <p className="mt-1 text-sm text-muted-foreground">
              {search || stage !== "all"
                ? "Try adjusting your filters."
                : "Run screening to populate the candidate list."}
            </p>
          </div>
        </div>
      ) : (
        /* ── List ─────────────────────────────────────────────────── */
        <div className="rounded-xl border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40">
                <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Candidate
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground hidden sm:table-cell">
                  Stage
                </th>
                <th className="px-4 py-2.5 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Match
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground hidden md:table-cell">
                  Source
                </th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((c, i) => (
                <tr
                  key={c.applicationId}
                  className={cn(
                    "border-b border-border last:border-0 hover:bg-muted/30 transition-colors",
                    i % 2 === 0 ? "bg-transparent" : "bg-muted/10",
                  )}
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/jobs/${id}/candidates/${c.id}`}
                      className="hover:underline font-medium truncate block max-w-[220px]"
                    >
                      {c.name}
                    </Link>
                    {c.headline && (
                      <p className="text-xs text-muted-foreground truncate max-w-[220px]">
                        {c.headline}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-3 hidden sm:table-cell">
                    <span className="text-xs text-muted-foreground">
                      {KANBAN_STAGE_LABELS[c.pipelineStage]}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <MatchChip score={c.matchScore} skills={c.matchedSkills} />
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell">
                    <span className="text-xs text-muted-foreground">{c.sourceChannel ?? "—"}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {candidatePage && candidatePage.total > candidatePage.pageSize && (
            <div className="px-4 py-3 border-t border-border text-xs text-muted-foreground text-center">
              Showing {candidates.length} of {candidatePage.total} candidates
            </div>
          )}
        </div>
      )}
    </div>
  );
}

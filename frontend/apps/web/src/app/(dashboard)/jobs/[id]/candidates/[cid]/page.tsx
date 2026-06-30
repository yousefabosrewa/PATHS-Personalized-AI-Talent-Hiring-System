"use client";

import { use } from "react";
import { AlertCircle, RefreshCw, UserX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { useCandidateDetail } from "@/lib/hooks";
import { CandidateProfileHeader } from "@/components/features/candidate-profile/CandidateProfileHeader";
import { CvViewer } from "@/components/features/candidate-profile/CvViewer";
import { ScoreBreakdown } from "@/components/features/candidate-profile/ScoreBreakdown";
import { ActivityTimeline } from "@/components/features/candidate-profile/ActivityTimeline";
import { CandidateActionBar } from "@/components/features/candidate-profile/CandidateActionBar";

interface Props {
  params: Promise<{ id: string; cid: string }>;
}

export default function CandidateDetailPage({ params }: Props) {
  const { id: jobId, cid: candidateId } = use(params);

  const {
    data: candidate,
    isLoading,
    isError,
    error,
    refetch,
  } = useCandidateDetail(candidateId, jobId);

  // ── Loading ───────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="flex flex-col gap-6 p-6 max-w-5xl">
        <div className="flex items-start gap-4">
          <Skeleton className="h-14 w-14 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-4 w-64" />
            <Skeleton className="h-3 w-40" />
          </div>
        </div>
        <Skeleton className="h-8 w-60" />
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full rounded-lg" />
            ))}
          </div>
          <div className="space-y-4">
            <Skeleton className="h-48 rounded-xl" />
            <Skeleton className="h-48 rounded-xl" />
          </div>
        </div>
      </div>
    );
  }

  // ── Error ─────────────────────────────────────────────────────────────
  if (isError || !candidate) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
        {isError ? (
          <AlertCircle className="h-10 w-10 text-destructive" />
        ) : (
          <UserX className="h-10 w-10 text-muted-foreground" />
        )}
        <div>
          <p className="font-semibold">
            {isError ? "Failed to load candidate" : "Candidate not found"}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {error instanceof Error ? error.message : "An unexpected error occurred."}
          </p>
        </div>
        {isError && (
          <Button variant="outline" size="sm" onClick={() => refetch()} className="gap-2">
            <RefreshCw className="h-3.5 w-3.5" /> Try again
          </Button>
        )}
      </div>
    );
  }

  // ── Success ───────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-6 p-6 max-w-5xl">
      <CandidateProfileHeader candidate={candidate} jobId={jobId} />

      {/* Action bar */}
      <CandidateActionBar
        candidate={candidate}
        applicationId={candidateId}
        jobId={jobId}
      />

      <Separator />

      {/* Main layout */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left: CV */}
        <div className="lg:col-span-2">
          <CvViewer cv={candidate.cv} />
        </div>

        {/* Right: Score + Activity */}
        <div className="space-y-6">
          <div className="rounded-xl border border-border bg-card p-4">
            <ScoreBreakdown scores={candidate.scores} overallScore={candidate.overallScore} />
          </div>

          <div className="rounded-xl border border-border bg-card p-4">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Activity
            </h3>
            <ActivityTimeline activity={candidate.activity} />
          </div>
        </div>
      </div>
    </div>
  );
}

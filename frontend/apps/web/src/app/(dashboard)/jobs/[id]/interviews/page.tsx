"use client";

import { use } from "react";
import {
  AlertCircle,
  Calendar,
  CheckCircle2,
  Clock,
  ExternalLink,
  Loader2,
  RefreshCw,
  Video,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useJobDetail, useInterviewList } from "@/lib/hooks";
import { useAuthStore } from "@/lib/stores/auth.store";
import type { BackendInterviewListItem } from "@/lib/api";
import { JobHeader } from "@/components/features/job-detail/JobHeader";
import { JobTabBar } from "@/components/features/job-detail/JobTabBar";
import { JobStatsStrip } from "@/components/features/job-detail/JobStatsStrip";
import { cn } from "@/lib/utils";

interface Props {
  params: Promise<{ id: string }>;
}

const STATUS_COLORS: Record<string, string> = {
  scheduled:  "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  // AI-run interviews started from a candidate profile land here.
  in_progress:"bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400",
  completed:  "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  cancelled:  "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
  no_show:    "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  rescheduled:"bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  draft:      "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
};

const TYPE_LABELS: Record<string, string> = {
  hr: "HR",
  technical: "Technical",
  mixed: "Mixed",
};

const STATUS_DISPLAY_LABELS: Record<string, string> = {
  no_show: "No-show",
  rescheduled: "Rescheduled",
  cancelled: "Cancelled",
};

function InterviewStatusBadge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize",
        STATUS_COLORS[status] ?? STATUS_COLORS.draft,
      )}
    >
      {STATUS_DISPLAY_LABELS[status] ?? status.replace(/_/g, " ")}
    </span>
  );
}

// An interview is considered "missed" when its scheduled slot has lapsed by
// more than this grace window without anyone joining (still in "scheduled").
const NO_SHOW_GRACE_MS = 2 * 60 * 60 * 1000; // 2 hours

type InterviewRow = { iv: BackendInterviewListItem; displayStatus: string };

/**
 * Bucket an interview into the active list or the cancelled section, and derive
 * the status to display. Rescheduled, cancelled and no-show interviews are
 * "cancelled"; a still-"scheduled" interview whose time + 2h has passed without
 * anyone joining is treated as a no-show and also moves to cancelled.
 */
function classifyInterview(iv: BackendInterviewListItem, now: number): {
  bucket: "active" | "cancelled";
  displayStatus: string;
} {
  const raw = iv.status;
  if (raw === "cancelled" || raw === "no_show" || raw === "rescheduled") {
    return { bucket: "cancelled", displayStatus: raw };
  }
  if (raw === "scheduled" && iv.scheduled_start) {
    const t = new Date(iv.scheduled_start).getTime();
    if (Number.isFinite(t) && now > t + NO_SHOW_GRACE_MS) {
      return { bucket: "cancelled", displayStatus: "no_show" };
    }
  }
  return { bucket: "active", displayStatus: raw };
}

function InterviewTable({ rows, jobId }: { rows: InterviewRow[]; jobId: string }) {
  return (
    <div className="rounded-xl border border-border overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/40">
            <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Candidate
            </th>
            <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground hidden sm:table-cell">
              Type
            </th>
            <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Status
            </th>
            <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground hidden lg:table-cell">
              Performance
            </th>
            <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground hidden md:table-cell">
              Scheduled
            </th>
            <th className="px-4 py-2.5 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Actions
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ iv: interview, displayStatus }, i) => (
            <tr
              key={interview.interview_id}
              className={cn(
                "border-b border-border last:border-0 hover:bg-muted/30 transition-colors",
                i % 2 === 0 ? "bg-transparent" : "bg-muted/10",
              )}
            >
              <td className="px-4 py-3 font-medium">{interview.candidate_name}</td>
              <td className="px-4 py-3 hidden sm:table-cell">
                <span className="text-xs text-muted-foreground">
                  {TYPE_LABELS[interview.interview_type] ?? interview.interview_type}
                </span>
              </td>
              <td className="px-4 py-3">
                <InterviewStatusBadge status={displayStatus} />
              </td>
              <td className="px-4 py-3 hidden lg:table-cell">
                {interview.final_score != null || interview.recommendation ? (
                  <div className="flex flex-col gap-0.5">
                    {interview.final_score != null && (
                      <span
                        className={cn(
                          "text-xs font-semibold",
                          interview.final_score >= 75
                            ? "text-emerald-400"
                            : interview.final_score >= 50
                              ? "text-amber-400"
                              : "text-red-400",
                        )}
                      >
                        {Math.round(interview.final_score)}/100
                        {interview.confidence != null
                          ? ` · ${Math.round((interview.confidence <= 1 ? interview.confidence * 100 : interview.confidence))}% conf`
                          : ""}
                      </span>
                    )}
                    {interview.recommendation && (
                      <span
                        className="text-[11px] text-muted-foreground truncate max-w-[200px]"
                        title={interview.recommendation}
                      >
                        {interview.recommendation}
                      </span>
                    )}
                  </div>
                ) : (
                  <span className="text-xs text-muted-foreground">
                    {interview.status === "completed" ? "Pending analysis" : "—"}
                  </span>
                )}
              </td>
              <td className="px-4 py-3 hidden md:table-cell">
                <span className="text-xs text-muted-foreground">
                  {interview.scheduled_start
                    ? new Date(interview.scheduled_start).toLocaleString()
                    : "—"}
                </span>
              </td>
              <td className="px-4 py-3 text-right">
                <div className="flex items-center justify-end gap-2">
                  {interview.meeting_url && (
                    <a
                      href={interview.meeting_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                    >
                      <Video className="h-3.5 w-3.5" />
                      Join
                    </a>
                  )}
                  <Link href={`/jobs/${jobId}/interviews/${interview.interview_id}`}>
                    <Button variant="ghost" size="sm" className="h-7 gap-1 text-xs">
                      <ExternalLink className="h-3 w-3" />
                      {interview.status === "completed" ? "Analysis" : "View"}
                    </Button>
                  </Link>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function InterviewsPage({ params }: Props) {
  const { id } = use(params);
  // Source the org from the auth store (the legacy `paths_org` localStorage key
  // was never written, so reading it left orgId empty and the interview query
  // disabled — the tab always showed "no interviews").
  const { user } = useAuthStore();
  const orgId = user?.orgId ?? "";

  const {
    data: job,
    isLoading: jobLoading,
    isError: jobError,
  } = useJobDetail(id);

  const {
    data: interviews = [],
    isLoading: intLoading,
    isError: intError,
    refetch,
  } = useInterviewList(orgId);

  const isLoading = jobLoading || intLoading;
  const isError = jobError || intError;

  // Filter to this job's interviews — strict job_id match (the list now
  // returns job_id); fall back to the job-title heuristic for old rows.
  const jobInterviews = interviews.filter((i) =>
    i.job_id ? i.job_id === id : Boolean(job?.title && i.job_title === job.title),
  );

  // Split into active vs cancelled. "Cancelled" collects rescheduled, cancelled,
  // explicit no-shows, and scheduled interviews whose slot lapsed by >2h with
  // nobody joining (auto no-show).
  const now = Date.now();
  const activeRows: InterviewRow[] = [];
  const cancelledRows: InterviewRow[] = [];
  for (const iv of jobInterviews) {
    const { bucket, displayStatus } = classifyInterview(iv, now);
    (bucket === "cancelled" ? cancelledRows : activeRows).push({ iv, displayStatus });
  }

  // ── Loading ───────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="flex flex-col gap-5 p-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-10 w-full" />
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  // ── Error ─────────────────────────────────────────────────────────────────
  if (isError || !job) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
        <AlertCircle className="h-10 w-10 text-destructive" />
        <p className="font-semibold">Failed to load interviews</p>
        <Button variant="outline" size="sm" onClick={() => refetch()} className="gap-2">
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

      {/* ── Empty ─────────────────────────────────────────────────────────── */}
      {jobInterviews.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
          <Calendar className="h-12 w-12 text-muted-foreground/40" />
          <div>
            <p className="font-semibold">No interviews scheduled</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Schedule interviews from the candidates list after shortlisting.
            </p>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          {/* ── Active interviews ─────────────────────────────────────────── */}
          <section className="flex flex-col gap-2">
            {activeRows.length > 0 ? (
              <InterviewTable rows={activeRows} jobId={id} />
            ) : (
              <div className="rounded-xl border border-dashed border-border py-10 text-center text-sm text-muted-foreground">
                No active interviews — everything is in the cancelled section below.
              </div>
            )}
          </section>

          {/* ── Cancelled / missed interviews ─────────────────────────────── */}
          {cancelledRows.length > 0 && (
            <section className="flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <XCircle className="h-4 w-4 text-rose-500" />
                <h3 className="text-sm font-semibold">Cancelled</h3>
                <Badge variant="outline" className="text-[10px]">
                  {cancelledRows.length}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground">
                Rescheduled, cancelled, or missed interviews — including ones where nobody
                joined within 2&nbsp;hours of the scheduled time.
              </p>
              <InterviewTable rows={cancelledRows} jobId={id} />
            </section>
          )}
        </div>
      )}
    </div>
  );
}

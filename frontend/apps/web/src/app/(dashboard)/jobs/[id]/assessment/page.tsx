"use client";

/**
 * Assessment tab for a single job (replaces the old Screening tab).
 *
 * Lists every candidate on the job and whether they took the published
 * assessment — with their score and a short AI performance summary. Rows
 * expand to show strengths / areas to improve; "View profile" opens the
 * candidate.
 */

import { use, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import {
  ChevronDown,
  ClipboardCheck,
  Eye,
  FileText,
  Info,
  Loader2,
} from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useJobDetail, useJobAssessmentResults } from "@/lib/hooks";
import { JobHeader } from "@/components/features/job-detail/JobHeader";
import { JobTabBar } from "@/components/features/job-detail/JobTabBar";
import { JobStatsStrip } from "@/components/features/job-detail/JobStatsStrip";
import { cn } from "@/lib/utils/cn";
import { initials } from "@/lib/utils/format";
import type { BackendAssessmentResultRow } from "@/lib/api";

function scoreColor(pct: number | null): string {
  if (pct == null) return "text-muted-foreground";
  if (pct >= 75) return "text-emerald-400";
  if (pct >= 50) return "text-amber-400";
  return "text-red-400";
}

function CandidateAssessmentRow({
  row,
  expanded,
  onToggle,
}: {
  row: BackendAssessmentResultRow;
  expanded: boolean;
  onToggle: () => void;
}) {
  const taken = row.status === "submitted";
  const pct = row.score_percent;

  return (
    <div
      className={cn(
        "glass rounded-xl overflow-hidden transition-all",
        expanded && taken && "ring-1 ring-primary/20 glow-blue",
      )}
    >
      <button
        onClick={onToggle}
        disabled={!taken}
        className={cn(
          "w-full flex items-center gap-4 p-4 text-left transition-colors",
          taken ? "hover:bg-primary/5" : "cursor-default opacity-90",
        )}
      >
        <Avatar className="h-10 w-10 shrink-0">
          <AvatarFallback className="bg-primary/10 text-primary text-xs font-semibold">
            {initials(row.candidate_name ?? "—")}
          </AvatarFallback>
        </Avatar>

        <div className="flex-1 min-w-0">
          <p className="text-[14px] font-semibold text-foreground truncate">
            {row.candidate_name ?? "Candidate"}
          </p>
          <p className="text-[12px] text-muted-foreground truncate">
            {row.current_title || "—"}
            {row.stage ? ` · ${row.stage.replace(/_/g, " ")}` : ""}
          </p>
        </div>

        {/* Status / score */}
        {taken ? (
          <div className="text-right shrink-0">
            <p className={cn("font-mono text-2xl font-bold tracking-tight", scoreColor(pct))}>
              {pct == null ? "—" : `${Math.round(pct)}%`}
            </p>
            <p className="text-[10px] text-muted-foreground">
              {row.score != null && row.max_score != null
                ? `${Math.round(row.score)}/${Math.round(row.max_score)}`
                : "assessment score"}
            </p>
          </div>
        ) : (
          <Badge
            variant="outline"
            className="shrink-0 border-muted/40 bg-muted/20 text-[10px] text-muted-foreground"
          >
            Not taken
          </Badge>
        )}

        {row.provisional && taken && (
          <Badge
            variant="outline"
            className="shrink-0 border-amber-500/30 bg-amber-500/10 text-[10px] text-amber-300"
            title="Auto-grader was unavailable — provisional score pending review."
          >
            Provisional
          </Badge>
        )}

        {taken && (
          <ChevronDown
            className={cn(
              "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
              expanded && "rotate-180",
            )}
          />
        )}
      </button>

      <AnimatePresence>
        {expanded && taken && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className="border-t border-border/40 p-5 space-y-4">
              {row.summary && (
                <div className="rounded-lg bg-primary/5 border border-primary/10 p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-widest text-primary/70 mb-1.5">
                    Performance summary
                  </p>
                  <p className="text-[13px] text-foreground leading-relaxed">
                    {row.summary}
                  </p>
                </div>
              )}

              {row.strengths.length > 0 && (
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-widest text-emerald-400/70 mb-1.5">
                    Strengths
                  </p>
                  <ul className="ml-4 list-disc text-[13px] text-foreground/90 space-y-0.5">
                    {row.strengths.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                </div>
              )}

              {row.areas_to_improve.length > 0 && (
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-widest text-amber-400/70 mb-1.5">
                    Areas to improve
                  </p>
                  <ul className="ml-4 list-disc text-[13px] text-foreground/90 space-y-0.5">
                    {row.areas_to_improve.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                </div>
              )}

              {row.submitted_at && (
                <p className="text-[11px] text-muted-foreground">
                  Submitted {new Date(row.submitted_at).toLocaleString()}
                </p>
              )}

              {row.candidate_id && (
                <div className="flex items-center gap-2 pt-1">
                  <Link href={`/candidates/${row.candidate_id}`}>
                    <Button variant="outline" size="sm" className="h-8 gap-1.5 text-xs">
                      <Eye className="h-3.5 w-3.5" /> View profile
                    </Button>
                  </Link>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function JobAssessmentPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: job, isLoading: jobLoading } = useJobDetail(id);
  const { data, isLoading } = useJobAssessmentResults(id);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const toggle = (appId: string) =>
    setExpandedId((cur) => (cur === appId ? null : appId));

  const results = data?.results ?? [];

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
    <div className="h-full overflow-y-auto">
      <div className="sticky top-0 z-10 border-b border-border/50 bg-background/80 backdrop-blur-sm px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/jobs">
            <Button variant="ghost" size="sm" className="gap-1.5 text-muted-foreground hover:text-foreground -ml-2">
              ← Back
            </Button>
          </Link>
          <div className="h-5 w-px bg-border/50" />
          <div>
            <h1 className="font-heading text-base font-bold text-foreground">
              Assessment — {job?.title ?? "…"}
            </h1>
            <p className="text-[12px] text-muted-foreground">
              {data
                ? `${data.submitted_count} of ${data.total_count} candidate${data.total_count === 1 ? "" : "s"} took the assessment`
                : "Loading…"}
            </p>
          </div>
        </div>
        {data?.template_title && (
          <Badge variant="outline" className="gap-1.5 border-primary/20 text-primary text-[11px]">
            <ClipboardCheck className="h-3 w-3" /> {data.template_title}
          </Badge>
        )}
      </div>

      <div className="p-6 space-y-5 max-w-4xl">
        {job && (
          <>
            <JobHeader job={job} />
            <JobTabBar jobId={id} />
            <JobStatsStrip stats={job.stats} />
          </>
        )}

        {data && !data.has_assessment && (
          <div className="flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-[12px] text-amber-200">
            <Info className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              No assessment has been published for this job yet. Generate &amp; publish one
              from the assessment builder, then candidates can take it from their applications.
            </span>
          </div>
        )}

        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-heading text-lg font-bold text-foreground">Assessment results</h2>
            <p className="text-sm text-muted-foreground">
              Every candidate on this job, with their assessment score and AI performance summary.
              Click a row that has been taken to expand it.
            </p>
          </div>
        </div>

        {isLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-16 w-full rounded-xl" />
            <Skeleton className="h-16 w-full rounded-xl" />
          </div>
        ) : (
          <div className="space-y-3">
            {results.map((row) => (
              <CandidateAssessmentRow
                key={row.application_id}
                row={row}
                expanded={expandedId === row.application_id}
                onToggle={() => toggle(row.application_id)}
              />
            ))}
            {results.length === 0 && (
              <div className="rounded-xl border border-dashed border-border/40 p-16 text-center">
                <FileText className="mx-auto h-10 w-10 text-muted-foreground/30 mb-3" />
                <p className="text-sm font-medium text-muted-foreground">
                  No candidates on this job yet.
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

"use client";

/**
 * Screening board for a single job (Fixes.md §4–§9).
 *
 * What this page is for:
 *   • Show the candidates currently in the screening funnel for this job.
 *   • Let the recruiter Advance or Remove each one.
 *   • Surface the per-candidate score breakdown when the row is expanded.
 *
 * What this page is NOT for (intentionally removed):
 *   • "Propose Shortlist" — HITL approval lives on the Decision tab now.
 *   • Per-row "Run Screening" — scoring runs automatically on the screening
 *     run / shortlist flow; the recruiter no longer triggers it here.
 *   • Fake-zero scores — when no scoring data exists we render "Score pending"
 *     rather than a misleading "0".
 */

import { use, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import {
  AlertTriangle,
  BarChart2,
  CheckCircle2,
  ChevronDown,
  Eye,
  Info,
  Layers,
  Loader2,
  Play,
  RefreshCw,
  Star,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useJobDetail,
  useShortlist,
  useRunScreening,
  useScreeningRun,
  useAdvanceStage,
  useScreeningSourceCandidates,
  useAddCandidateToJob,
} from "@/lib/hooks";
import { useAuthStore } from "@/lib/stores/auth.store";
import { useQueryClient } from "@tanstack/react-query";
import { JobHeader } from "@/components/features/job-detail/JobHeader";
import { JobTabBar } from "@/components/features/job-detail/JobTabBar";
import { JobStatsStrip } from "@/components/features/job-detail/JobStatsStrip";
import { cn } from "@/lib/utils/cn";
import { initials } from "@/lib/utils/format";
import type { Application } from "@/types";
import type { BackendScreeningResult } from "@/lib/api";

// ── Run Status Card ──────────────────────────────────────────────────────────

const RUN_STATUS_STYLES: Record<
  string,
  { bar: string; badge: string; label: string }
> = {
  pending:   { bar: "bg-amber-500 animate-pulse w-1/3",  badge: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",  label: "Pending"   },
  running:   { bar: "bg-blue-500 animate-pulse w-2/3",   badge: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",       label: "Running"   },
  completed: { bar: "bg-green-500 w-full",               badge: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",   label: "Completed" },
  failed:    { bar: "bg-red-500 w-1/4",                  badge: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",           label: "Failed"    },
};

function ScreeningRunCard({
  runId,
  onRefresh,
  refreshing,
}: {
  runId: string;
  onRefresh: () => void;
  refreshing: boolean;
}) {
  const { data: run, isLoading } = useScreeningRun(runId);

  if (isLoading) return <Skeleton className="h-20 w-full rounded-xl" />;
  if (!run) return null;

  const style =
    RUN_STATUS_STYLES[run.status?.toLowerCase() ?? "pending"] ??
    RUN_STATUS_STYLES.pending;

  return (
    <div className="rounded-xl border border-border bg-card p-4 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <BarChart2 className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold">Screening Run</span>
          <span
            className={cn(
              "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
              style.badge,
            )}
          >
            {style.label}
          </span>
        </div>
        <Button
          size="sm"
          variant="ghost"
          className="h-7 gap-1 text-xs text-muted-foreground"
          onClick={onRefresh}
          disabled={refreshing}
        >
          <RefreshCw className={cn("h-3.5 w-3.5", refreshing && "animate-spin")} />
          Refresh
        </Button>
      </div>

      <div className="h-1.5 w-full rounded-full bg-muted/40 overflow-hidden">
        <div className={cn("h-full rounded-full transition-all duration-700", style.bar)} />
      </div>

      <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
        <span>
          <span className="font-medium text-foreground">Run ID: </span>
          {run.screening_run_id?.slice(0, 8)}…
        </span>
        {run.top_k && (
          <span>
            <span className="font-medium text-foreground">Top-K: </span>
            {run.top_k}
          </span>
        )}
        {run.results && (
          <span>
            <span className="font-medium text-foreground">Results: </span>
            {run.results.length}
          </span>
        )}
        {run.status === "failed" && run.error_message && (
          <span className="text-red-500">{run.error_message}</span>
        )}
      </div>
    </div>
  );
}

// ── Per-dimension score bar (inside expanded breakdown) ─────────────────────

function ScoreBar({
  label, raw, evidenceCount, confidence,
}: {
  label: string; raw: number; evidenceCount: number; confidence: number;
}) {
  const pct = Math.round(raw * 100);
  const confColor =
    confidence >= 0.75 ? "text-emerald-400"
    : confidence >= 0.5 ? "text-amber-400"
    : "text-red-400";
  const barColor =
    pct >= 75 ? "bg-emerald-500" : pct >= 50 ? "bg-amber-500" : "bg-red-500";

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-[12px] font-medium text-muted-foreground">{label}</span>
        <div className="flex items-center gap-3 text-[11px]">
          <span className={cn("font-semibold", confColor)}>
            {Math.round(confidence * 100)}% conf.
          </span>
          <span className="text-muted-foreground/60">{evidenceCount} ev.</span>
          <span className="font-mono font-bold text-foreground">{pct}%</span>
        </div>
      </div>
      <div className="h-2 w-full rounded-full bg-muted/40 overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.7, ease: "easeOut" }}
          className={cn("h-full rounded-full", barColor)}
        />
      </div>
    </div>
  );
}

// Stage progression order — MUST match VALID_STAGES on the backend.
const STAGE_ORDER = [
  "sourced",
  "applied",
  "screening",
  "assessment",
  "hr_interview",
  "tech_interview",
  "decision",
  "hired",
] as const;

// Stages the Screening tab owns. Anything past this set has been advanced
// out and shouldn't keep showing in the screening list.
const SCREENING_STAGES = new Set(["sourced", "applied", "screening"]);

function nextStage(current: string | null | undefined): string {
  if (!current) return "screening";
  const i = STAGE_ORDER.indexOf(current as (typeof STAGE_ORDER)[number]);
  return i >= 0 && i < STAGE_ORDER.length - 1 ? STAGE_ORDER[i + 1] : "screening";
}

// ── Candidate row ───────────────────────────────────────────────────────────

function CandidateShortlistRow({
  app, rank, expanded, onToggle,
}: {
  app: Application; rank: number; expanded: boolean; onToggle: () => void;
}) {
  const c = app.candidate;
  // Fixes.md §4: never silently render 0 for missing scoring data. If the
  // adapter couldn't extract a numeric score we render a "pending" badge
  // instead of a misleading "0". `matchScore === 0` from a real computation
  // is allowed through (it's a real zero, not missing data).
  const hasScore = typeof app.matchScore === "number" && !Number.isNaN(app.matchScore);
  const score = hasScore ? (app.matchScore as number) : null;

  const qc = useQueryClient();
  const advance = useAdvanceStage();
  const [busy, setBusy] = useState<"advance" | "remove" | null>(null);

  const a = app as unknown as Record<string, unknown>;
  const currentStage =
    (typeof a.stage === "string" ? a.stage : null) ??
    (typeof a.currentStageCode === "string" ? a.currentStageCode : null) ??
    (typeof a.current_stage_code === "string"
      ? (a.current_stage_code as string)
      : null);

  async function runMove(stage: string, kind: "advance" | "remove") {
    setBusy(kind);
    try {
      await advance.mutateAsync({ id: app.id, stage });
      // Refresh anything that lists candidates / applications.
      qc.invalidateQueries({ queryKey: ["candidates"] });
      qc.invalidateQueries({ queryKey: ["applications"] });
      qc.invalidateQueries({ queryKey: ["shortlist"] });
      qc.invalidateQueries({ queryKey: ["jobCandidates"] });
      toast.success(
        kind === "advance"
          ? `Advanced to ${stage.replace(/_/g, " ")}`
          : "Candidate removed from this job",
      );
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Action failed");
    } finally {
      setBusy(null);
    }
  }

  const scoreColor =
    score == null ? "text-muted-foreground"
    : score >= 80 ? "text-emerald-400"
    : score >= 60 ? "text-amber-400"
    : "text-red-400";

  return (
    <div
      className={cn(
        "glass rounded-xl overflow-hidden transition-all",
        expanded && "ring-1 ring-primary/20 glow-blue",
      )}
    >
      {/* Summary row — clicking it toggles the breakdown panel. */}
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-4 p-4 text-left hover:bg-primary/5 transition-colors"
      >
        {/* Rank */}
        <div
          className={cn(
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold",
            rank === 1
              ? "bg-amber-500/20 text-amber-400 ring-1 ring-amber-500/30"
              : rank === 2
              ? "bg-slate-500/20 text-slate-300 ring-1 ring-slate-500/30"
              : rank === 3
              ? "bg-orange-900/20 text-orange-400 ring-1 ring-orange-900/30"
              : "bg-muted/40 text-muted-foreground",
          )}
        >
          {rank === 1 ? "★" : rank}
        </div>

        {/* Avatar — keeps existing photo URL when present, falls back to
            initials. Fixes.md §6: never strip candidate photos. */}
        <Avatar className="h-10 w-10 shrink-0">
          {!app.isAnonymized && c.avatar && <AvatarImage src={c.avatar} alt={c.name} />}
          <AvatarFallback className="bg-primary/10 text-primary text-xs font-semibold">
            {app.isAnonymized ? "?" : initials(c.name)}
          </AvatarFallback>
        </Avatar>

        {/* Identity */}
        <div className="flex-1 min-w-0">
          <p className="text-[14px] font-semibold text-foreground truncate">
            {app.isAnonymized ? c.alias : c.name}
          </p>
          <p className="text-[12px] text-muted-foreground truncate">
            {c.title || "—"}{c.location ? ` · ${c.location}` : ""}
            {app.sourcePlatform ? ` · ${app.sourcePlatform}` : ""}
          </p>
        </div>

        {/* Score block */}
        <div className="text-right shrink-0">
          {score == null ? (
            <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-400">
              Score pending
            </span>
          ) : (
            <>
              <p className={cn("font-mono text-2xl font-bold tracking-tight", scoreColor)}>
                {score}
              </p>
              <p className="text-[10px] text-muted-foreground">match score</p>
            </>
          )}
        </div>

        {/* Confidence */}
        <div className="text-right shrink-0 hidden sm:block">
          {app.matchConfidence != null ? (
            <>
              <p
                className={cn(
                  "text-[13px] font-semibold",
                  app.matchConfidence >= 0.75 ? "text-emerald-400" : "text-amber-400",
                )}
              >
                {Math.round(app.matchConfidence * 100)}%
              </p>
              <p className="text-[10px] text-muted-foreground">confidence</p>
            </>
          ) : (
            <p className="text-[10px] text-muted-foreground">—</p>
          )}
        </div>

        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
            expanded && "rotate-180",
          )}
        />
      </button>

      {/* Expanded breakdown */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className="border-t border-border/40 p-5 space-y-5">
              {/* Score breakdown — populated when criteria_breakdown comes back */}
              {app.matchScores && app.matchScores.length > 0 ? (
                <div className="space-y-3">
                  <h4 className="text-[12px] font-semibold uppercase tracking-widest text-muted-foreground/60">
                    Score Breakdown
                  </h4>
                  {app.matchScores.map((s) => (
                    <ScoreBar
                      key={s.dimension}
                      label={s.dimension}
                      raw={s.raw}
                      evidenceCount={s.evidenceCount}
                      confidence={s.confidence}
                    />
                  ))}
                </div>
              ) : (
                <p className="rounded-lg border border-amber-500/15 bg-amber-500/5 px-3 py-2 text-[12px] text-amber-300">
                  Detailed score breakdown not available yet — re-run screening to
                  recompute the per-dimension matrix.
                </p>
              )}

              {/* AI rationale */}
              {app.explanation && (
                <div className="rounded-lg bg-primary/5 border border-primary/10 p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-widest text-primary/70 mb-1.5">
                    AI Rationale
                  </p>
                  <p className="text-[13px] text-foreground leading-relaxed">
                    {app.explanation}
                  </p>
                </div>
              )}

              {/* Evidence pills */}
              {c.evidenceItems.length > 0 && (
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/60 mb-2">
                    Evidence Used
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {c.evidenceItems.map((ev) => (
                      <span
                        key={ev.id}
                        className="evidence-pill max-w-[200px] truncate"
                        title={ev.extractedText}
                      >
                        {ev.extractedText.slice(0, 50)}…
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Bias flags */}
              {app.biasFlags && app.biasFlags.length > 0 && (
                <div className="rounded-lg bg-amber-500/5 border border-amber-500/15 p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-widest text-amber-400/70 mb-1.5">
                    Bias Flags
                  </p>
                  {app.biasFlags.map((flag) => (
                    <div
                      key={flag.rule}
                      className="flex items-center gap-2 text-[13px] text-amber-400"
                    >
                      <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                      {flag.description}
                    </div>
                  ))}
                </div>
              )}

              {/* Actions: View Profile / Advance / Remove */}
              <div className="flex items-center gap-2 pt-1">
                <Link href={`/candidates/${c.id}`}>
                  <Button variant="outline" size="sm" className="h-8 gap-1.5 text-xs">
                    <Eye className="h-3.5 w-3.5" /> View Profile
                  </Button>
                </Link>
                <Button
                  size="sm"
                  disabled={busy !== null}
                  onClick={() => runMove(nextStage(currentStage), "advance")}
                  className="h-8 gap-1.5 text-xs bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/20 border border-emerald-500/20"
                >
                  {busy === "advance" ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  )}
                  Advance
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={busy !== null}
                  onClick={() => runMove("rejected", "remove")}
                  className="h-8 gap-1.5 text-xs text-destructive hover:bg-destructive/10"
                >
                  {busy === "remove" ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <XCircle className="h-3.5 w-3.5" />
                  )}
                  Remove
                </Button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Page ────────────────────────────────────────────────────────────────────

// ── Run Screening: top source-database candidates scored for this job ──────

function SourceScoreChip({ score }: { score: number | null }) {
  if (score == null) {
    return <span className="text-[11px] text-muted-foreground">—</span>;
  }
  const tone =
    score >= 75 ? "text-emerald-400" : score >= 50 ? "text-amber-400" : "text-rose-400";
  return (
    <span className={cn("font-mono text-base font-bold tabular-nums", tone)}>
      {score}
      <span className="text-[10px] font-normal text-muted-foreground">%</span>
    </span>
  );
}

function SourceCandidatesScreening({ jobId }: { jobId: string }) {
  const { data, isLoading, isError, refetch, isFetching } =
    useScreeningSourceCandidates(jobId);
  const add = useAddCandidateToJob(jobId);
  const [addingId, setAddingId] = useState<string | null>(null);
  const items = data?.items ?? [];

  const onAdd = async (candidateId: string) => {
    setAddingId(candidateId);
    try {
      const res = await add.mutateAsync(candidateId);
      toast.success(res.already_in_process ? "Already in the process." : "Candidate added to the process.");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not add the candidate.");
    } finally {
      setAddingId(null);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Star className="h-4 w-4 text-primary" />
        <h2 className="text-sm font-semibold">Top candidates from your database</h2>
        <span className="text-xs text-muted-foreground">· ranked by match to this job</span>
        <Button
          size="sm"
          variant="ghost"
          className="ml-auto h-7 gap-1.5 text-xs"
          onClick={() => refetch()}
          disabled={isFetching}
        >
          <RefreshCw className={cn("h-3.5 w-3.5", isFetching && "animate-spin")} /> Refresh
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full rounded-xl" />
          ))}
        </div>
      ) : isError ? (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/5 px-4 py-3 text-[12px] text-rose-300">
          Could not load candidates from your database.
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border/40 px-4 py-8 text-center text-[12px] text-muted-foreground">
          No candidates in your database yet. Import or source candidates first.
        </div>
      ) : (
        <div className="rounded-xl border border-border/40 overflow-hidden divide-y divide-border/40">
          {items.map((c, i) => (
            <div key={c.candidate_id} className="flex items-center gap-3 px-4 py-3 hover:bg-muted/20 transition-colors">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[11px] font-bold text-primary">
                {i + 1}
              </span>
              <Avatar className="h-9 w-9 shrink-0">
                <AvatarFallback className="bg-primary/10 text-primary text-xs font-semibold">
                  {initials(c.name ?? "?")}
                </AvatarFallback>
              </Avatar>
              <Link href={`/candidates/${c.candidate_id}`} className="min-w-0 flex-1 hover:underline">
                <p className="truncate text-[13px] font-semibold text-foreground">{c.name}</p>
                {(c.current_title || c.headline) && (
                  <p className="truncate text-[11px] text-muted-foreground">{c.current_title || c.headline}</p>
                )}
              </Link>
              <SourceScoreChip score={c.score} />
              {c.already_applied ? (
                <span className="flex items-center gap-1 text-[11px] text-emerald-400">
                  <CheckCircle2 className="h-3.5 w-3.5" /> In process
                </span>
              ) : (
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 gap-1.5 text-xs"
                  onClick={() => onAdd(c.candidate_id)}
                  disabled={addingId === c.candidate_id}
                >
                  {addingId === c.candidate_id ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Play className="h-3.5 w-3.5" />
                  )}
                  Add to process
                </Button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ScreeningPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  // Source the org from the auth store (the legacy `paths_org` localStorage key
  // was never written, so reading it left orgId empty — the "Run Screening"
  // button was permanently disabled with "Organisation ID missing").
  const { user } = useAuthStore();
  const orgId = user?.orgId ?? "";

  const { data: job, isLoading: jobLoading } = useJobDetail(id);
  const { data: rawShortlist = [] } = useShortlist(id);
  // Filter to the screening funnel only — advanced/rejected candidates
  // appear on the Pipeline / Decision tabs instead.
  const shortlist = useMemo(
    () =>
      rawShortlist.filter((app) => {
        const a = app as unknown as Record<string, unknown>;
        const stage = String(
          a.stage ?? a.currentStageCode ?? a.current_stage_code ?? "",
        ).toLowerCase();
        return !stage || SCREENING_STAGES.has(stage);
      }),
    [rawShortlist],
  );

  const { mutateAsync: runScreening, isPending: runPending } = useRunScreening(id);
  const qc = useQueryClient();
  const [latestRunId, setLatestRunId] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [runResults, setRunResults] = useState<BackendScreeningResult[] | null>(null);
  const [runMeta, setRunMeta] = useState<{ scored: number; scanned: number } | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(
    shortlist[0]?.id ?? null,
  );
  const toggle = (appId: string) =>
    setExpandedId((cur) => (cur === appId ? null : appId));

  async function handleRunScreening() {
    if (!orgId) {
      toast.error("Organization not found — please log in again.");
      return;
    }
    try {
      const result = await runScreening({ organization_id: orgId, top_k: 10 });
      setLatestRunId(result.screening_run_id ?? null);
      setRunResults(result.results ?? []);
      setRunMeta({
        scored: result.candidates_scored ?? (result.results?.length ?? 0),
        scanned: result.total_candidates_scanned ?? 0,
      });
      // Refresh anything that shows candidate scores.
      qc.invalidateQueries({ queryKey: ["shortlist"] });
      qc.invalidateQueries({ queryKey: ["jobCandidates"] });
      const n = result.results?.length ?? 0;
      toast.success(
        n > 0
          ? `Screening complete — ${n} candidate${n === 1 ? "" : "s"} scored & ranked.`
          : "Screening complete — no matching candidates in the database.",
      );
    } catch {
      toast.error("Failed to run screening");
    }
  }

  function handleRefreshRun() {
    setRefreshKey((k) => k + 1);
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
    <div className="h-full overflow-y-auto">
      {/* Sticky top bar */}
      <div className="sticky top-0 z-10 border-b border-border/50 bg-background/80 backdrop-blur-sm px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/jobs">
            <Button
              variant="ghost"
              size="sm"
              className="gap-1.5 text-muted-foreground hover:text-foreground -ml-2"
            >
              ← Back
            </Button>
          </Link>
          <div className="h-5 w-px bg-border/50" />
          <div>
            <h1 className="font-heading text-base font-bold text-foreground">
              Screening — {job?.title ?? "…"}
            </h1>
            <p className="text-[12px] text-muted-foreground">
              Score your database candidates against this job and add the best to the process.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge
            variant="outline"
            className="gap-1.5 border-primary/20 text-primary text-[11px]"
          >
            <Layers className="h-3 w-3" /> Anonymized scoring
          </Badge>
        </div>
      </div>

      <div className="p-6 space-y-5 max-w-4xl">
        {job && (
          <>
            <JobHeader job={job} />
            <JobTabBar jobId={id} />
            <JobStatsStrip stats={job.stats} />
          </>
        )}

        {/* Run Screening result — top candidates from your database, scored
            against this job, each with an "Add to process" action. */}
        <SourceCandidatesScreening jobId={id} />

        {latestRunId && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <BarChart2 className="h-4 w-4 text-primary" />
              <h2 className="text-sm font-semibold">Latest Screening Run</h2>
            </div>
            <ScreeningRunCard
              key={refreshKey}
              runId={latestRunId}
              onRefresh={handleRefreshRun}
              refreshing={false}
            />
          </div>
        )}

        {/* Ranked results from the latest "Run Screening" DB scan. */}
        {runResults && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Star className="h-4 w-4 text-primary" />
              <h2 className="text-sm font-semibold">
                Ranked results
                {runMeta ? ` — ${runMeta.scored} scored of ${runMeta.scanned} scanned` : ""}
              </h2>
            </div>
            {runResults.length === 0 ? (
              <div className="rounded-xl border border-dashed border-border/40 p-8 text-center text-sm text-muted-foreground">
                No matching candidates were found in the database for this job.
              </div>
            ) : (
              <div className="rounded-xl border border-border overflow-hidden">
                {runResults.map((r, i) => {
                  const pct = Math.round(r.final_score);
                  const tone =
                    pct >= 75 ? "text-emerald-400"
                    : pct >= 50 ? "text-amber-400"
                    : "text-red-400";
                  return (
                    <div
                      key={r.result_id}
                      className={cn(
                        "flex items-center gap-4 px-4 py-3 border-b border-border/40 last:border-0",
                        i % 2 ? "bg-muted/10" : "bg-transparent",
                      )}
                    >
                      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-muted/40 text-[12px] font-bold text-muted-foreground">
                        {r.rank_position ?? i + 1}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="text-[13px] font-semibold text-foreground truncate">
                          {r.blind_label}
                        </p>
                        <p className="text-[11px] text-muted-foreground">
                          {r.recommendation
                            ? r.recommendation.replace(/_/g, " ")
                            : r.match_classification ?? "scored"}
                          {" · "}vector {Math.round(r.vector_similarity_score)} · agent {Math.round(r.agent_score)}
                        </p>
                      </div>
                      <span className={cn("font-mono text-xl font-bold tabular-nums", tone)}>
                        {pct}
                        <span className="text-[10px] font-normal text-muted-foreground"> /100</span>
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
            <p className="text-[11px] text-muted-foreground">
              Candidates are anonymized (blind labels) until a manager approves de-anonymization
              on the Decision tab.
            </p>
          </div>
        )}

      </div>
    </div>
  );
}

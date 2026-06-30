"use client";

/**
 * Candidate → Development & Growth.
 *
 * Shows the candidate the role they were hired (or assessed) for, their
 * personalised development plan from the hiring decision — 18 months when
 * accepted, 12 months when rejected — with real calendar dates per phase and
 * a per-task progress tracker (To do · Doing · Done).
 */

import { useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import {
  TrendingUp, Briefcase, CalendarClock, ChevronDown, CheckCircle2,
  Loader2, Sparkles, Target, ListChecks, ArrowRight,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils/cn";
import { useMyDevelopmentPlan, useUpdateMyDevelopmentProgress } from "@/lib/hooks";
import type {
  BackendDevPlanPhase,
  BackendDevPlanTask,
  DevPlanTaskStatus,
} from "@/lib/api";

const STATUS_META: Record<DevPlanTaskStatus, { label: string; active: string }> = {
  todo: { label: "To do", active: "bg-muted text-foreground" },
  in_progress: { label: "Doing", active: "bg-amber-500/20 text-amber-300 ring-1 ring-amber-500/40" },
  done: { label: "Done", active: "bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/40" },
};

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: "short", year: "numeric" });
  } catch {
    return "";
  }
}

const PHASE_STATUS_BADGE: Record<string, string> = {
  done: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  in_progress: "border-amber-500/30 bg-amber-500/10 text-amber-400",
  not_started: "border-muted/40 bg-muted/20 text-muted-foreground",
};

const INFO_SECTIONS: Array<{ key: keyof BackendDevPlanPhase; heading: string }> = [
  { key: "skills_to_improve", heading: "Skills to build" },
  { key: "learning_resources", heading: "Learning resources" },
  { key: "measurable_outcomes_or_kpis", heading: "Outcomes / KPIs" },
  { key: "manager_check_in_points", heading: "Manager check-ins" },
  { key: "evidence_to_collect", heading: "Evidence to collect" },
];

function TaskRow({
  task,
  onSet,
  pending,
}: {
  task: BackendDevPlanTask;
  onSet: (status: DevPlanTaskStatus) => void;
  pending: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border/40 bg-muted/10 px-3 py-2">
      <span
        className={cn(
          "flex-1 min-w-0 text-[13px]",
          task.status === "done" ? "text-muted-foreground line-through" : "text-foreground/90",
        )}
      >
        {task.text}
      </span>
      <div className="inline-flex shrink-0 overflow-hidden rounded-md border border-border/50">
        {(["todo", "in_progress", "done"] as const).map((s) => (
          <button
            key={s}
            type="button"
            disabled={pending}
            onClick={() => onSet(s)}
            className={cn(
              "px-2.5 py-1 text-[11px] font-medium transition-colors",
              task.status === s
                ? STATUS_META[s].active
                : "text-muted-foreground hover:bg-muted/40",
              s !== "todo" && "border-l border-border/50",
            )}
          >
            {STATUS_META[s].label}
          </button>
        ))}
      </div>
    </div>
  );
}

function PhaseCard({
  phase,
  planId,
  index,
}: {
  phase: BackendDevPlanPhase;
  planId: string;
  index: number;
}) {
  const [open, setOpen] = useState(index === 0);
  const update = useUpdateMyDevelopmentProgress();

  const dateRange =
    phase.start_date && phase.end_date
      ? `${fmtDate(phase.start_date)} – ${fmtDate(phase.end_date)}`
      : "";
  const doneCount = phase.tasks.filter((t) => t.status === "done").length;

  const setStatus = (taskId: string, status: DevPlanTaskStatus) =>
    update.mutate({ plan_id: planId, item_id: taskId, status });

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04 }}
      className="glass gradient-border rounded-2xl overflow-hidden"
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-primary/5 transition-colors"
      >
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-[13px] font-bold text-primary">
          {index + 1}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[14px] font-semibold text-foreground">{phase.label}</p>
          {dateRange && (
            <p className="mt-0.5 flex items-center gap-1 text-[11px] text-muted-foreground">
              <CalendarClock className="h-3 w-3" /> {dateRange}
            </p>
          )}
        </div>
        {phase.tasks.length > 0 && (
          <span className="shrink-0 text-[11px] text-muted-foreground">
            {doneCount}/{phase.tasks.length} done
          </span>
        )}
        <Badge
          variant="outline"
          className={cn("shrink-0 text-[10px] capitalize", PHASE_STATUS_BADGE[phase.status] ?? "")}
        >
          {phase.status.replace(/_/g, " ")}
        </Badge>
        <ChevronDown
          className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")}
        />
      </button>

      {open && (
        <div className="space-y-4 border-t border-border/40 p-4">
          {phase.tasks.length > 0 ? (
            <div className="space-y-2">
              <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-widest text-primary/80">
                <ListChecks className="h-3.5 w-3.5" /> Tasks this phase
              </p>
              {phase.tasks.map((t) => (
                <TaskRow key={t.id} task={t} pending={update.isPending} onSet={(s) => setStatus(t.id, s)} />
              ))}
            </div>
          ) : (
            <p className="text-[12px] text-muted-foreground">No specific tasks listed for this phase.</p>
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            {INFO_SECTIONS.map(({ key, heading }) => {
              const items = (phase[key] as string[]) ?? [];
              if (!items.length) return null;
              return (
                <div key={String(key)}>
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
                    {heading}
                  </p>
                  <ul className="ml-3 mt-1 list-disc space-y-0.5 text-[12px] text-foreground/85">
                    {items.map((it, i) => (
                      <li key={i}>{it}</li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </motion.div>
  );
}

export default function CandidateDevelopmentPage() {
  const { data, isLoading } = useMyDevelopmentPlan();

  if (isLoading) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-8 space-y-5">
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-28 w-full rounded-2xl" />
        <Skeleton className="h-40 w-full rounded-2xl" />
      </div>
    );
  }

  if (!data?.has_plan) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-8">
        <div className="mb-6">
          <h1 className="font-heading text-3xl font-bold text-foreground">Development &amp; Growth</h1>
        </div>
        <div className="rounded-2xl border border-dashed border-border/40 py-16 text-center">
          <TrendingUp className="mx-auto mb-3 h-10 w-10 text-muted-foreground/30" />
          <p className="text-sm font-medium text-muted-foreground">
            {data?.message ?? "No development plan yet."}
          </p>
          <Button className="mt-5 gap-2" size="sm" variant="outline" asChild>
            <Link href="/candidate/applications">
              View applications <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </Button>
        </div>
      </div>
    );
  }

  const progress = data.progress ?? { total: 0, done: 0, in_progress: 0, todo: 0, percent: 0 };
  const accepted = data.decision === "accepted";

  return (
    <div className="mx-auto max-w-3xl px-6 py-8 space-y-6">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="font-heading text-3xl font-bold text-foreground">Development &amp; Growth</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Your personalised plan and progress for{" "}
          <span className="font-semibold text-foreground">{data.job_title ?? "your role"}</span>
          {data.company_name ? ` · ${data.company_name}` : ""}.
        </p>
      </motion.div>

      {/* Role + plan summary card */}
      <div className="glass gradient-border rounded-2xl p-5 space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge
            variant="outline"
            className={cn(
              "gap-1 text-[11px]",
              accepted
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                : "border-amber-500/30 bg-amber-500/10 text-amber-400",
            )}
          >
            <Briefcase className="h-3 w-3" />
            {accepted ? "Hired" : "Reapplication plan"} · {data.job_title ?? "Role"}
          </Badge>
          <Badge variant="outline" className="gap-1 text-[11px] text-muted-foreground">
            <Sparkles className="h-3 w-3" /> {data.title}
          </Badge>
          {data.duration_months ? (
            <Badge variant="outline" className="text-[11px] text-muted-foreground">
              {data.duration_months}-month plan
            </Badge>
          ) : null}
        </div>

        {data.summary && (
          <p className="text-[13px] leading-relaxed text-foreground/90">{data.summary}</p>
        )}

        {/* Overall progress */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-[12px]">
            <span className="flex items-center gap-1.5 font-medium text-foreground">
              <Target className="h-3.5 w-3.5 text-primary" /> Overall progress
            </span>
            <span className="font-mono font-bold text-foreground">{progress.percent}%</span>
          </div>
          <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted/40">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${progress.percent}%` }}
              transition={{ duration: 0.6, ease: "easeOut" }}
              className="h-full rounded-full bg-primary"
            />
          </div>
          <div className="flex flex-wrap gap-3 text-[11px] text-muted-foreground">
            <span className="flex items-center gap-1">
              <CheckCircle2 className="h-3 w-3 text-emerald-400" /> {progress.done} finished
            </span>
            <span className="flex items-center gap-1">
              <Loader2 className="h-3 w-3 text-amber-400" /> {progress.in_progress} in progress
            </span>
            <span className="flex items-center gap-1">
              <ListChecks className="h-3 w-3" /> {progress.todo} to do
            </span>
            <span className="text-muted-foreground/60">· {progress.total} tasks total</span>
          </div>
        </div>

        {data.candidate_message && (
          <div className="rounded-lg border border-primary/15 bg-primary/5 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-primary/70 mb-1">
              A note for you
            </p>
            <p className="whitespace-pre-wrap text-[12px] text-foreground/90">{data.candidate_message}</p>
          </div>
        )}
      </div>

      {/* Phases */}
      <div className="space-y-3">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
          Your roadmap · {(data.phases ?? []).length} phases
        </p>
        {(data.phases ?? []).map((phase, i) => (
          <PhaseCard key={phase.key} phase={phase} planId={data.plan_id ?? ""} index={i} />
        ))}
      </div>
    </div>
  );
}

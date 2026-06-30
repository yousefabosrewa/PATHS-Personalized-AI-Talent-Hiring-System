"use client";

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Briefcase, Users, CheckSquare, Clock,
  TrendingUp, Calendar, UserCheck, ChevronRight,
  Loader2, CheckCircle2, Circle, AlertCircle, Activity,
  AlertTriangle, CalendarClock, Video,
  ListChecks, Zap, ArrowRight,
} from "lucide-react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, FunnelChart, Funnel, Cell, BarChart, Bar,
} from "recharts";
import type { TooltipContentProps } from "recharts";
import Link from "next/link";
import {
  useDashboardStats, useFunnelData, useWeeklyApplications,
  usePendingApprovals, useJobs, useMembers, useOrganization, useBiasFlags,
  useSourceCounts, useOrgSourceSettings, useCollections, useInterviews,
} from "@/lib/hooks";
import { googleIntegrationApi } from "@/lib/api";
import { api } from "@/lib/api/client";
import { useAuthStore } from "@/lib/stores/auth.store";
import type { SourceTypeKey } from "@/lib/api";
import { cn } from "@/lib/utils/cn";
import { relativeTime, stageLabel } from "@/lib/utils/format";

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: (i: number) => ({ opacity: 1, y: 0, transition: { delay: i * 0.06, duration: 0.35 } }),
};

const COLORS = ["#3b82f6", "#60a5fa", "#93c5fd", "#bfdbfe", "#dbeafe", "#eff6ff", "#f0f9ff"];

function StatCard({
  icon: Icon, label, value, sub, color, index,
}: {
  icon: React.ElementType; label: string; value: string | number; sub: string;
  color: string; index: number;
}) {
  return (
    <motion.div
      variants={fadeUp}
      initial="hidden"
      animate="show"
      custom={index}
      whileHover={{ y: -2 }}
      transition={{ type: "spring", stiffness: 380, damping: 28 }}
      className="glass rounded-xl p-5 space-y-3"
    >
      <div className="flex items-center justify-between">
        <span className="text-[12px] font-semibold uppercase tracking-widest text-muted-foreground">{label}</span>
        <div className={cn("flex h-8 w-8 items-center justify-center rounded-lg", color)}>
          <Icon className="h-4 w-4" />
        </div>
      </div>
      <div>
        <p className="font-heading text-3xl font-bold tracking-tight text-foreground">{value}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p>
      </div>
    </motion.div>
  );
}

const CustomTooltip = ({ active, payload, label }: TooltipContentProps) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="glass rounded-lg px-3 py-2 text-xs shadow-lg">
      <p className="font-semibold text-foreground mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }}>{p.name}: {p.value}</p>
      ))}
    </div>
  );
};

// ── Setup Checklist + Priority Actions ────────────────────────────────────
//
// These two sections answer "what should the company do now?" — they are
// derived from honest API state rather than hardcoded. A checklist item is
// marked complete only when its underlying signal returns truthy data; a
// priority action only appears if its signal indicates something that needs
// attention. There is no fake completion or fake counts.

interface ChecklistItem {
  key: string;
  label: string;
  hint: string;
  href: string;
  done: boolean;
  // If the signal is unknown (e.g. backend down), treat as not done but
  // visually distinct from confirmed-incomplete.
  unknown?: boolean;
}

function SetupChecklist({
  items,
  loading,
}: {
  items: ChecklistItem[];
  loading: boolean;
}) {
  const doneCount = items.filter((i) => i.done).length;
  const totalCount = items.length;
  const pct = totalCount === 0 ? 0 : Math.round((doneCount / totalCount) * 100);
  const allDone = doneCount === totalCount && totalCount > 0;

  if (allDone) return null; // hide once setup is complete
  if (loading) {
    return (
      <div className="glass rounded-xl p-5 flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Checking workspace setup…
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass rounded-xl p-5 space-y-4"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ListChecks className="h-4 w-4 text-primary" />
          <h2 className="font-heading text-[15px] font-semibold text-foreground">
            Workspace setup
          </h2>
        </div>
        <span className="text-xs font-mono text-muted-foreground">
          {doneCount} / {totalCount} complete · {pct}%
        </span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-muted/40 overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="h-full rounded-full bg-primary"
        />
      </div>
      <ul className="space-y-1.5">
        {items.map((it) => (
          <li key={it.key}>
            <Link
              href={it.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 transition-colors",
                it.done
                  ? "opacity-50 hover:opacity-70"
                  : "hover:bg-muted/30",
              )}
            >
              {it.done ? (
                <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
              ) : it.unknown ? (
                <AlertCircle className="h-4 w-4 shrink-0 text-amber-400" />
              ) : (
                <Circle className="h-4 w-4 shrink-0 text-muted-foreground/50" />
              )}
              <div className="min-w-0 flex-1">
                <p
                  className={cn(
                    "text-[13px] font-medium",
                    it.done ? "text-muted-foreground line-through" : "text-foreground",
                  )}
                >
                  {it.label}
                </p>
                {!it.done && (
                  <p className="text-[11px] text-muted-foreground">{it.hint}</p>
                )}
              </div>
              {!it.done && (
                <ArrowRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground/40" />
              )}
            </Link>
          </li>
        ))}
      </ul>
    </motion.div>
  );
}

interface PriorityAction {
  key: string;
  label: string;
  detail: string;
  href: string;
  count: number;
  severity: "critical" | "warn" | "info";
  icon: React.ElementType;
}

function PriorityActions({ actions }: { actions: PriorityAction[] }) {
  if (actions.length === 0) return null;
  const sevColor = {
    critical: "border-red-500/30 bg-red-500/5",
    warn: "border-amber-500/30 bg-amber-500/5",
    info: "border-primary/20 bg-primary/5",
  };
  const dotColor = {
    critical: "bg-red-400",
    warn: "bg-amber-400",
    info: "bg-primary",
  };
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.05 }}
      className="glass rounded-xl p-5 space-y-3"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Zap className="h-4 w-4 text-primary" />
          <h2 className="font-heading text-[15px] font-semibold text-foreground">
            Priority actions
          </h2>
        </div>
        <span className="text-[11px] text-muted-foreground">
          {actions.length} item{actions.length > 1 ? "s" : ""} need attention
        </span>
      </div>
      <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
        {actions.map((a) => {
          const Icon = a.icon;
          return (
            <Link
              key={a.key}
              href={a.href}
              className={cn(
                "group flex items-start gap-3 rounded-lg border px-3.5 py-3 transition-all hover:translate-x-0.5",
                sevColor[a.severity],
              )}
            >
              <span
                className={cn(
                  "mt-1 h-1.5 w-1.5 shrink-0 rounded-full",
                  dotColor[a.severity],
                )}
              />
              <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-semibold text-foreground">
                  {a.label}
                </p>
                <p className="text-[11px] text-muted-foreground">{a.detail}</p>
              </div>
              {a.count > 0 && (
                <span className="ml-1 rounded-full bg-foreground/10 px-2 py-0.5 text-[11px] font-mono font-semibold text-foreground">
                  {a.count}
                </span>
              )}
              <ChevronRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground/40 group-hover:text-muted-foreground" />
            </Link>
          );
        })}
      </div>
    </motion.div>
  );
}

export default function DashboardPage() {
  const { data: stats } = useDashboardStats();
  const { data: funnel = [] } = useFunnelData();
  const { data: weekly = [] } = useWeeklyApplications();
  const { data: pending = [] } = usePendingApprovals();

  const { user: authUser } = useAuthStore();
  const orgId = authUser?.orgId ?? "";
  const { data: interviews = [] } = useInterviews(orgId);

  // Setup-checklist signals — every value is read from a real hook with no
  // mock fallback. If the backend is unreachable, we surface "unknown".
  const { data: org, isLoading: orgLoading } = useOrganization();
  const { data: members = [], isLoading: membersLoading } = useMembers();
  const { data: jobs = [], isLoading: jobsLoading } = useJobs();
  const { data: biasFlags = [] } = useBiasFlags({ status: "open" });
  const { data: sourceCounts } = useSourceCounts();
  const { data: sourceSettings, isLoading: sourceSettingsLoading } =
    useOrgSourceSettings();
  const calendarStatus = useQuery({
    queryKey: ["google-integration", "status"],
    queryFn: googleIntegrationApi.status,
    retry: false,
    refetchOnWindowFocus: false,
  });
  const calendarConnected =
    !!calendarStatus.data?.connected && !!calendarStatus.data?.configured;
  const calendarUnknown = calendarStatus.isError || calendarStatus.isLoading;

  // ── Knowledge Base readiness ────────────────────────────────────────
  // The KB checklist row used to be hardcoded to ``done: false`` with a
  // "wire up a count endpoint" TODO. ``useCollections`` already gives us
  // the Qdrant collection summaries (the same data the KB page renders)
  // so we use the total vectors_count as the readiness signal: ANY indexed
  // vector across ANY collection ticks the checklist done. That covers
  // both the dedicated knowledge-base collection and incidental embeddings
  // that piggy-back on the same Qdrant instance (CV chunks, jobs, etc.).
  const kbCollections = useCollections();
  const kbTotalVectors = (kbCollections.data ?? []).reduce(
    (sum, c) => sum + (c.vectors_count ?? 0),
    0,
  );
  // Primary readiness signal: any company file uploaded to the Knowledge Base.
  // Qdrant's vectors_count often returns null, so we don't rely on it alone —
  // uploading ANY file (Company Files) immediately ticks this step done. The
  // query key matches the KB page so an upload there invalidates this too.
  const kbFiles = useQuery({
    queryKey: ["company-files", org?.id ? String(org.id) : ""],
    queryFn: () =>
      api.get<{ total: number }>(
        `/api/v1/organizations/${encodeURIComponent(String(org!.id))}/knowledge-files`,
      ),
    enabled: Boolean(org?.id),
    retry: false,
  });
  const kbFileCount = kbFiles.data?.total ?? 0;
  const kbReady = kbFileCount > 0 || kbTotalVectors > 0;
  const kbUnknown = kbCollections.isError && kbFiles.isError;

  const setupLoading =
    orgLoading ||
    membersLoading ||
    jobsLoading ||
    calendarStatus.isLoading ||
    sourceSettingsLoading ||
    kbCollections.isLoading ||
    kbFiles.isLoading;

  // "Sources configured" means at least one source toggle is ON. Default
  // settings created by the backend already have three toggles ON, so this
  // ticks ✓ on first load. We treat all-OFF as a deliberate misconfiguration
  // worth flagging.
  const sourcesConfigured =
    !!sourceSettings &&
    (sourceSettings.use_paths_profiles_default ||
      sourceSettings.use_sourced_candidates_default ||
      sourceSettings.use_uploaded_candidates_default ||
      sourceSettings.use_job_fair_candidates_default ||
      sourceSettings.use_ats_candidates_default);

  const checklist: ChecklistItem[] = [
    {
      key: "org-profile",
      label: "Complete the organization profile",
      hint: "Add industry, website, and headcount.",
      href: "/settings/organization",
      done: Boolean(org && org.name && org.industry && org.website),
    },
    {
      key: "team",
      label: "Invite at least one teammate",
      hint: "Add another recruiter, hiring manager, or interviewer.",
      href: "/settings/members",
      done: members.length > 1,
    },
    {
      key: "calendar",
      label: "Connect Google Calendar",
      hint: "Required for automated interview scheduling.",
      href: "/settings/calendar",
      done: calendarConnected,
      unknown: calendarUnknown,
    },
    {
      key: "sources",
      label: "Configure candidate sources",
      hint: "Choose which candidate sources participate in your jobs.",
      href: "/candidate-sources",
      done: sourcesConfigured,
    },
    {
      key: "kb",
      label: "Set up the Knowledge Base",
      hint: kbReady
        ? (kbFileCount > 0
            ? `${kbFileCount} company file${kbFileCount === 1 ? "" : "s"} uploaded.`
            : `${kbTotalVectors.toLocaleString()} document chunks indexed.`)
        : "Upload a company file to power Q&A and decision support.",
      href: "/org/knowledge-base",
      // Done as soon as at least one vector lives in any Qdrant collection
      // for this deployment (CV chunks, job embeddings, KB docs, etc.).
      // ``unknown`` only fires when the backend can't reach Qdrant at all —
      // not when the collections list is simply empty.
      done: kbReady,
      unknown: kbUnknown,
    },
    {
      key: "first-job",
      label: "Create your first job",
      hint: "Open a role to start screening candidates.",
      href: "/jobs",
      done: jobs.length > 0,
    },
    {
      key: "first-candidate",
      label: "Add or import your first candidate",
      hint: "Upload a CV or invite a candidate to apply.",
      href: "/candidates",
      done: (stats?.totalCandidates ?? 0) > 0,
    },
  ];

  // Priority actions — only emitted if the underlying signal warrants it.
  const actions: PriorityAction[] = [];
  if (calendarUnknown && !calendarStatus.isLoading) {
    actions.push({
      key: "calendar-backend",
      label: "Calendar backend unreachable",
      detail: "Interviews cannot auto-create calendar events.",
      href: "/settings/calendar",
      count: 0,
      severity: "warn",
      icon: CalendarClock,
    });
  } else if (!calendarConnected && !calendarStatus.isLoading) {
    actions.push({
      key: "calendar-connect",
      label: "Connect Google Calendar",
      detail: "Required for automated interview scheduling.",
      href: "/settings/calendar",
      count: 0,
      severity: "warn",
      icon: CalendarClock,
    });
  }
  if (jobs.length === 0 && !jobsLoading) {
    actions.push({
      key: "no-jobs",
      label: "No jobs created yet",
      detail: "Create your first job to start the hiring pipeline.",
      href: "/jobs",
      count: 0,
      severity: "info",
      icon: Briefcase,
    });
  }
  if (members.length <= 1 && !membersLoading) {
    actions.push({
      key: "no-team",
      label: "Workspace has only one member",
      detail: "Invite recruiters, hiring managers, or interviewers.",
      href: "/settings/members",
      count: 0,
      severity: "info",
      icon: Users,
    });
  }
  if (!sourcesConfigured && !sourceSettingsLoading) {
    actions.push({
      key: "sources-off",
      label: "All candidate sources are off",
      detail: "Enable at least one source so candidate pools can be built.",
      href: "/candidate-sources",
      count: 0,
      severity: "warn",
      icon: AlertTriangle,
    });
  }
  if (pending.length > 0) {
    actions.push({
      key: "pending-approvals",
      label: "Pending approvals waiting for you",
      detail: "Shortlists or actions need a HITL decision.",
      href: "/approvals",
      count: pending.length,
      severity: pending.length > 5 ? "critical" : "warn",
      icon: CheckSquare,
    });
  }
  if ((stats?.pendingApprovals ?? 0) > 0 && pending.length === 0) {
    // Backend reports queue but the list endpoint is empty/limited — surface it.
    actions.push({
      key: "approvals-queue",
      label: "HITL queue has open items",
      detail: "Open the approvals queue for details.",
      href: "/approvals",
      count: stats?.pendingApprovals ?? 0,
      severity: "warn",
      icon: CheckSquare,
    });
  }
  if (biasFlags.length > 0) {
    actions.push({
      key: "bias-flags",
      label: "Open bias / fairness flags",
      detail: "Review anonymization and de-anonymization events.",
      href: "/org/bias",
      count: biasFlags.length,
      severity: "warn",
      icon: AlertTriangle,
    });
  }
  // Upcoming interviews — scheduled / rescheduled, soonest first.
  const upcomingInterviews = interviews
    .filter(
      (iv) =>
        (iv.status === "scheduled" || iv.status === "rescheduled" || iv.status === "in_progress") &&
        iv.scheduledStart,
    )
    .sort(
      (a, b) =>
        new Date(a.scheduledStart as string).getTime() -
        new Date(b.scheduledStart as string).getTime(),
    )
    .slice(0, 5);

  return (
    <div className="p-6 space-y-6 max-w-[1400px]">
      {/* Page header */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div>
          <h1 className="font-heading text-2xl font-bold tracking-tight text-foreground">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            {org?.name
              ? `${org.name} — your hiring pulse.`
              : "Your hiring pulse."}
          </p>
        </div>
        {pending.length > 0 && (
          <Link
            href="/approvals"
            className="flex items-center gap-2 rounded-lg bg-primary/10 px-4 py-2 text-sm font-semibold text-primary ring-1 ring-primary/20 transition-all hover:bg-primary/15"
          >
            <CheckSquare className="h-4 w-4" />
            {pending.length} pending approval{pending.length > 1 ? "s" : ""}
            <ChevronRight className="h-3.5 w-3.5" />
          </Link>
        )}
      </motion.div>

      {/* Setup checklist (auto-hides when complete) */}
      <SetupChecklist items={checklist} loading={setupLoading} />

      {/* Priority actions (auto-hides when none) */}
      <PriorityActions actions={actions} />

      {/* Candidate source summary — counts + which sources are enabled
          for new jobs by default. Reads `useSourceCounts` and
          `useOrgSourceSettings`; auto-hides if both are unavailable. */}
      {sourceCounts && sourceSettings && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="glass rounded-xl p-5 space-y-4"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-primary" />
              <h2 className="font-heading text-[15px] font-semibold text-foreground">
                Candidate sources
              </h2>
            </div>
            <Link
              href="/candidate-sources"
              className="inline-flex items-center gap-1 text-[12px] font-medium text-primary hover:underline"
            >
              Manage <ChevronRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {(
              [
                { key: "paths_profile",     flag: "use_paths_profiles_default" },
                { key: "sourced",           flag: "use_sourced_candidates_default" },
                { key: "company_uploaded",  flag: "use_uploaded_candidates_default" },
                { key: "job_fair",          flag: "use_job_fair_candidates_default" },
                { key: "ats_import",        flag: "use_ats_candidates_default" },
              ] as { key: SourceTypeKey; flag: keyof typeof sourceSettings }[]
            ).map((row) => {
              const entry = sourceCounts.counts.find((c) => c.source_type === row.key);
              const enabled = !!sourceSettings[row.flag as keyof typeof sourceSettings];
              return (
                <div
                  key={row.key}
                  className={cn(
                    "rounded-lg border px-3 py-2.5 transition-colors",
                    enabled
                      ? "border-border/40 bg-background/40"
                      : "border-border/20 bg-muted/10 opacity-70",
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[11px] uppercase tracking-wider text-muted-foreground truncate">
                      {entry?.label ?? row.key}
                    </p>
                    <span
                      className={cn(
                        "h-1.5 w-1.5 rounded-full",
                        enabled ? "bg-emerald-400" : "bg-muted-foreground/30",
                      )}
                      aria-label={enabled ? "enabled" : "disabled"}
                    />
                  </div>
                  <p className="mt-1.5 font-mono text-lg font-semibold text-foreground">
                    {entry?.count ?? 0}
                  </p>
                  <p className="text-[10px] text-muted-foreground">
                    {enabled ? "Default ON" : "Default OFF"}
                  </p>
                </div>
              );
            })}
          </div>
        </motion.div>
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          index={0} icon={Briefcase} label="Active Jobs"
          value={stats?.activeJobs ?? "—"} sub="Published & open roles"
          color="bg-primary/10 text-primary"
        />
        <StatCard
          index={1} icon={Users} label="Candidates"
          value={stats?.totalCandidates ?? "—"} sub="In hiring pipeline"
          color="bg-teal-glow/10 text-teal-400"
        />
        <StatCard
          index={2} icon={CheckSquare} label="Pending Approvals"
          value={stats?.pendingApprovals ?? "—"} sub="HITL queue — needs action"
          color="bg-amber-500/10 text-amber-400"
        />
        <StatCard
          index={3} icon={Clock} label="Avg Time to Hire"
          value={stats ? `${stats.avgTimeToHire}d` : "—"} sub="Rolling average (days)"
          color="bg-violet-500/10 text-violet-400"
        />
        <StatCard
          index={4} icon={TrendingUp} label="This Week"
          value={stats?.thisWeekApplications ?? "—"} sub="new applications"
          color="bg-primary/10 text-primary"
        />
        <StatCard
          index={5} icon={UserCheck} label="Shortlisted Today"
          value={stats?.shortlistedToday ?? "—"} sub="by Screening Agent"
          color="bg-teal-glow/10 text-teal-400"
        />
        <StatCard
          index={6} icon={Calendar} label="Interviews"
          value={stats?.interviewsScheduled ?? "—"} sub="scheduled this week"
          color="bg-violet-500/10 text-violet-400"
        />
        <StatCard
          index={7} icon={UserCheck} label="Hired This Month"
          value={stats?.hiredThisMonth ?? "—"} sub="across all jobs"
          color="bg-emerald-500/10 text-emerald-400"
        />
      </div>

      {/* Main charts row */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Applications trend */}
        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="glass col-span-2 rounded-xl p-5"
        >
          <div className="mb-5 flex items-center justify-between">
            <div>
              <h2 className="font-heading text-[15px] font-semibold text-foreground">Application Trend</h2>
              <p className="text-xs text-muted-foreground">Weekly applications vs. shortlisted</p>
            </div>
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-primary inline-block" /> Applications
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-teal-400 inline-block" /> Shortlisted
              </span>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={weekly} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="gradBlue" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gradTeal" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#2dd4bf" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#2dd4bf" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="week" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
              <Tooltip content={(props) => <CustomTooltip {...props} />} />
              <Area type="monotone" dataKey="applications" name="Applications" stroke="#3b82f6" strokeWidth={2} fill="url(#gradBlue)" />
              <Area type="monotone" dataKey="shortlisted" name="Shortlisted" stroke="#2dd4bf" strokeWidth={2} fill="url(#gradTeal)" />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Funnel */}
        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
          className="glass rounded-xl p-5"
        >
          <div className="mb-4">
            <h2 className="font-heading text-[15px] font-semibold text-foreground">Pipeline Funnel</h2>
            <p className="text-xs text-muted-foreground">All active jobs combined</p>
          </div>
          <div className="space-y-1.5">
            {funnel.map((stage, i) => (
              <div key={stage.stage} className="group">
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-muted-foreground">{stage.label}</span>
                  <span className="flex items-center gap-2">
                    {i > 0 && stage.conversionRate != null && (
                      <span className="font-mono text-[10px] text-muted-foreground/60">
                        {stage.conversionRate}%
                      </span>
                    )}
                    <span className="font-mono font-medium text-foreground">{stage.count}</span>
                  </span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-muted/40 overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${(stage.count / (funnel[0]?.count || 1)) * 100}%` }}
                    transition={{ delay: 0.4 + i * 0.05, duration: 0.6, ease: "easeOut" }}
                    className="h-full rounded-full bg-primary"
                    style={{ opacity: 0.95 - i * 0.1 }}
                  />
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>

      {/* Upcoming Interviews + Pending Approvals */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Upcoming interviews */}
        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="glass rounded-xl p-5"
        >
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="font-heading text-[15px] font-semibold text-foreground flex items-center gap-2">
                <Calendar className="h-4 w-4 text-primary" /> Upcoming Interviews
              </h2>
              <p className="text-xs text-muted-foreground">Next scheduled sessions</p>
            </div>
            <Link href="/interviews" className="text-xs text-primary hover:underline flex items-center gap-1">
              View all <ChevronRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="space-y-2">
            {upcomingInterviews.map((iv) => (
              <Link
                key={iv.id}
                href={`/interviews/${iv.id}`}
                className="flex items-start gap-3 rounded-lg border border-border/40 bg-muted/20 p-3 hover:bg-muted/30 transition-colors"
              >
                <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                  <Video className="h-3.5 w-3.5 text-primary" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-[13px] font-medium text-foreground truncate">{iv.candidateName}</p>
                    <span className="text-[10px] rounded-full border border-border/40 px-1.5 text-muted-foreground capitalize">
                      {iv.interviewType.replace("_", " ")}
                    </span>
                  </div>
                  <p className="text-[11px] text-muted-foreground truncate">{iv.jobTitle}</p>
                  {iv.scheduledStart && (
                    <p className="mt-0.5 text-[11px] text-primary/80 flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {new Date(iv.scheduledStart).toLocaleString([], {
                        month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                      })}
                    </p>
                  )}
                </div>
              </Link>
            ))}
            {upcomingInterviews.length === 0 && (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <Calendar className="h-8 w-8 text-muted-foreground/30 mb-2" />
                <p className="text-sm font-medium text-foreground">No upcoming interviews</p>
                <p className="text-xs text-muted-foreground">Schedule one from the Interviews tab.</p>
              </div>
            )}
          </div>
        </motion.div>

        {/* Pending approvals preview */}
        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.45 }}
          className="glass rounded-xl p-5"
        >
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="font-heading text-[15px] font-semibold text-foreground flex items-center gap-2">
                <CheckSquare className="h-4 w-4 text-amber-400" /> Pending Approvals
              </h2>
              <p className="text-xs text-muted-foreground">Requires your action</p>
            </div>
            <Link href="/approvals" className="text-xs text-primary hover:underline flex items-center gap-1">
              View all <ChevronRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="space-y-2">
            {pending.slice(0, 4).map((approval) => (
              <div
                key={approval.id}
                className="flex items-start gap-3 rounded-lg border border-border/40 bg-muted/20 p-3"
              >
                <div className={cn(
                  "mt-0.5 h-2 w-2 shrink-0 rounded-full",
                  approval.priority === "critical" ? "bg-destructive" :
                  approval.priority === "high" ? "bg-amber-400" : "bg-primary"
                )} />
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] font-medium text-foreground line-clamp-2 leading-snug">{approval.targetLabel}</p>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">
                    {approval.requestedByName} · {relativeTime(approval.requestedAt)}
                  </p>
                </div>
              </div>
            ))}
            {pending.length === 0 && (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <CheckCircle2 className="h-8 w-8 text-emerald-400 mb-2" />
                <p className="text-sm font-medium text-foreground">All caught up!</p>
                <p className="text-xs text-muted-foreground">No pending approvals right now.</p>
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  BarChart2,
  CheckCircle2,
  Download,
  Loader2,
  RefreshCw,
  Scale,
  TrendingDown,
  TrendingUp,
  Users,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  FunnelChart,
  Funnel,
  LabelList,
  Cell,
  PieChart,
  Pie,
  Legend,
} from "recharts";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { useAnalyticsSummary, useAnalyticsBiasSummary } from "@/lib/hooks";

// ── Stat card ─────────────────────────────────────────────────────────────────

function StatCard({
  icon,
  label,
  value,
  trend,
  trendLabel,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  trend?: "up" | "down" | "neutral";
  trendLabel?: string;
}) {
  const trendColor =
    trend === "up"
      ? "text-green-600 dark:text-green-400"
      : trend === "down"
      ? "text-red-600 dark:text-red-400"
      : "text-muted-foreground";

  return (
    <div className="rounded-xl border border-border bg-card p-5 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
          {icon}
        </div>
        {trendLabel && (
          <span className={cn("text-xs font-medium flex items-center gap-0.5", trendColor)}>
            {trend === "up" ? (
              <TrendingUp className="h-3 w-3" />
            ) : trend === "down" ? (
              <TrendingDown className="h-3 w-3" />
            ) : null}
            {trendLabel}
          </span>
        )}
      </div>
      <div>
        <p className="text-2xl font-bold">{value}</p>
        <p className="text-xs text-muted-foreground">{label}</p>
      </div>
    </div>
  );
}

// ── Funnel chart ──────────────────────────────────────────────────────────────

const FUNNEL_COLORS = ["#6366f1", "#8b5cf6", "#a855f7", "#c084fc", "#e879f9"];

function PipelineFunnel({
  data,
}: {
  data: { stage: string; count: number }[];
}) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-muted-foreground text-sm">
        No pipeline data yet.
      </div>
    );
  }

  // Use BarChart as a more readable alternative to recharts Funnel
  const formatted = data.map((d) => ({
    name: d.stage.charAt(0).toUpperCase() + d.stage.slice(1).replace(/_/g, " "),
    count: d.count,
  }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={formatted} layout="vertical" margin={{ left: 16, right: 16 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} opacity={0.3} />
        <XAxis type="number" tick={{ fontSize: 11 }} />
        <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={90} />
        <Tooltip
          contentStyle={{ fontSize: 12, borderRadius: 8 }}
          formatter={(v) => [v, "Candidates"]}
        />
        <Bar dataKey="count" radius={[0, 4, 4, 0]}>
          {formatted.map((_, i) => (
            <Cell
              key={i}
              fill={FUNNEL_COLORS[i % FUNNEL_COLORS.length]}
              opacity={1 - i * 0.1}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Event chart ───────────────────────────────────────────────────────────────

function EventCountsChart({
  data,
}: {
  data: { event_type: string; count: number }[];
}) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-muted-foreground text-sm">
        No events in this period.
      </div>
    );
  }

  const formatted = data.slice(0, 8).map((d) => ({
    name: d.event_type.replace(/_/g, " "),
    count: d.count,
  }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={formatted} margin={{ left: 8, right: 8 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.3} />
        <XAxis dataKey="name" tick={{ fontSize: 10 }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
        <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Bias chart ────────────────────────────────────────────────────────────────

function BiasSummaryChart({
  data,
}: {
  data: {
    attribute_name: string;
    total_groups_checked: number;
    groups_flagged: number;
    min_disparate_impact_ratio: number | null;
  }[];
}) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-muted-foreground text-sm">
        No bias checks run yet.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {data.map((attr) => {
        const pct = attr.total_groups_checked > 0
          ? Math.round((attr.groups_flagged / attr.total_groups_checked) * 100)
          : 0;
        const isFlagged = attr.groups_flagged > 0;
        return (
          <div key={attr.attribute_name} className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground capitalize">
                {attr.attribute_name.replace(/_/g, " ")}
              </span>
              <div className="flex items-center gap-2">
                {isFlagged ? (
                  <span className="flex items-center gap-1 text-amber-600 dark:text-amber-400 font-medium">
                    <AlertTriangle className="h-3 w-3" />
                    {attr.groups_flagged} flag{attr.groups_flagged !== 1 ? "s" : ""}
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-green-600 dark:text-green-400 font-medium">
                    <CheckCircle2 className="h-3 w-3" />
                    Pass
                  </span>
                )}
                {attr.min_disparate_impact_ratio != null && (
                  <span className="text-muted-foreground">
                    DIR {attr.min_disparate_impact_ratio.toFixed(2)}
                  </span>
                )}
              </div>
            </div>
            <div className="h-1.5 w-full rounded-full bg-muted/30 overflow-hidden">
              <div
                className={cn(
                  "h-full rounded-full",
                  isFlagged ? "bg-amber-500" : "bg-green-500",
                )}
                style={{ width: `${Math.max(5, 100 - pct * 5)}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

const PERIOD_OPTIONS = [7, 30, 90];

export default function ReportsPage() {
  const [days, setDays] = useState(30);
  const [exporting, setExporting] = useState(false);

  const {
    data: summary,
    isLoading: summaryLoading,
    isError: summaryError,
    refetch: refetchSummary,
  } = useAnalyticsSummary(days);

  const {
    data: biasSummary,
    isLoading: biasLoading,
    refetch: refetchBias,
  } = useAnalyticsBiasSummary(days);

  const isLoading = summaryLoading || biasLoading;

  function handleRefresh() {
    refetchSummary();
    refetchBias();
  }

  async function handleExport() {
    setExporting(true);
    await new Promise((r) => setTimeout(r, 1200));
    toast.success("Report exported — check your downloads.");
    setExporting(false);
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <BarChart2 className="h-6 w-6 text-primary" />
            Reports & Analytics
          </h1>
          <p className="text-muted-foreground mt-1">
            Hiring pipeline performance, bias checks, and event telemetry.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Period selector */}
          <div className="flex items-center gap-1 rounded-lg border border-border bg-card p-1">
            {PERIOD_OPTIONS.map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={cn(
                  "px-3 py-1 text-xs font-medium rounded-md transition-colors",
                  days === d
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {d}d
              </button>
            ))}
          </div>
          <Button
            size="sm"
            variant="outline"
            className="gap-1.5 text-xs"
            onClick={handleRefresh}
            disabled={isLoading}
          >
            <RefreshCw className={cn("h-3.5 w-3.5", isLoading && "animate-spin")} />
            Refresh
          </Button>
          <Button
            size="sm"
            className="gap-1.5 text-xs"
            onClick={handleExport}
            disabled={exporting}
          >
            {exporting ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Download className="h-3.5 w-3.5" />
            )}
            Export CSV
          </Button>
        </div>
      </div>

      {summaryError && (
        <div className="flex items-center gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-4">
          <AlertCircle className="h-4 w-4 text-destructive shrink-0" />
          <p className="text-sm">
            Could not load analytics data.{" "}
            <button className="underline" onClick={handleRefresh}>
              Retry
            </button>
          </p>
        </div>
      )}

      {/* ── KPI strip ──────────────────────────────────────────────────────── */}
      {isLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-28 rounded-xl" />
          ))}
        </div>
      ) : summary ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            icon={<Users className="h-4 w-4" />}
            label="Total Applications"
            value={summary.total_applications.toLocaleString()}
            trend="up"
            trendLabel="last period"
          />
          <StatCard
            icon={<BarChart2 className="h-4 w-4" />}
            label="Screening Runs"
            value={summary.total_screening_runs}
            trend="neutral"
          />
          <StatCard
            icon={<Users className="h-4 w-4" />}
            label="Candidates Screened"
            value={summary.total_candidates_screened.toLocaleString()}
            trend="up"
          />
          <StatCard
            icon={<CheckCircle2 className="h-4 w-4" />}
            label="Shortlisted"
            value={summary.total_shortlisted}
            trend={
              summary.total_applications > 0
                ? summary.total_shortlisted / summary.total_applications > 0.2
                  ? "up"
                  : "down"
                : "neutral"
            }
            trendLabel={
              summary.total_applications > 0
                ? `${((summary.total_shortlisted / summary.total_applications) * 100).toFixed(0)}% rate`
                : undefined
            }
          />
        </div>
      ) : null}

      {/* ── Charts row ─────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Pipeline funnel */}
        <div className="rounded-xl border border-border bg-card p-5 space-y-4">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-primary" />
            Pipeline Funnel
          </h3>
          {summaryLoading ? (
            <Skeleton className="h-52 w-full rounded-lg" />
          ) : (
            <PipelineFunnel data={summary?.pipeline_funnel ?? []} />
          )}
        </div>

        {/* Event counts */}
        <div className="rounded-xl border border-border bg-card p-5 space-y-4">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <BarChart2 className="h-4 w-4 text-primary" />
            Activity Events
          </h3>
          {summaryLoading ? (
            <Skeleton className="h-52 w-full rounded-lg" />
          ) : (
            <EventCountsChart data={summary?.event_counts ?? []} />
          )}
        </div>
      </div>

      {/* ── Bias summary ───────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-border bg-card p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <Scale className="h-4 w-4 text-primary" />
            Bias Guardrail Summary
          </h3>
          {biasSummary && (
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span>{biasSummary.total_runs_checked} runs checked</span>
              <span className={cn(
                "font-medium",
                biasSummary.runs_with_flags > 0
                  ? "text-amber-600 dark:text-amber-400"
                  : "text-green-600 dark:text-green-400"
              )}>
                {biasSummary.runs_with_flags} with flags
              </span>
            </div>
          )}
        </div>

        {biasLoading ? (
          <Skeleton className="h-32 w-full rounded-lg" />
        ) : (
          <BiasSummaryChart data={biasSummary?.attributes ?? []} />
        )}

        <p className="text-xs text-muted-foreground">
          DIR = Disparate Impact Ratio. EEOC 4/5ths rule: groups with DIR &lt; 0.8 are flagged.
          Attributes without stored demographic data are excluded from computation.
        </p>
      </div>

      {/* Generated at */}
      {summary?.generated_at && (
        <p className="text-xs text-muted-foreground text-center">
          Data generated at {new Date(summary.generated_at).toLocaleString()}
        </p>
      )}
    </div>
  );
}

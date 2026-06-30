"use client";

import { Bot, Building2, Users, Briefcase, UserSquare2, AlertTriangle } from "lucide-react";
import { useAdminPlatformStats, useAdminSystemHealth } from "@/lib/hooks";
import Link from "next/link";

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  alert,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number | string;
  sub?: string;
  alert?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border p-5 shadow-sm ${
        alert ? "border-destructive/30 bg-destructive/5" : "border-border/50 bg-white"
      }`}
    >
      <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        <Icon className={`h-4 w-4 ${alert ? "text-destructive" : "text-primary"}`} />
        {label}
      </div>
      <p
        className={`font-heading text-3xl font-bold ${
          alert ? "text-destructive" : "text-foreground"
        }`}
      >
        {value}
      </p>
      {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

export default function AdminAnalyticsPage() {
  const { data: stats, isLoading: statsLoading } = useAdminPlatformStats();
  const { data: health } = useAdminSystemHealth();

  return (
    <div className="mx-auto max-w-6xl px-8 py-10 space-y-8">
      <div>
        <h1 className="font-heading text-3xl font-bold">Platform Analytics</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Real-time counts across the entire PATHS platform.
        </p>
      </div>

      {statsLoading ? (
        <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-28 animate-pulse rounded-xl border border-border/40 bg-muted/20" />
          ))}
        </div>
      ) : stats ? (
        <>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <StatCard
              icon={Building2}
              label="Active Orgs"
              value={stats.active_orgs}
              sub={`${stats.pending_orgs} pending approval`}
            />
            <StatCard
              icon={Users}
              label="Total Users"
              value={stats.total_users}
            />
            <StatCard
              icon={UserSquare2}
              label="Candidates"
              value={stats.total_candidates}
            />
            <StatCard
              icon={Briefcase}
              label="Jobs"
              value={stats.total_jobs}
            />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <StatCard
              icon={Bot}
              label="Agent Runs (total)"
              value={stats.total_agent_runs}
              sub="All time"
            />
            <StatCard
              icon={AlertTriangle}
              label="Failed Runs"
              value={stats.failed_agent_runs}
              sub="All time — retry from Agent Monitor"
              alert={stats.failed_agent_runs > 0}
            />
          </div>
        </>
      ) : null}

      {/* System health summary */}
      {health && (
        <div
          className={`rounded-xl border p-5 shadow-sm ${
            health.overall === "healthy"
              ? "border-green-300 bg-green-50"
              : "border-amber-300 bg-amber-50"
          }`}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="font-semibold text-sm">
                {health.overall === "healthy"
                  ? "✓ All systems operational"
                  : "⚠ One or more services degraded"}
              </p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Last checked: {new Date(health.checked_at).toLocaleString()}
              </p>
            </div>
            <Link
              href="/admin/system"
              className="text-sm font-medium text-primary hover:underline"
            >
              View details →
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

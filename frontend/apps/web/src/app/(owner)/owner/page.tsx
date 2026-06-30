"use client";

import Link from "next/link";
import {
  TrendingUp, Users, AlertCircle, ArrowUpRight, ArrowDownRight,
  Building2, DollarSign,
} from "lucide-react";
import { useRevenueSummary } from "@/lib/hooks";

function fmt(cents: number, currency = "USD") {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(cents / 100);
}

function MetricCard({
  label,
  value,
  sub,
  icon: Icon,
  href,
}: {
  label: string;
  value: string;
  sub?: string;
  icon: React.ComponentType<{ className?: string }>;
  href?: string;
}) {
  const inner = (
    <div className="rounded-xl border border-border/50 bg-white p-5 shadow-sm hover:shadow-md transition-shadow">
      <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        <Icon className="h-4 w-4 text-primary" />
        {label}
      </div>
      <p className="font-heading text-3xl font-bold text-foreground">{value}</p>
      {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
  return href ? <Link href={href}>{inner}</Link> : inner;
}

export default function OwnerDashboardPage() {
  const { data: summary, isLoading, error } = useRevenueSummary();

  const churnPct = summary
    ? `${(summary.churn_rate_30d * 100).toFixed(1)}%`
    : "—";

  const orgGrowth =
    summary && summary.new_orgs_last_month > 0
      ? ((summary.new_orgs_this_month - summary.new_orgs_last_month) /
          summary.new_orgs_last_month) *
        100
      : null;

  return (
    <div className="mx-auto max-w-6xl px-8 py-10 space-y-8">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-heading text-3xl font-bold">Owner Dashboard</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Business command centre — real-time revenue metrics.
          </p>
        </div>
        <Link
          href="/owner/revenue"
          className="flex items-center gap-1.5 rounded-lg border border-border/50 px-3 py-1.5 text-sm font-medium hover:bg-muted/30"
        >
          <TrendingUp className="h-3.5 w-3.5" /> Full analytics
        </Link>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          Failed to load revenue data.
        </div>
      )}

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <div
              key={i}
              className="h-28 animate-pulse rounded-xl border border-border/40 bg-muted/20"
            />
          ))}
        </div>
      ) : summary ? (
        <>
          {/* KPI cards */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              label="MRR"
              value={fmt(summary.mrr_cents)}
              sub="Monthly recurring revenue"
              icon={DollarSign}
              href="/owner/revenue"
            />
            <MetricCard
              label="ARR"
              value={fmt(summary.arr_cents)}
              sub="Annualised"
              icon={TrendingUp}
            />
            <MetricCard
              label="Churn (30d)"
              value={churnPct}
              sub={churnPct === "0.0%" ? "No churn this period" : "Of active subscriptions"}
              icon={AlertCircle}
            />
            <MetricCard
              label="New orgs"
              value={String(summary.new_orgs_this_month)}
              sub={
                orgGrowth !== null
                  ? `${orgGrowth >= 0 ? "+" : ""}${orgGrowth.toFixed(0)}% vs last month`
                  : `${summary.new_orgs_last_month} last month`
              }
              icon={Building2}
              href="/owner/orgs"
            />
          </div>

          {/* Revenue by plan */}
          {summary.revenue_by_plan.length > 0 && (
            <div className="rounded-xl border border-border/50 bg-white p-5 shadow-sm">
              <h2 className="mb-4 font-heading text-lg font-semibold">Revenue by Plan</h2>
              <div className="space-y-3">
                {summary.revenue_by_plan.map((p) => (
                  <div key={p.plan}>
                    <div className="mb-1 flex items-center justify-between text-sm">
                      <span className="capitalize font-medium">{p.plan}</span>
                      <span className="font-semibold">{fmt(p.cents)}</span>
                    </div>
                    <div className="h-2 rounded-full bg-muted">
                      <div
                        className="h-2 rounded-full bg-primary"
                        style={{ width: `${(p.pct * 100).toFixed(0)}%` }}
                      />
                    </div>
                    <p className="mt-0.5 text-right text-[10px] text-muted-foreground">
                      {(p.pct * 100).toFixed(0)}%
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Alerts */}
          {summary.alerts.length > 0 && (
            <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-5 shadow-sm">
              <h2 className="mb-3 font-heading text-lg font-semibold text-destructive">
                Payment Alerts
              </h2>
              <div className="space-y-2">
                {summary.alerts.map((a, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-3 rounded-lg border border-destructive/20 bg-white p-3"
                  >
                    <AlertCircle className="h-4 w-4 shrink-0 text-destructive" />
                    <span className="text-sm">{a.message}</span>
                    <code className="ml-auto text-xs text-muted-foreground">{a.org_id}</code>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Quick links */}
          <div className="grid gap-3 sm:grid-cols-3">
            {[
              { href: "/owner/customers", label: "Customer Health", desc: "View at-risk accounts" },
              { href: "/owner/plans", label: "Plans Editor", desc: "Update pricing" },
              { href: "/owner/announcements", label: "Announcements", desc: "Send platform-wide" },
            ].map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="rounded-xl border border-border/50 bg-white p-4 shadow-sm hover:shadow-md transition-shadow"
              >
                <p className="font-semibold text-sm">{item.label}</p>
                <p className="text-xs text-muted-foreground mt-0.5">{item.desc}</p>
                <ArrowUpRight className="mt-3 h-4 w-4 text-primary" />
              </Link>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}

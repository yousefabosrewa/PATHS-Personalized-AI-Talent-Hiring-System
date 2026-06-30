"use client";

import { useState } from "react";
import {
  AlertCircle,
  ArrowUpRight,
  Check,
  CreditCard,
  ExternalLink,
  FileText,
  Loader2,
  RefreshCw,
  Sparkles,
  TrendingUp,
  Zap,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import {
  useOrgSubscription,
  useOrgInvoices,
  useUsage,
  useCustomerPortalLink,
  usePublicPlans,
} from "@/lib/hooks";
import { useAuthStore } from "@/lib/stores/auth.store";

// ── Helpers ───────────────────────────────────────────────────────────────

function fmtCents(cents: number, currency = "USD") {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 0,
  }).format(cents / 100);
}

function fmtDate(iso: string | null | undefined) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

// ── Status badge ──────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  trialing: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  past_due: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  cancelled: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
};

function InvoiceStatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    paid: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    open: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
    void: "bg-muted text-muted-foreground",
    uncollectible: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium capitalize",
        colors[status] ?? colors.void,
      )}
    >
      {status}
    </span>
  );
}

// ── Usage meter ───────────────────────────────────────────────────────────

function UsageMeter({
  label,
  used,
  limit,
}: {
  label: string;
  used: number;
  limit: number;
}) {
  const unlimited = limit === -1;
  const pct = unlimited ? 0 : Math.min(100, Math.round((used / limit) * 100));
  const isWarn = !unlimited && pct >= 80;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className={cn("font-medium", isWarn && "text-amber-600 dark:text-amber-400")}>
          {unlimited ? `${used.toLocaleString()} / ∞` : `${used.toLocaleString()} / ${limit.toLocaleString()}`}
        </span>
      </div>
      {!unlimited && (
        <Progress
          value={pct}
          className={cn("h-1.5", isWarn && "[&>div]:bg-amber-500")}
        />
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function BillingPage() {
  // Source the org from the auth store (the legacy `paths_org` localStorage key
  // was never written, so reading it left oid empty — every billing query
  // (subscription, invoices, usage) stayed disabled and the page showed no data).
  const { user } = useAuthStore();
  const oid = user?.orgId ?? "";

  const { data: sub, isLoading: subLoading, refetch: refetchSub } = useOrgSubscription(oid);
  const { data: invoices = [], isLoading: invLoading } = useOrgInvoices(oid);
  const { data: usage, isLoading: usageLoading } = useUsage(oid);
  const { data: plans = [], isLoading: plansLoading } = usePublicPlans();
  const { mutateAsync: openPortal, isPending: openingPortal } = useCustomerPortalLink(oid);

  async function handlePortal() {
    try {
      await openPortal();
    } catch {
      toast.error("Could not open billing portal. Please try again.");
    }
  }

  const plan = sub?.plan;
  const limits: Record<string, number> = (plan?.limits as Record<string, number>) ?? {};

  const LIMIT_LABELS: Record<string, string> = {
    cvs_per_month: "CVs Processed",
    jobs_active: "Active Jobs",
    seats: "Seats Used",
    agent_runs_per_hour: "Agent Runs / hr",
  };

  return (
    <div className="flex flex-col gap-6 p-6 max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <CreditCard className="h-6 w-6 text-primary" />
          Billing & Subscription
        </h1>
        <p className="text-muted-foreground mt-1">
          Manage your plan, invoices, and usage limits.
        </p>
      </div>

      {/* ── Current plan card ─────────────────────────────────────────── */}
      <div className="rounded-xl border border-border bg-card p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            Current Plan
          </h3>
          <Button
            size="sm"
            variant="outline"
            className="gap-1.5 text-xs"
            onClick={handlePortal}
            disabled={openingPortal || !sub?.plan}
          >
            {openingPortal ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <ExternalLink className="h-3.5 w-3.5" />
            )}
            Manage in Stripe
          </Button>
        </div>

        {subLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-48 rounded-lg" />
            <Skeleton className="h-4 w-32 rounded" />
          </div>
        ) : sub?.plan ? (
          <div className="flex flex-wrap items-center gap-4">
            <div>
              <p className="text-3xl font-bold">{sub.plan.name}</p>
              <p className="text-xs text-muted-foreground mt-0.5 capitalize">
                {sub.billing_cycle} billing
              </p>
            </div>
            <span
              className={cn(
                "inline-flex items-center rounded-full px-3 py-1 text-xs font-medium capitalize",
                STATUS_COLORS[sub.status] ?? "text-muted-foreground",
              )}
            >
              {sub.status}
            </span>
            {sub.cancel_at_period_end && (
              <Badge variant="outline" className="text-[10px] text-destructive border-destructive/30">
                Cancels {fmtDate(sub.current_period_end)}
              </Badge>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <AlertCircle className="h-4 w-4" />
            No active subscription.{" "}
            <a href="/pricing" className="underline text-primary">
              Pick a plan
            </a>
          </div>
        )}

        {sub && (
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="rounded-lg bg-muted/30 px-3 py-2">
              <p className="text-muted-foreground">Period start</p>
              <p className="font-medium">{fmtDate(sub.current_period_start)}</p>
            </div>
            <div className="rounded-lg bg-muted/30 px-3 py-2">
              <p className="text-muted-foreground">Period end</p>
              <p className="font-medium">{fmtDate(sub.current_period_end)}</p>
            </div>
          </div>
        )}
      </div>

      {/* ── Usage meters ─────────────────────────────────────────────── */}
      <div className="rounded-xl border border-border bg-card p-5 space-y-4">
        <h3 className="font-semibold flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-primary" />
          Usage This Period
        </h3>

        {usageLoading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-6 w-full rounded" />
            ))}
          </div>
        ) : usage ? (
          <div className="space-y-3">
            <UsageMeter
              label={LIMIT_LABELS.cvs_per_month ?? "CVs Processed"}
              used={usage.cvs_processed}
              limit={limits.cvs_per_month ?? -1}
            />
            <UsageMeter
              label={LIMIT_LABELS.jobs_active ?? "Active Jobs"}
              used={usage.jobs_active}
              limit={limits.jobs_active ?? -1}
            />
            <UsageMeter
              label={LIMIT_LABELS.seats ?? "Seats"}
              used={usage.seats_used}
              limit={limits.seats ?? -1}
            />
            <UsageMeter
              label="Agent Runs"
              used={usage.agent_runs}
              limit={limits.agent_runs_per_hour ?? -1}
            />
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No usage data available.</p>
        )}
      </div>

      {/* ── Upgrade strip ──────────────────────────────────────────────── */}
      {plans.length > 0 && sub?.plan && (
        <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-semibold">Want more power?</p>
            <p className="text-xs text-muted-foreground">
              Compare plans and upgrade instantly.
            </p>
          </div>
          <a href="/pricing">
            <Button size="sm" className="gap-1.5 text-xs">
              <Zap className="h-3.5 w-3.5" />
              View Plans
              <ArrowUpRight className="h-3.5 w-3.5" />
            </Button>
          </a>
        </div>
      )}

      <Separator />

      {/* ── Invoices ──────────────────────────────────────────────────── */}
      <div className="space-y-3">
        <h3 className="font-semibold flex items-center gap-2">
          <FileText className="h-4 w-4 text-primary" />
          Invoices
        </h3>

        {invLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-12 w-full rounded-lg" />
            ))}
          </div>
        ) : invoices.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">
            No invoices yet.
          </p>
        ) : (
          <div className="rounded-xl border border-border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/30 text-xs text-muted-foreground">
                <tr>
                  <th className="text-left px-4 py-2">Date</th>
                  <th className="text-left px-4 py-2">Period</th>
                  <th className="text-right px-4 py-2">Amount</th>
                  <th className="text-center px-4 py-2">Status</th>
                  <th className="text-right px-4 py-2">PDF</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv, i) => (
                  <tr
                    key={inv.id}
                    className={cn(
                      "border-t border-border/50",
                      i % 2 === 0 ? "bg-card" : "bg-muted/10",
                    )}
                  >
                    <td className="px-4 py-3 text-xs">{fmtDate(inv.paid_at)}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {fmtDate(inv.period_start)} – {fmtDate(inv.period_end)}
                    </td>
                    <td className="px-4 py-3 text-right font-medium">
                      {fmtCents(inv.amount_cents, inv.currency)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <InvoiceStatusBadge status={inv.status} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      {inv.pdf_url ? (
                        <a
                          href={inv.pdf_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-primary hover:underline text-xs inline-flex items-center gap-0.5"
                        >
                          PDF <ExternalLink className="h-2.5 w-2.5" />
                        </a>
                      ) : (
                        <span className="text-muted-foreground text-xs">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

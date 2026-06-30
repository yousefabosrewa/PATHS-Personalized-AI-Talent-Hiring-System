"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Activity, Building2, CheckCircle2, ClockAlert, FileSearch, ShieldCheck, Users, XCircle,
} from "lucide-react";
import { platformAdminApi, type AdminDashboardStats, type AdminOrgRequestRow } from "@/lib/api/platform-admin.api";

function StatCard({
  icon: Icon, label, value, sub,
}: { icon: React.ComponentType<{ className?: string }>; label: string; value: number | string; sub?: string }) {
  return (
    <div className="rounded-xl border border-border/50 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        <Icon className="h-4 w-4 text-primary" />
        {label}
      </div>
      <p className="font-heading text-3xl font-bold text-foreground">{value}</p>
      {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

export default function AdminOverviewPage() {
  const [stats, setStats] = useState<AdminDashboardStats | null>(null);
  const [pending, setPending] = useState<AdminOrgRequestRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const [s, p] = await Promise.all([
          platformAdminApi.dashboardStats(),
          platformAdminApi.listRequests({ status: "pending", limit: 8 }),
        ]);
        if (!mounted) return;
        setStats(s);
        setPending(p);
      } catch (err) {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : "Failed to load");
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, []);

  return (
    <div className="mx-auto max-w-6xl px-8 py-10">
      <div className="mb-8">
        <h1 className="font-heading text-3xl font-bold">Platform Admin</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Approve company access, monitor activity, and manage the platform.
        </p>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {loading ? (
        <div className="rounded-xl border border-border/40 bg-muted/20 p-8 text-center text-sm text-muted-foreground">
          Loading platform stats…
        </div>
      ) : stats && (
        <>
          <div className="mb-8 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <StatCard icon={ClockAlert}  label="Pending Requests"  value={stats.pending_requests}   sub="Awaiting decision" />
            <StatCard icon={CheckCircle2} label="Approved Companies" value={stats.approved_requests} sub="All-time" />
            <StatCard icon={XCircle}     label="Rejected Requests"  value={stats.rejected_requests} sub="All-time" />
            <StatCard icon={Building2}   label="Active Orgs"        value={stats.active_organizations} sub={`${stats.suspended_organizations} suspended`} />
          </div>
          <div className="mb-8 grid gap-4 md:grid-cols-3">
            <StatCard icon={Users}        label="Candidates"         value={stats.candidates} />
            <StatCard icon={Building2}    label="Organisation members" value={stats.organization_members} />
            <StatCard icon={ShieldCheck}  label="Platform admins"     value={stats.platform_admins} />
          </div>
        </>
      )}

      <div className="rounded-xl border border-border/50 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-border/40 p-5">
          <div>
            <h2 className="font-heading text-lg font-semibold">Pending access requests</h2>
            <p className="text-xs text-muted-foreground">Most recent first.</p>
          </div>
          <Link href="/admin/organization-requests" className="text-sm font-medium text-primary hover:underline">
            View all
          </Link>
        </div>
        <div className="divide-y divide-border/30">
          {pending.length === 0 ? (
            <p className="p-5 text-sm text-muted-foreground">No pending requests. ✓</p>
          ) : (
            pending.map((r) => (
              <Link
                key={r.id}
                href={`/admin/organization-requests/${r.id}`}
                className="flex items-center justify-between gap-4 p-4 transition-colors hover:bg-muted/30"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-foreground">{r.organization_name}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {r.requester_name} · {r.requester_email}
                    {r.contact_role ? ` · ${r.contact_role}` : ""}
                  </p>
                </div>
                <span className="flex items-center gap-1 rounded-full border border-amber-300/70 bg-amber-50 px-2.5 py-1 text-[11px] font-medium text-amber-700">
                  <FileSearch className="h-3 w-3" />
                  Review
                </span>
              </Link>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

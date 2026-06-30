"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CheckCircle2, ClockAlert, XCircle } from "lucide-react";
import { platformAdminApi, type AdminOrgRequestRow } from "@/lib/api/platform-admin.api";
import { cn } from "@/lib/utils/cn";

const STATUS_TABS = [
  { value: "pending",  label: "Pending",  icon: ClockAlert,   color: "text-amber-600 border-amber-300/70 bg-amber-50" },
  { value: "approved", label: "Approved", icon: CheckCircle2, color: "text-emerald-600 border-emerald-300/70 bg-emerald-50" },
  { value: "rejected", label: "Rejected", icon: XCircle,      color: "text-rose-600 border-rose-300/70 bg-rose-50" },
];

export default function OrgRequestsListPage() {
  const [active, setActive] = useState("pending");
  const [rows, setRows] = useState<AdminOrgRequestRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await platformAdminApi.listRequests({ status: active, limit: 100 });
        if (!mounted) return;
        setRows(data);
      } catch (err) {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : "Failed to load");
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, [active]);

  return (
    <div className="mx-auto max-w-6xl px-8 py-10">
      <div className="mb-8">
        <h1 className="font-heading text-3xl font-bold">Company access requests</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Review companies that requested platform access and approve or reject each.
        </p>
      </div>

      <div className="mb-5 flex gap-2">
        {STATUS_TABS.map((t) => {
          const isActive = active === t.value;
          const Icon = t.icon;
          return (
            <button
              key={t.value}
              onClick={() => setActive(t.value)}
              className={cn(
                "flex items-center gap-2 rounded-full border px-4 py-1.5 text-sm font-medium transition-colors",
                isActive
                  ? t.color
                  : "border-border/50 text-muted-foreground hover:border-border hover:text-foreground",
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              {t.label}
            </button>
          );
        })}
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="rounded-xl border border-border/50 bg-white shadow-sm">
        {loading ? (
          <p className="p-6 text-sm text-muted-foreground">Loading…</p>
        ) : rows.length === 0 ? (
          <p className="p-6 text-sm text-muted-foreground">No {active} requests.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/40 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <th className="px-5 py-3">Company</th>
                <th className="px-5 py-3">Requester</th>
                <th className="px-5 py-3">Role</th>
                <th className="px-5 py-3">Submitted</th>
                <th className="px-5 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-border/30 last:border-0 hover:bg-muted/20">
                  <td className="px-5 py-3">
                    <p className="font-medium text-foreground">{r.organization_name}</p>
                    <p className="text-xs text-muted-foreground">{r.organization_slug}</p>
                  </td>
                  <td className="px-5 py-3">
                    <p className="text-foreground">{r.requester_name}</p>
                    <p className="text-xs text-muted-foreground">{r.requester_email}</p>
                  </td>
                  <td className="px-5 py-3 text-muted-foreground">{r.contact_role ?? "—"}</td>
                  <td className="px-5 py-3 text-xs text-muted-foreground">
                    {new Date(r.submitted_at).toLocaleString()}
                  </td>
                  <td className="px-5 py-3 text-right">
                    <Link
                      href={`/admin/organization-requests/${r.id}`}
                      className="inline-flex rounded-md border border-border bg-white px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted/40"
                    >
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

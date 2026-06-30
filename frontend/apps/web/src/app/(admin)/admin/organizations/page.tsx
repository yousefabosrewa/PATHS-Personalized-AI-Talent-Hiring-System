"use client";

import { useEffect, useState } from "react";
import { Building2, Loader2, Pause, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { platformAdminApi, type AdminOrgRow } from "@/lib/api/platform-admin.api";
import { cn } from "@/lib/utils/cn";

const STATUS_FILTERS = [
  { value: "",                 label: "All" },
  { value: "active",           label: "Active" },
  { value: "pending_approval", label: "Pending" },
  { value: "rejected",         label: "Rejected" },
  { value: "suspended",        label: "Suspended" },
];

const STATUS_STYLE: Record<AdminOrgRow["status"], string> = {
  active:           "border-emerald-300/70 bg-emerald-50 text-emerald-700",
  pending_approval: "border-amber-300/70 bg-amber-50 text-amber-700",
  rejected:         "border-rose-300/70 bg-rose-50 text-rose-700",
  suspended:        "border-slate-300/70 bg-slate-50 text-slate-700",
};

export default function AdminOrganizationsPage() {
  const [filter, setFilter] = useState("");
  const [rows, setRows] = useState<AdminOrgRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await platformAdminApi.listOrganizations(
        filter ? { status: filter } : undefined,
      );
      setRows(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await platformAdminApi.listOrganizations(
          filter ? { status: filter } : undefined,
        );
        setRows(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load");
      } finally {
        setLoading(false);
      }
    })();
  }, [filter]);

  const onSuspend = async (org: AdminOrgRow) => {
    const reason = window.prompt(`Suspend "${org.name}"? Enter reason:`);
    if (!reason || reason.trim().length < 3) return;
    setBusyId(org.id);
    try {
      await platformAdminApi.suspendOrganization(org.id, reason.trim());
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Suspension failed");
    } finally {
      setBusyId(null);
    }
  };

  const onUnsuspend = async (org: AdminOrgRow) => {
    if (!window.confirm(`Re-activate "${org.name}"?`)) return;
    setBusyId(org.id);
    try {
      await platformAdminApi.unsuspendOrganization(org.id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unsuspension failed");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="mx-auto max-w-6xl px-8 py-10">
      <div className="mb-8">
        <h1 className="font-heading text-3xl font-bold">Organisations</h1>
        <p className="mt-1 text-sm text-muted-foreground">All companies on the platform.</p>
      </div>

      <div className="mb-5 flex flex-wrap gap-2">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={cn(
              "rounded-full border px-4 py-1.5 text-sm font-medium transition-colors",
              filter === f.value
                ? "border-primary/50 bg-primary/10 text-primary"
                : "border-border/50 text-muted-foreground hover:border-border hover:text-foreground",
            )}
          >
            {f.label}
          </button>
        ))}
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
          <p className="p-6 text-sm text-muted-foreground">No organisations match this filter.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/40 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <th className="px-5 py-3">Organisation</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Members</th>
                <th className="px-5 py-3">Created</th>
                <th className="px-5 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-border/30 last:border-0 hover:bg-muted/20">
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <Building2 className="h-4 w-4 text-muted-foreground" />
                      <div>
                        <p className="font-medium text-foreground">{r.name}</p>
                        <p className="text-xs text-muted-foreground">{r.slug}{r.contact_email ? ` · ${r.contact_email}` : ""}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-3">
                    <span className={cn("inline-flex rounded-full border px-2.5 py-0.5 text-[11px] font-semibold", STATUS_STYLE[r.status])}>
                      {r.status.replace("_", " ")}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-muted-foreground">{r.member_count}</td>
                  <td className="px-5 py-3 text-xs text-muted-foreground">
                    {new Date(r.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-5 py-3 text-right">
                    {r.status === "active" && (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="border-rose-200 text-rose-600 hover:bg-rose-50"
                        onClick={() => onSuspend(r)}
                        disabled={busyId === r.id}
                      >
                        {busyId === r.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <><Pause className="mr-1 h-3.5 w-3.5" /> Suspend</>}
                      </Button>
                    )}
                    {r.status === "suspended" && (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="border-emerald-200 text-emerald-600 hover:bg-emerald-50"
                        onClick={() => onUnsuspend(r)}
                        disabled={busyId === r.id}
                      >
                        {busyId === r.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <><Play className="mr-1 h-3.5 w-3.5" /> Re-activate</>}
                      </Button>
                    )}
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

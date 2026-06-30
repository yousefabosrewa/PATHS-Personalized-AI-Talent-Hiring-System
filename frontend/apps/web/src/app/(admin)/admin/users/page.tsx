"use client";

import { useEffect, useState } from "react";
import { platformAdminApi, type AdminUserRow } from "@/lib/api/platform-admin.api";
import { cn } from "@/lib/utils/cn";

const TABS = [
  { value: "",                    label: "All" },
  { value: "candidate",           label: "Candidates" },
  { value: "organization_member", label: "Org members" },
  { value: "platform_admin",      label: "Platform admins" },
];

const TYPE_STYLE: Record<string, string> = {
  candidate:           "border-sky-200 bg-sky-50 text-sky-700",
  organization_member: "border-violet-200 bg-violet-50 text-violet-700",
  platform_admin:      "border-amber-200 bg-amber-50 text-amber-700",
};

export default function AdminUsersPage() {
  const [filter, setFilter] = useState("");
  const [rows, setRows] = useState<AdminUserRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await platformAdminApi.listUsers(
          filter ? { account_type: filter, limit: 200 } : { limit: 200 },
        );
        if (mounted) setRows(data);
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : "Failed to load");
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, [filter]);

  return (
    <div className="mx-auto max-w-6xl px-8 py-10">
      <div className="mb-8">
        <h1 className="font-heading text-3xl font-bold">Users</h1>
        <p className="mt-1 text-sm text-muted-foreground">Every account on the platform.</p>
      </div>

      <div className="mb-5 flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button
            key={t.value}
            onClick={() => setFilter(t.value)}
            className={cn(
              "rounded-full border px-4 py-1.5 text-sm font-medium transition-colors",
              filter === t.value
                ? "border-primary/50 bg-primary/10 text-primary"
                : "border-border/50 text-muted-foreground hover:border-border hover:text-foreground",
            )}
          >
            {t.label}
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
          <p className="p-6 text-sm text-muted-foreground">No users match this filter.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/40 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <th className="px-5 py-3">Name</th>
                <th className="px-5 py-3">Email</th>
                <th className="px-5 py-3">Type</th>
                <th className="px-5 py-3">Active</th>
                <th className="px-5 py-3">Joined</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-border/30 last:border-0 hover:bg-muted/20">
                  <td className="px-5 py-3 font-medium text-foreground">{r.full_name}</td>
                  <td className="px-5 py-3 text-muted-foreground">{r.email}</td>
                  <td className="px-5 py-3">
                    <span className={cn(
                      "inline-flex rounded-full border px-2.5 py-0.5 text-[11px] font-semibold",
                      TYPE_STYLE[r.account_type] ?? "border-slate-200 bg-slate-50 text-slate-700",
                    )}>
                      {r.account_type.replace("_", " ")}
                    </span>
                  </td>
                  <td className="px-5 py-3">
                    {r.is_active ? (
                      <span className="text-emerald-600">●</span>
                    ) : (
                      <span className="text-muted-foreground">○</span>
                    )}
                  </td>
                  <td className="px-5 py-3 text-xs text-muted-foreground">
                    {new Date(r.created_at).toLocaleDateString()}
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

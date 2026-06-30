"use client";

import { useState } from "react";
import { Search } from "lucide-react";
import { useOwnerOrgs } from "@/lib/hooks";

const STATUS_BADGE: Record<string, string> = {
  active: "bg-green-100 text-green-700",
  pending_approval: "bg-amber-100 text-amber-700",
  suspended: "bg-red-100 text-red-700",
  rejected: "bg-gray-100 text-gray-600",
};

export default function OwnerOrgsPage() {
  const [q, setQ] = useState("");
  const [planFilter, setPlanFilter] = useState("");

  const { data: orgs = [], isLoading } = useOwnerOrgs({
    q: q || undefined,
    plan: planFilter || undefined,
  });

  return (
    <div className="mx-auto max-w-5xl px-8 py-10 space-y-6">
      <div>
        <h1 className="font-heading text-3xl font-bold">All Organisations</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Owner-level view of every org on the platform.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-56">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search by name…"
            className="w-full rounded-lg border border-border/50 pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>
        <span className="text-xs text-muted-foreground">{orgs.length} results</span>
      </div>

      <div className="rounded-xl border border-border/50 bg-white shadow-sm overflow-hidden">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-muted-foreground">Loading…</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/30 bg-muted/20 text-xs font-semibold uppercase text-muted-foreground">
                <th className="px-5 py-3 text-left">Organisation</th>
                <th className="px-5 py-3 text-left">Slug</th>
                <th className="px-5 py-3 text-left">Status</th>
                <th className="px-5 py-3 text-left">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/20">
              {orgs.map((org) => (
                <tr key={org.id} className="hover:bg-muted/10">
                  <td className="px-5 py-3 font-medium">{org.name}</td>
                  <td className="px-5 py-3 font-mono text-xs text-muted-foreground">
                    {org.slug}
                  </td>
                  <td className="px-5 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                        STATUS_BADGE[org.status] ?? "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {org.status}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-xs text-muted-foreground">
                    {org.created_at
                      ? new Date(org.created_at).toLocaleDateString()
                      : "—"}
                  </td>
                </tr>
              ))}
              {orgs.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-10 text-center text-muted-foreground">
                    No organisations found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

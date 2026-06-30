"use client";

import { useState } from "react";
import { Users, Filter } from "lucide-react";
import { useOwnerCustomers } from "@/lib/hooks";

const HEALTH_BG = (score: number) =>
  score >= 70
    ? "bg-green-100 text-green-700"
    : score >= 40
    ? "bg-amber-100 text-amber-700"
    : "bg-red-100 text-red-600";

export default function OwnerCustomersPage() {
  const [healthFilter, setHealthFilter] = useState("");
  const [planFilter, setPlanFilter] = useState("");

  const { data: customers = [], isLoading } = useOwnerCustomers({
    health: healthFilter || undefined,
    plan: planFilter || undefined,
  });

  return (
    <div className="mx-auto max-w-6xl px-8 py-10 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-heading text-3xl font-bold">Customer Analytics</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Health scores and plan info for every organisation.
          </p>
        </div>
        <span className="rounded-full bg-muted px-3 py-1 text-sm font-medium text-muted-foreground">
          {customers.length} orgs
        </span>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <Filter className="h-4 w-4 text-muted-foreground" />
        <select
          value={healthFilter}
          onChange={(e) => setHealthFilter(e.target.value)}
          className="rounded-lg border border-border/50 bg-white px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
        >
          <option value="">All health</option>
          <option value="at_risk">At risk (&lt;40)</option>
        </select>
        <select
          value={planFilter}
          onChange={(e) => setPlanFilter(e.target.value)}
          className="rounded-lg border border-border/50 bg-white px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
        >
          <option value="">All plans</option>
          <option value="starter">Starter</option>
          <option value="growth">Growth</option>
          <option value="enterprise">Enterprise</option>
        </select>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-border/50 bg-white shadow-sm overflow-hidden">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-muted-foreground">Loading…</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/30 bg-muted/20 text-xs font-semibold uppercase text-muted-foreground">
                  <th className="px-5 py-3 text-left">Organisation</th>
                  <th className="px-5 py-3 text-left">Plan</th>
                  <th className="px-5 py-3 text-left">Status</th>
                  <th className="px-5 py-3 text-left">Health</th>
                  <th className="px-5 py-3 text-left">Joined</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/20">
                {customers.map((c) => (
                  <tr key={c.org_id} className="hover:bg-muted/10">
                    <td className="px-5 py-3">
                      <p className="font-medium">{c.name}</p>
                      <code className="text-xs text-muted-foreground">
                        {c.org_id.slice(0, 8)}…
                      </code>
                    </td>
                    <td className="px-5 py-3">
                      <span className="capitalize font-medium">
                        {c.plan ?? "Free"}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <span className="rounded-full border border-border/40 px-2 py-0.5 text-xs capitalize">
                        {c.status}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-semibold ${HEALTH_BG(
                          c.health_score,
                        )}`}
                      >
                        {c.health_score}/100
                      </span>
                    </td>
                    <td className="px-5 py-3 text-xs text-muted-foreground">
                      {c.created_at ? new Date(c.created_at).toLocaleDateString() : "—"}
                    </td>
                  </tr>
                ))}
                {customers.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-10 text-center text-muted-foreground">
                      No customers found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

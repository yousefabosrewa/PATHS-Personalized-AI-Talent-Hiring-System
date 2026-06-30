"use client";

import { useState } from "react";
import { RefreshCw, RotateCcw, Filter } from "lucide-react";
import { useAdminAgentRuns, useRetryAgentRun } from "@/lib/hooks";
import type { AdminAgentRun } from "@/lib/api/platform-admin.api";

const STATUS_BADGE: Record<string, string> = {
  queued: "bg-blue-100 text-blue-700",
  running: "bg-amber-100 text-amber-700",
  completed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  cancelled: "bg-gray-100 text-gray-600",
};

export default function AdminAgentsPage() {
  const [statusFilter, setStatusFilter] = useState("");
  const [runTypeFilter, setRunTypeFilter] = useState("");

  const { data: runs = [], isLoading, refetch } = useAdminAgentRuns({
    status: statusFilter || undefined,
    run_type: runTypeFilter || undefined,
    limit: 100,
  });

  const retry = useRetryAgentRun();

  const handleRetry = async (id: string) => {
    try {
      await retry.mutateAsync(id);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Retry failed");
    }
  };

  const runTypes = Array.from(new Set(runs.map((r) => r.run_type))).sort();

  return (
    <div className="mx-auto max-w-6xl px-8 py-10 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-heading text-3xl font-bold">Agent Monitor</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Cross-org agent runs — real-time status across all pipelines.
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-1.5 rounded-lg border border-border/50 px-3 py-1.5 text-sm hover:bg-muted/30"
        >
          <RefreshCw className="h-3.5 w-3.5" /> Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <Filter className="h-4 w-4 text-muted-foreground" />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-border/50 bg-white px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
        >
          <option value="">All statuses</option>
          <option value="queued">Queued</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="cancelled">Cancelled</option>
        </select>
        <select
          value={runTypeFilter}
          onChange={(e) => setRunTypeFilter(e.target.value)}
          className="rounded-lg border border-border/50 bg-white px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
        >
          <option value="">All types</option>
          {runTypes.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <span className="ml-auto text-xs text-muted-foreground">{runs.length} runs</span>
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
                  <th className="px-4 py-3 text-left">Type</th>
                  <th className="px-4 py-3 text-left">Status</th>
                  <th className="px-4 py-3 text-left">Org</th>
                  <th className="px-4 py-3 text-left">Entity</th>
                  <th className="px-4 py-3 text-left">Node</th>
                  <th className="px-4 py-3 text-left">Started</th>
                  <th className="px-4 py-3 text-left">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/20">
                {runs.map((run) => (
                  <tr key={run.id} className="hover:bg-muted/10">
                    <td className="px-4 py-3 font-mono text-xs">{run.run_type}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                          STATUS_BADGE[run.status] ?? "bg-gray-100 text-gray-600"
                        }`}
                      >
                        {run.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground font-mono">
                      {run.organization_id.slice(0, 8)}…
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {run.entity_type ? `${run.entity_type}` : "—"}
                      {run.entity_id ? (
                        <span className="ml-1 font-mono">{run.entity_id.slice(0, 6)}…</span>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {run.current_node ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {run.started_at ? new Date(run.started_at).toLocaleString() : "—"}
                    </td>
                    <td className="px-4 py-3">
                      {(run.status === "failed" || run.status === "cancelled") && (
                        <button
                          onClick={() => handleRetry(run.id)}
                          disabled={retry.isPending}
                          title="Retry"
                          className="flex items-center gap-1 rounded-md border border-primary/40 px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10 disabled:opacity-50"
                        >
                          <RotateCcw className="h-3 w-3" /> Retry
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {runs.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-10 text-center text-muted-foreground">
                      No agent runs found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>

            {/* Error log panel for failed runs */}
            {runs.filter((r) => r.status === "failed" && r.error).length > 0 && (
              <div className="border-t border-border/30 p-4">
                <h3 className="mb-3 text-sm font-semibold text-destructive">
                  Error Log — Failed Runs
                </h3>
                <div className="space-y-2">
                  {runs
                    .filter((r) => r.status === "failed" && r.error)
                    .slice(0, 5)
                    .map((r) => (
                      <div
                        key={r.id}
                        className="rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-xs"
                      >
                        <p className="mb-1 font-mono font-semibold text-destructive">
                          {r.run_type} — {r.id.slice(0, 8)}
                        </p>
                        <pre className="whitespace-pre-wrap text-muted-foreground">
                          {r.error}
                        </pre>
                      </div>
                    ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

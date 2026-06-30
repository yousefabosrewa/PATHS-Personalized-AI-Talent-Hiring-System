"use client";

import { RefreshCw, CheckCircle2, XCircle, AlertTriangle } from "lucide-react";
import { useAdminSystemHealth } from "@/lib/hooks";

function ServiceRow({
  name,
  data,
}: {
  name: string;
  data: Record<string, unknown> | undefined;
}) {
  const status = (data?.status as string) ?? "unknown";
  const isHealthy = status === "healthy";
  const isUnreachable = status === "unreachable";

  return (
    <div className="flex items-center justify-between rounded-xl border border-border/50 bg-white p-4 shadow-sm">
      <div>
        <p className="font-semibold capitalize">{name}</p>
        {data && Object.keys(data).length > 1 && (
          <p className="mt-0.5 text-xs text-muted-foreground">
            {Object.entries(data)
              .filter(([k]) => k !== "status")
              .map(([k, v]) => `${k}: ${v}`)
              .join(" · ")}
          </p>
        )}
      </div>
      <div className="flex items-center gap-1.5">
        {isHealthy ? (
          <CheckCircle2 className="h-5 w-5 text-green-500" />
        ) : isUnreachable ? (
          <XCircle className="h-5 w-5 text-red-500" />
        ) : (
          <AlertTriangle className="h-5 w-5 text-amber-500" />
        )}
        <span
          className={`text-sm font-semibold ${
            isHealthy
              ? "text-green-600"
              : isUnreachable
              ? "text-red-600"
              : "text-amber-600"
          }`}
        >
          {status}
        </span>
      </div>
    </div>
  );
}

export default function AdminSystemPage() {
  const { data: health, isLoading, refetch } = useAdminSystemHealth();

  return (
    <div className="mx-auto max-w-3xl px-8 py-10 space-y-8">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-heading text-3xl font-bold">System Health</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Live probes — refreshes every 30 seconds automatically.
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-1.5 rounded-lg border border-border/50 px-3 py-1.5 text-sm hover:bg-muted/30"
        >
          <RefreshCw className="h-3.5 w-3.5" /> Refresh
        </button>
      </div>

      {isLoading ? (
        <div className="rounded-xl border border-border/40 bg-muted/20 p-8 text-center text-sm text-muted-foreground">
          Probing services…
        </div>
      ) : health ? (
        <>
          {/* Overall banner */}
          <div
            className={`rounded-xl border p-4 text-center font-semibold ${
              health.overall === "healthy"
                ? "border-green-300 bg-green-50 text-green-700"
                : "border-amber-300 bg-amber-50 text-amber-700"
            }`}
          >
            {health.overall === "healthy"
              ? "✓ All systems operational"
              : "⚠ One or more services degraded"}
          </div>

          {/* Service cards */}
          <div className="grid gap-3 sm:grid-cols-2">
            <ServiceRow name="PostgreSQL" data={health.services.postgres as Record<string, unknown>} />
            <ServiceRow name="Apache AGE" data={health.services.apache_age as Record<string, unknown>} />
            <ServiceRow name="Qdrant" data={health.services.qdrant as Record<string, unknown>} />
            <ServiceRow name="Ollama / LLM" data={health.services.ollama as Record<string, unknown>} />
          </div>

          {/* Agent error rate */}
          <div className="rounded-xl border border-border/50 bg-white p-5 shadow-sm">
            <p className="mb-1 text-xs font-semibold uppercase text-muted-foreground">
              Agent failures (last 24 h)
            </p>
            <p
              className={`text-3xl font-bold ${
                health.agent_runs_failed_24h > 0 ? "text-red-600" : "text-green-600"
              }`}
            >
              {health.agent_runs_failed_24h}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Last checked: {new Date(health.checked_at).toLocaleString()}
            </p>
          </div>
        </>
      ) : (
        <p className="text-sm text-destructive">Failed to load health data.</p>
      )}
    </div>
  );
}

"use client";

/**
 * Status Page — client-side component
 *
 * Polls /api/v1/health/databases every 30 s and renders service status cards.
 * Also checks the Next.js frontend itself (always "operational" if this page loads).
 */

import { useEffect, useState } from "react";
import { CheckCircle, XCircle, AlertCircle, RefreshCw, Clock } from "lucide-react";

type ServiceStatus = "operational" | "degraded" | "down" | "unknown";

interface ServiceCard {
  name: string;
  description: string;
  status: ServiceStatus;
  latencyMs?: number;
}

interface HealthResponse {
  postgres?: { status: string };
  age?:      { status: string };
  qdrant?:   { status: string };
  ollama?:   { status: string };
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";
const POLL_INTERVAL_MS = 30_000;

function toStatus(raw: string | undefined): ServiceStatus {
  if (!raw) return "unknown";
  if (raw === "healthy") return "operational";
  if (raw === "unhealthy" || raw === "error") return "down";
  return "degraded";
}

function StatusIcon({ status }: { status: ServiceStatus }) {
  if (status === "operational")
    return <CheckCircle className="h-5 w-5 text-green-500" />;
  if (status === "degraded")
    return <AlertCircle className="h-5 w-5 text-amber-500" />;
  if (status === "down")
    return <XCircle className="h-5 w-5 text-red-500" />;
  return <Clock className="h-5 w-5 text-muted-foreground animate-pulse" />;
}

function statusLabel(s: ServiceStatus) {
  return { operational: "Operational", degraded: "Degraded", down: "Down", unknown: "Checking…" }[s];
}

function statusColor(s: ServiceStatus) {
  return {
    operational: "text-green-600 bg-green-50 border-green-200",
    degraded:    "text-amber-600 bg-amber-50 border-amber-200",
    down:        "text-red-600 bg-red-50 border-red-200",
    unknown:     "text-muted-foreground bg-muted/10 border-border/40",
  }[s];
}

function overallBanner(services: ServiceCard[]) {
  if (services.some((s) => s.status === "down"))
    return { label: "Major outage", color: "bg-red-50 border-red-300 text-red-800" };
  if (services.some((s) => s.status === "degraded"))
    return { label: "Partial outage", color: "bg-amber-50 border-amber-300 text-amber-800" };
  if (services.some((s) => s.status === "unknown"))
    return { label: "Checking status…", color: "bg-muted/10 border-border/40 text-muted-foreground" };
  return { label: "All systems operational", color: "bg-green-50 border-green-300 text-green-800" };
}

export function StatusPageClient() {
  const [services, setServices] = useState<ServiceCard[]>([
    { name: "Frontend",      description: "Next.js web application",        status: "operational" },
    { name: "API",           description: "FastAPI backend",                 status: "unknown" },
    { name: "Database",      description: "PostgreSQL + Apache AGE",         status: "unknown" },
    { name: "Vector search", description: "Qdrant embedding store",          status: "unknown" },
    { name: "LLM inference", description: "OpenRouter / local Ollama",       status: "unknown" },
  ]);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [checking, setChecking] = useState(false);

  async function checkHealth() {
    setChecking(true);
    const t0 = performance.now();
    try {
      const res = await fetch(`${API_URL}/api/v1/health/databases`, {
        cache: "no-store",
        signal: AbortSignal.timeout(8000),
      });
      const latencyMs = Math.round(performance.now() - t0);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: HealthResponse = await res.json();

      setServices([
        { name: "Frontend",      description: "Next.js web application",   status: "operational" },
        { name: "API",           description: "FastAPI backend",            status: "operational", latencyMs },
        { name: "Database",      description: "PostgreSQL + Apache AGE",   status: toStatus(data.postgres?.status ?? data.age?.status) },
        { name: "Vector search", description: "Qdrant embedding store",    status: toStatus(data.qdrant?.status) },
        { name: "LLM inference", description: "OpenRouter / local Ollama", status: toStatus(data.ollama?.status) },
      ]);
    } catch {
      const latencyMs = Math.round(performance.now() - t0);
      setServices((prev) => prev.map((s) =>
        s.name === "Frontend" ? s : { ...s, status: "down", latencyMs }
      ));
    } finally {
      setLastChecked(new Date());
      setChecking(false);
    }
  }

  useEffect(() => {
    checkHealth();
    const id = setInterval(checkHealth, POLL_INTERVAL_MS);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const banner = overallBanner(services);

  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      {/* Header */}
      <div className="mb-10 flex items-start justify-between">
        <div>
          <h1 className="font-heading text-4xl font-bold mb-2">Platform Status</h1>
          {lastChecked ? (
            <p className="text-sm text-muted-foreground">
              Last checked: {lastChecked.toLocaleTimeString()} · auto-refreshes every 30 s
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">Checking…</p>
          )}
        </div>
        <button
          onClick={checkHealth}
          disabled={checking}
          className="flex items-center gap-1.5 rounded-lg border border-border/50 px-3 py-1.5 text-xs font-medium hover:bg-muted/30 disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${checking ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Overall status banner */}
      <div className={`mb-8 rounded-xl border px-5 py-4 font-medium ${banner.color}`}>
        {banner.label}
      </div>

      {/* Service cards */}
      <div className="space-y-3">
        {services.map((svc) => (
          <div
            key={svc.name}
            className="flex items-center justify-between rounded-xl border border-border/40 bg-white px-5 py-4 shadow-sm"
          >
            <div className="flex items-center gap-3">
              <StatusIcon status={svc.status} />
              <div>
                <p className="text-sm font-semibold">{svc.name}</p>
                <p className="text-xs text-muted-foreground">{svc.description}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              {svc.latencyMs !== undefined && (
                <span className="text-xs text-muted-foreground">{svc.latencyMs} ms</span>
              )}
              <span className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${statusColor(svc.status)}`}>
                {statusLabel(svc.status)}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Incident history placeholder */}
      <div className="mt-12">
        <h2 className="text-lg font-semibold mb-4">Recent incidents</h2>
        <div className="rounded-xl border border-border/40 bg-muted/5 px-5 py-8 text-center">
          <CheckCircle className="mx-auto h-8 w-8 text-green-400 mb-2" />
          <p className="text-sm text-muted-foreground">No incidents in the last 90 days.</p>
        </div>
      </div>

      {/* Footer */}
      <div className="mt-10 text-center text-xs text-muted-foreground">
        Subscribe to updates at{" "}
        <a href="mailto:support@paths.ai" className="text-primary hover:underline">
          support@paths.ai
        </a>
      </div>
    </div>
  );
}

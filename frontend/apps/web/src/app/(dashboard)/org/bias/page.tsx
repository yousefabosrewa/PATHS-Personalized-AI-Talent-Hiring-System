"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  ShieldCheck, AlertTriangle, Info, Loader2,
  CheckCircle2, XCircle, Clock,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";
import { useBiasFlags, useBiasAudit, useAnonymizedView } from "@/lib/hooks";
import type { BackendBiasFlagOut, BackendBiasAuditOut } from "@/lib/api";

const severityColor: Record<string, string> = {
  low: "border-yellow-500/30 bg-yellow-500/10 text-yellow-400",
  medium: "border-orange-500/30 bg-orange-500/10 text-orange-400",
  high: "border-red-500/30 bg-red-500/10 text-red-400",
  critical: "border-rose-500/30 bg-rose-500/10 text-rose-400",
};

const statusIcon: Record<string, typeof Clock> = {
  open: Clock,
  reviewed: CheckCircle2,
  dismissed: XCircle,
};

function SeverityBadge({ severity }: { severity: string }) {
  const s = severity.toLowerCase();
  return (
    <Badge variant="outline" className={cn("text-[10px] font-mono", severityColor[s] ?? severityColor.low)}>
      {s}
    </Badge>
  );
}

function StatusBadge({ status }: { status: string }) {
  const s = status.toLowerCase();
  const Icon = statusIcon[s] ?? Clock;
  const colorMap: Record<string, string> = {
    open: "text-amber-400 border-amber-500/30 bg-amber-500/10",
    reviewed: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
    dismissed: "text-muted-foreground border-border/60 bg-muted/30",
  };
  return (
    <Badge variant="outline" className={cn("text-[10px] gap-1", colorMap[s] ?? colorMap.open)}>
      <Icon className="h-3 w-3" />
      {s}
    </Badge>
  );
}

function FlagCard({ flag }: { flag: BackendBiasFlagOut }) {
  return (
    <div className="glass rounded-xl p-4 space-y-2">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
          <p className="text-sm font-semibold text-foreground">{flag.rule}</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <SeverityBadge severity={flag.severity} />
          <StatusBadge status={flag.status} />
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        Scope: <span className="font-mono text-[11px]">{flag.scope}</span>
        {" · "}ID: <span className="font-mono text-[11px]">{flag.scope_id.slice(0, 12)}...</span>
      </p>
      {flag.detail && (
        <pre className="text-[10px] text-muted-foreground/70 overflow-x-auto max-h-20">
          {JSON.stringify(flag.detail, null, 1)}
        </pre>
      )}
      <p className="text-[10px] text-muted-foreground/50">
        {flag.created_at ? new Date(flag.created_at).toLocaleString() : ""}
      </p>
    </div>
  );
}

function AuditRow({ entry }: { entry: BackendBiasAuditOut }) {
  return (
    <div className="glass rounded-xl p-3 flex items-start gap-3">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/10 mt-0.5">
        <Info className="h-3.5 w-3.5 text-primary" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[13px] font-medium text-foreground">
          {entry.event_type.replace(/_/g, " ")}
        </p>
        <div className="mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground">
          {entry.candidate_id && <span>Candidate: {entry.candidate_id.slice(0, 12)}...</span>}
          {entry.job_id && <span>Job: {entry.job_id.slice(0, 12)}...</span>}
          {entry.actor_id && <span>Actor: {entry.actor_id.slice(0, 12)}...</span>}
        </div>
        {entry.detail_json && (
          <pre className="mt-1 text-[10px] text-muted-foreground/60 overflow-x-auto max-h-12">
            {JSON.stringify(entry.detail_json)}
          </pre>
        )}
        <p className="mt-0.5 text-[10px] text-muted-foreground/40">
          {new Date(entry.created_at).toLocaleString()}
        </p>
      </div>
    </div>
  );
}

export default function OrgBiasPage() {
  const [flagFilter, setFlagFilter] = useState("open");
  const [anonCandidateId, setAnonCandidateId] = useState("");

  const { data: flags = [], isLoading: flagsLoading } = useBiasFlags(
    flagFilter ? { status: flagFilter } : undefined,
  );
  const { data: audit = [], isLoading: auditLoading } = useBiasAudit();
  const { data: anonymizedView, isLoading: anonLoading } = useAnonymizedView(anonCandidateId);

  const openCount = flags.filter((f) => f.status === "open").length;

  return (
    <div className="h-full overflow-y-auto p-6 space-y-8 max-w-5xl">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-3"
      >
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
          <ShieldCheck className="h-5 w-5 text-primary" />
        </div>
        <div>
          <h1 className="font-heading text-xl font-bold tracking-tight text-foreground">
            Bias & Fairness
          </h1>
          <p className="text-sm text-muted-foreground">
            Guardrails, anonymization, and audit trail across the hiring pipeline.
          </p>
        </div>
      </motion.div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="glass rounded-xl p-5 space-y-1"
        >
          <p className="text-2xl font-bold text-foreground">{openCount}</p>
          <p className="text-xs text-muted-foreground">Open bias flags</p>
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.08 }}
          className="glass rounded-xl p-5 space-y-1"
        >
          <p className="text-2xl font-bold text-foreground">{flags.length - openCount}</p>
          <p className="text-xs text-muted-foreground">Reviewed / dismissed</p>
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.11 }}
          className="glass rounded-xl p-5 space-y-1"
        >
          <p className="text-2xl font-bold text-foreground">{audit.length}</p>
          <p className="text-xs text-muted-foreground">Audit events tracked</p>
        </motion.div>
      </div>

      {/* Bias Flags */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.14 }}
        className="glass gradient-border rounded-2xl p-6 space-y-4"
      >
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-400" />
            <h2 className="text-sm font-semibold uppercase tracking-wider text-foreground">
              Bias Flags
            </h2>
          </div>
          <div className="flex items-center gap-2">
            {["open", "reviewed", "dismissed", ""].map((s) => (
              <button
                key={s}
                onClick={() => setFlagFilter(s)}
                className={cn(
                  "px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors",
                  flagFilter === s
                    ? "bg-primary/15 text-primary"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/30",
                )}
              >
                {s || "all"}
              </button>
            ))}
          </div>
        </div>

        {flagsLoading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading flags…
          </div>
        )}

        {!flagsLoading && flags.length === 0 && (
          <div className="glass rounded-xl p-6 text-sm text-muted-foreground text-center">
            No bias flags found. The system is operating without bias alerts.
          </div>
        )}

        {!flagsLoading && flags.length > 0 && (
          <div className="space-y-3">
            {flags.map((flag) => (
              <FlagCard key={flag.id} flag={flag} />
            ))}
          </div>
        )}
      </motion.div>

      {/* Audit Log */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.17 }}
        className="glass gradient-border rounded-2xl p-6 space-y-4"
      >
        <div className="flex items-center gap-2">
          <Info className="h-4 w-4 text-primary" />
          <h2 className="text-sm font-semibold uppercase tracking-wider text-foreground">
            Audit Log
          </h2>
        </div>

        {auditLoading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading audit log…
          </div>
        )}

        {!auditLoading && audit.length === 0 && (
          <div className="glass rounded-xl p-6 text-sm text-muted-foreground text-center">
            No audit entries recorded yet.
          </div>
        )}

        {!auditLoading && audit.length > 0 && (
          <div className="space-y-2">
            {audit.slice(0, 20).map((entry) => (
              <AuditRow key={entry.id} entry={entry} />
            ))}
          </div>
        )}
      </motion.div>

      {/* Anonymization Lookup */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="glass rounded-xl p-6 space-y-4"
      >
        <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Anonymization Lookup
        </h2>
        <p className="text-xs text-muted-foreground">
          Enter a candidate UUID to view the anonymized profile used by scoring agents.
        </p>
        <div className="flex gap-2">
          <div className="flex-1">
            <Input
              placeholder="Candidate UUID"
              value={anonCandidateId}
              onChange={(e) => setAnonCandidateId(e.target.value)}
            />
          </div>
        </div>
        {anonLoading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading…
          </div>
        )}
        {anonymizedView && (
          <div className="glass rounded-xl p-4 space-y-2 text-sm">
            <p className="font-mono text-xs text-muted-foreground">
              View v{anonymizedView.view_version}
              {" · "}Stripped {anonymizedView.stripped_fields?.length ?? 0} fields
            </p>
            {anonymizedView.stripped_fields && anonymizedView.stripped_fields.length > 0 && (
              <p className="text-xs text-amber-400">
                Stripped: {anonymizedView.stripped_fields.join(", ")}
              </p>
            )}
            <pre className="text-[10px] text-muted-foreground/70 overflow-x-auto max-h-40">
              {JSON.stringify(anonymizedView.view_json, null, 1)}
            </pre>
          </div>
        )}
      </motion.div>
    </div>
  );
}

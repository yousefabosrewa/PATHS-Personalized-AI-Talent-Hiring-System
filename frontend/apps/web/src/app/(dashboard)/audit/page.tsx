"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Search, Filter, Shield, Download, ChevronRight, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuditEvents } from "@/lib/hooks";
import { cn } from "@/lib/utils/cn";
import { shortDateTime, relativeTime } from "@/lib/utils/format";
import type { AuditAction, UserRole } from "@/types";

const actionColor: Record<string, string> = {
  "candidate.deanonymized": "text-orange-400",
  "shortlist.approved":     "text-emerald-400",
  "shortlist.rejected":     "text-red-400",
  "shortlist.proposed":     "text-primary",
  "decision.finalized":     "text-amber-400",
  "job.published":          "text-teal-400",
  "member.invited":         "text-indigo-400",
  "candidate.merged":       "text-cyan-400",
  "org.settings_updated":   "text-violet-400",
  "assessment.generated":   "text-primary",
};

const actorRoleLabel: Record<UserRole, string> = {
  admin:          "Admin",
  super_admin:    "Super Admin",
  recruiter:      "Recruiter",
  hiring_manager: "Hiring Mgr.",
  interviewer:    "Interviewer",
  candidate:      "Candidate",
};

export default function AuditPage() {
  const { data: events = [] } = useAuditEvents();
  const [search, setSearch] = useState("");

  const filtered = events.filter((ev) =>
    !search ||
    ev.action.toLowerCase().includes(search.toLowerCase()) ||
    ev.actorName.toLowerCase().includes(search.toLowerCase()) ||
    ev.targetLabel.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="h-full overflow-y-auto">
      {/* Header */}
      <div className="border-b border-border/50 bg-background/60 backdrop-blur-sm px-6 py-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="font-heading text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              <Shield className="h-5 w-5 text-primary" /> Audit Log
            </h1>
            <p className="text-sm text-muted-foreground">
              Immutable append-only record · Every action is traceable
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground/60" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search events…"
                className="h-9 w-52 rounded-lg border border-border/60 bg-muted/40 pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground/50 focus:border-primary/50 focus:outline-none focus:ring-1 focus:ring-primary/20 transition-all"
              />
            </div>
            <Button variant="outline" size="sm" className="h-9 gap-1.5 text-xs">
              <Filter className="h-3.5 w-3.5" /> Filter
            </Button>
            <Button variant="outline" size="sm" className="h-9 gap-1.5 text-xs">
              <Download className="h-3.5 w-3.5" /> Export
            </Button>
          </div>
        </div>
      </div>

      <div className="p-6 max-w-5xl space-y-2">
        {/* Stats */}
        <div className="flex items-center gap-6 text-xs text-muted-foreground mb-4">
          <span><span className="font-semibold text-foreground">{events.length}</span> total events</span>
          <span><span className="font-semibold text-foreground">{filtered.length}</span> shown</span>
          <span className="flex items-center gap-1 text-emerald-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 agent-pulse" />
            Append-only · tamper-evident
          </span>
        </div>

        {/* Timeline */}
        <div className="glass rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border/40 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/60">
                <th className="px-4 py-3 text-left">Timestamp</th>
                <th className="px-4 py-3 text-left">Actor</th>
                <th className="px-4 py-3 text-left">Action</th>
                <th className="px-4 py-3 text-left">Target</th>
                <th className="px-4 py-3 text-left">IP</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border/30">
              {filtered.map((event, i) => (
                <motion.tr
                  key={event.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: i * 0.03 }}
                  className="group hover:bg-muted/20 transition-colors"
                >
                  <td className="px-4 py-3 whitespace-nowrap">
                    <div>
                      <p className="text-[12px] font-mono text-foreground/80">{shortDateTime(event.timestamp)}</p>
                      <p className="text-[10px] text-muted-foreground/60">{relativeTime(event.timestamp)}</p>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div>
                      <p className="text-[13px] font-semibold text-foreground">{event.actorName}</p>
                      <p className="text-[11px] text-muted-foreground">
                        {actorRoleLabel[event.actorRole] ?? event.actorRole}
                      </p>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn(
                      "font-mono text-[12px] font-semibold",
                      actionColor[event.action] ?? "text-muted-foreground"
                    )}>
                      {event.action}
                    </span>
                  </td>
                  <td className="px-4 py-3 max-w-[200px]">
                    <p className="text-[12px] text-foreground/80 truncate" title={event.targetLabel}>
                      {event.targetLabel}
                    </p>
                  </td>
                  <td className="px-4 py-3">
                    <span className="font-mono text-[11px] text-muted-foreground/60">{event.ip}</span>
                  </td>
                  <td className="px-4 py-3">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 opacity-0 group-hover:opacity-100"
                      title="View details"
                    >
                      <ExternalLink className="h-3 w-3" />
                    </Button>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>

          {filtered.length === 0 && (
            <div className="py-16 text-center">
              <Shield className="mx-auto h-8 w-8 text-muted-foreground/30 mb-2" />
              <p className="text-sm text-muted-foreground">No events match your search.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

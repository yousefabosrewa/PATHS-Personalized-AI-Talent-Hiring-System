"use client";

import { Users, Star, CheckCircle, Clock } from "lucide-react";
import type { JobDetailStats } from "@/types";

interface Props {
  stats: JobDetailStats;
}

export function JobStatsStrip({ stats }: Props) {
  const shortlisted = stats.byStage.shortlist + stats.byStage.reveal +
    stats.byStage.outreach + stats.byStage.interview +
    stats.byStage.evaluate + stats.byStage.decide;

  const cards = [
    { label: "Total Candidates", value: stats.totalCandidates, icon: Users, color: "text-blue-600" },
    { label: "In Screening", value: stats.byStage.screen, icon: Star, color: "text-amber-600" },
    { label: "Shortlisted+", value: shortlisted, icon: CheckCircle, color: "text-green-600" },
    { label: "In Pipeline", value: stats.totalCandidates, icon: Clock, color: "text-purple-600" },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {cards.map(({ label, value, icon: Icon, color }) => (
        <div
          key={label}
          className="rounded-xl border border-border bg-card px-4 py-3 flex items-center gap-3"
        >
          <Icon className={`h-5 w-5 shrink-0 ${color}`} />
          <div>
            <p className="text-2xl font-bold leading-none">{value}</p>
            <p className="mt-1 text-xs text-muted-foreground">{label}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

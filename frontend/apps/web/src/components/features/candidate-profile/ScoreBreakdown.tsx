"use client";

import { cn } from "@/lib/utils";
import type { ScoreCriterion } from "@/types";

interface Props {
  scores: ScoreCriterion[];
  overallScore: number | null;
}

function ScoreBar({ value, max = 100 }: { value: number; max?: number }) {
  const pct = Math.min(100, (value / max) * 100);
  const color =
    pct >= 75 ? "bg-green-500"
    : pct >= 50 ? "bg-amber-500"
    : "bg-red-500";
  return (
    <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
      <div className={cn("h-full rounded-full transition-all", color)} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function ScoreBreakdown({ scores, overallScore }: Props) {
  if (scores.length === 0 && overallScore == null) return null;

  return (
    <div className="space-y-4">
      {overallScore != null && (
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Overall Score
          </span>
          <span className="text-lg font-bold tabular-nums">{overallScore.toFixed(0)}</span>
        </div>
      )}

      {scores.length > 0 && (
        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Criteria Breakdown
          </p>
          {scores.map((s) => (
            <div key={s.criterion} className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="capitalize">{s.criterion.replace(/_/g, " ")}</span>
                <span className="tabular-nums font-medium">
                  {s.score != null ? s.score.toFixed(0) : "—"}
                  {s.weight != null && (
                    <span className="text-muted-foreground ml-1">×{s.weight}</span>
                  )}
                </span>
              </div>
              {s.score != null && <ScoreBar value={s.score} />}
              {s.reasoning && (
                <p className="text-[10px] text-muted-foreground leading-relaxed line-clamp-2">
                  {s.reasoning}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

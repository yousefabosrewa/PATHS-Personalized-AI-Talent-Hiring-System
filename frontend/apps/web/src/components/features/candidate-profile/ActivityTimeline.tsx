"use client";

import { formatDistanceToNow } from "date-fns";
import type { ActivityEvent } from "@/types";

interface Props {
  activity: ActivityEvent[];
}

const EVENT_COLORS: Record<string, string> = {
  stage_change: "bg-blue-500",
  score_update: "bg-green-500",
  note_added: "bg-amber-500",
  email_sent: "bg-purple-500",
  interview_scheduled: "bg-indigo-500",
};

function dot(type: string) {
  return EVENT_COLORS[type] ?? "bg-muted-foreground";
}

function formatEventLabel(type: string) {
  return type.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
}

export function ActivityTimeline({ activity }: Props) {
  if (activity.length === 0) {
    return (
      <p className="text-xs text-muted-foreground py-4 text-center">No activity recorded yet.</p>
    );
  }

  return (
    <div className="relative space-y-4 pl-5">
      {/* Vertical line */}
      <div className="absolute left-[7px] top-0 bottom-0 w-px bg-border" />

      {activity.map((event, i) => (
        <div key={i} className="relative flex gap-3">
          {/* Dot */}
          <div className={`absolute -left-[13px] mt-0.5 h-3 w-3 rounded-full border-2 border-background ${dot(event.type)}`} />

          <div className="min-w-0 flex-1">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-xs font-medium">{formatEventLabel(event.type)}</span>
              <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                {formatDistanceToNow(new Date(event.at), { addSuffix: true })}
              </span>
            </div>
            {event.actor && (
              <p className="text-[10px] text-muted-foreground">{event.actor}</p>
            )}
            {Object.keys(event.payload).length > 0 && (
              <div className="mt-0.5 text-[10px] text-muted-foreground space-x-2">
                {Object.entries(event.payload).map(([k, v]) => (
                  <span key={k}>
                    <span className="font-medium">{k}:</span> {String(v)}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

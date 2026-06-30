"use client";

import { Shield, Info, Workflow, Flag, CheckCircle2 } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { JobDetail } from "@/types";

interface Props {
  job: JobDetail;
}

export function JobOverviewTab({ job }: Props) {
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      {/* Left: description */}
      <div className="lg:col-span-2 space-y-6">
        {job.description && (
          <section>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Description
            </h2>
            <div
              className="prose prose-sm dark:prose-invert max-w-none"
              dangerouslySetInnerHTML={{ __html: job.description }}
            />
          </section>
        )}

        {job.requiredSkills.length > 0 && (
          <section>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Required Skills
            </h2>
            <div className="flex flex-wrap gap-2">
              {job.requiredSkills.map((s) => (
                <span
                  key={s.name}
                  className="inline-flex items-center gap-1 rounded-md border border-border bg-muted px-2.5 py-1 text-xs font-medium"
                >
                  {s.name}
                  <span className="text-muted-foreground">w{s.weight}</span>
                </span>
              ))}
            </div>
          </section>
        )}

        {job.optionalSkills.length > 0 && (
          <section>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Nice-to-have
            </h2>
            <div className="flex flex-wrap gap-2">
              {job.optionalSkills.map((s) => (
                <span
                  key={s.name}
                  className="inline-flex items-center gap-1 rounded-md border border-dashed border-border px-2.5 py-1 text-xs text-muted-foreground"
                >
                  {s.name}
                </span>
              ))}
            </div>
          </section>
        )}
      </div>

      {/* Right: salary + workflow + fairness rubric */}
      <div className="space-y-4">
        {/* Configured candidate workflow (hiring pipeline) */}
        <div className="rounded-xl border border-border bg-card p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Workflow className="h-4 w-4 text-blue-500" />
            <p className="text-sm font-semibold">Hiring workflow</p>
          </div>
          <ol className="space-y-1.5">
            <li className="flex items-center gap-2 text-xs text-muted-foreground">
              <Flag className="h-3.5 w-3.5 shrink-0 text-emerald-500" /> Applied
            </li>
            {job.hiringPipeline.length === 0 && (
              <li className="text-xs text-muted-foreground">Default workflow.</li>
            )}
            {job.hiringPipeline.map((s, i) => (
              <li key={s.key} className="flex items-center gap-2 text-xs">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[10px] font-bold text-primary">
                  {i + 1}
                </span>
                <span className="font-medium">{s.label}</span>
                <span className="ml-auto rounded-full bg-muted px-2 py-0.5 text-[10px] capitalize text-muted-foreground">
                  {s.group}
                </span>
              </li>
            ))}
            <li className="flex items-center gap-2 text-xs text-muted-foreground">
              <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-blue-500" /> Offer → Hired
            </li>
          </ol>
        </div>

        {(job.salaryMin || job.salaryMax) && (
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">
              Salary Range
            </p>
            <p className="text-lg font-bold">
              {job.salaryMin != null ? `$${job.salaryMin.toLocaleString()}` : "—"}
              {" – "}
              {job.salaryMax != null ? `$${job.salaryMax.toLocaleString()}` : "—"}
            </p>
          </div>
        )}

        <div className="rounded-xl border border-border bg-card p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-blue-500" />
            <p className="text-sm font-semibold">Fairness Rubric</p>
          </div>

          {job.fairnessRubric ? (
            <>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Status</span>
                <span className={job.fairnessRubric.enabled ? "text-green-600 font-medium" : "text-muted-foreground"}>
                  {job.fairnessRubric.enabled ? "Enabled" : "Disabled"}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground flex items-center gap-1">
                  4/5 threshold
                  <Tooltip>
                    <TooltipTrigger>
                      <Info className="h-3 w-3" />
                    </TooltipTrigger>
                    <TooltipContent>
                      Disparate impact ratio — selection rate for any protected group must be ≥ {job.fairnessRubric.disparateImpactThreshold * 100}% of the highest-rate group.
                    </TooltipContent>
                  </Tooltip>
                </span>
                <span className="font-medium">{(job.fairnessRubric.disparateImpactThreshold * 100).toFixed(0)}%</span>
              </div>
              <div className="space-y-1">
                {Object.entries(job.fairnessRubric.protectedAttrs).map(([attr, on]) => (
                  <div key={attr} className="flex items-center justify-between text-xs">
                    <span className="capitalize text-muted-foreground">{attr.replace(/_/g, " ")}</span>
                    <span className={on ? "text-blue-600 font-medium" : "text-muted-foreground"}>
                      {on ? "Monitored" : "Off"}
                    </span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="text-xs text-muted-foreground">No rubric configured yet.</p>
          )}
        </div>
      </div>
    </div>
  );
}

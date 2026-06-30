"use client";

/**
 * Candidate Pipeline (fix2.md §1).
 *
 * Always renders as a list / table. The kanban view, the filter button and
 * the kanban/list view toggle were removed in fix2.md §1 — recruiters get a
 * single sortable, searchable table with every candidate's stage, job,
 * match score and applied-date.
 *
 * The Candidate Sources side-tab was also folded into this same page (see
 * `<CandidatesTabBar>`) so all candidate-related work lives under
 * /candidates instead of being split across three separate sidebar items.
 */

import { useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Search, Shield, ShieldOff, ChevronRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { useApplications } from "@/lib/hooks";
import { useAuthStore } from "@/lib/stores/auth.store";
import { cn } from "@/lib/utils/cn";
import { relativeTime, initials } from "@/lib/utils/format";
import type { Application, ApplicationStatus } from "@/types";
import { CandidatesTabBar } from "@/components/features/candidates/CandidatesTabBar";

// fix3.md §1 — these recruiter-style roles see the candidate pipeline
// with names anonymized by default.  Identity is only revealed for a
// specific candidate after the Hiring Manager approves a de-anonymization
// request on the candidate's profile page.
const HR_ROLE_CODES = new Set([
  "admin", "hr", "hr_manager", "recruiter",
  "hiring_manager", "manager", "lead",
]);

const STAGE_CHIP: Record<ApplicationStatus, { label: string; color: string }> = {
  applied:        { label: "Applied",        color: "bg-slate-500/10 text-slate-400 border-slate-500/20" },
  sourced:        { label: "Sourced",        color: "bg-slate-500/10 text-slate-400 border-slate-500/20" },
  screening:      { label: "Screening",      color: "bg-primary/10 text-primary border-primary/20" },
  assessment:     { label: "Assessment",     color: "bg-violet-500/10 text-violet-400 border-violet-500/20" },
  hr_interview:   { label: "HR Interview",   color: "bg-teal-500/10 text-teal-400 border-teal-500/20" },
  tech_interview: { label: "Tech Interview", color: "bg-indigo-500/10 text-indigo-400 border-indigo-500/20" },
  decision:       { label: "Decision",       color: "bg-amber-500/10 text-amber-400 border-amber-500/20" },
  rejected:       { label: "Rejected Candidate", color: "bg-rose-500/10 text-rose-400 border-rose-500/20" },
  withdrawn:      { label: "Withdrawn",      color: "bg-zinc-500/10 text-zinc-400 border-zinc-500/20" },
  hired:          { label: "Accepted Candidate", color: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" },
};

function ScoreCell({ score }: { score?: number }) {
  if (score == null || Number.isNaN(score)) {
    return (
      <span className="text-[11px] font-medium text-muted-foreground/80 whitespace-nowrap">
        Not scored yet
      </span>
    );
  }
  const color = score >= 80 ? "text-emerald-400" : score >= 60 ? "text-amber-400" : "text-red-400";
  return <span className={cn("font-mono text-[13px] font-bold", color)}>{score}%</span>;
}

export default function CandidatesPipelinePage() {
  const { data: applications = [], isLoading, isError, error, refetch } = useApplications();
  const [search, setSearch] = useState("");
  const { user: authUser } = useAuthStore();
  const role = String(authUser?.role ?? authUser?.accountType ?? "").toLowerCase();
  // HR / recruiter / hiring-manager → anonymize names in this list.
  const anonymizeByDefault = HR_ROLE_CODES.has(role);

  const filtered = applications.filter((app) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    // Recruiters search by alias / job / title only — real name is masked.
    return (
      (!anonymizeByDefault && app.candidate.name.toLowerCase().includes(q)) ||
      app.candidate.alias.toLowerCase().includes(q) ||
      app.candidate.title.toLowerCase().includes(q) ||
      app.job.title.toLowerCase().includes(q)
    );
  });

  return (
    <div className="flex h-full flex-col">
      {/* Top bar */}
      <div className="border-b border-border/50 bg-background/60 backdrop-blur-sm px-6 py-4">
        <div className="flex items-center justify-between gap-4 mb-3">
          <div>
            <h1 className="font-heading text-xl font-bold tracking-tight text-foreground">
              Candidates
            </h1>
            <p className="text-sm text-muted-foreground">
              {isLoading
                ? "Loading pipeline…"
                : `${applications.length} in pipeline · ${filtered.length} shown`}
            </p>
          </div>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground/60" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by name, title or job…"
              className="h-9 w-72 rounded-lg border border-border/60 bg-muted/40 pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground/50 focus:border-primary/50 focus:outline-none focus:ring-1 focus:ring-primary/20 transition-all"
            />
          </div>
        </div>
        <CandidatesTabBar />
      </div>

      {isError && (
        <div className="mx-6 mt-4 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error instanceof Error ? error.message : "Could not load applications."}{" "}
          <button type="button" onClick={() => void refetch()} className="ml-2 underline">
            Retry
          </button>
        </div>
      )}

      {/* List view */}
      {isLoading ? (
        <div className="flex-1 p-6">
          <div className="glass rounded-xl h-64 animate-pulse bg-muted/15" />
        </div>
      ) : applications.length === 0 ? (
        <div className="flex flex-1 items-center justify-center p-6">
          <div className="max-w-md rounded-xl border border-dashed border-border/50 px-8 py-12 text-center text-sm text-muted-foreground">
            No applications yet. Use <strong>Candidates → Sources</strong> to import a CSV or
            invite candidates to apply.
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-6">
          <div className="glass rounded-xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border/40 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/60">
                  <th className="px-4 py-3 text-left">Candidate</th>
                  <th className="px-4 py-3 text-left">Stage</th>
                  <th className="px-4 py-3 text-left">Job</th>
                  <th className="px-4 py-3 text-right">Match score</th>
                  <th className="px-4 py-3 text-right">Applied</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border/30">
                {filtered.map((app: Application) => {
                  const c = app.candidate;
                  // Anonymize for HR users until they've been approved per-candidate.
                  // The list view never knows about per-candidate approvals (those
                  // are scoped to the profile page), so we apply blanket
                  // anonymization to the table here — recruiters open a profile
                  // and request de-anon there.
                  const masked = anonymizeByDefault || app.isAnonymized;
                  const stageConf = STAGE_CHIP[app.status] ?? STAGE_CHIP.applied;
                  return (
                    <motion.tr
                      key={app.id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="group hover:bg-muted/20 transition-colors"
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className="relative">
                            <Avatar className="h-8 w-8">
                              <AvatarFallback className="bg-primary/10 text-primary text-[11px]">
                                {masked ? "?" : initials(c.name)}
                              </AvatarFallback>
                            </Avatar>
                            {masked ? (
                              <ShieldOff className="absolute -right-1 -top-1 h-3 w-3 text-amber-400" />
                            ) : (
                              <Shield className="absolute -right-1 -top-1 h-3 w-3 text-emerald-400/70" />
                            )}
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-foreground">
                              {masked ? c.alias : c.name}
                            </p>
                            <p className="text-[11px] text-muted-foreground">{c.title || "—"}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={cn("rounded-full border px-2 py-0.5 text-[11px] font-semibold", stageConf.color)}>
                          {stageConf.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-muted-foreground truncate max-w-[240px]">
                        {app.job.title || "—"}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <ScoreCell score={app.matchScore} />
                      </td>
                      <td className="px-4 py-3 text-right text-[12px] text-muted-foreground">
                        {relativeTime(app.applyDate)}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Link href={`/candidates/${c.id}`}>
                          <Button variant="ghost" size="icon" className="h-7 w-7 opacity-0 group-hover:opacity-100">
                            <ChevronRight className="h-3.5 w-3.5" />
                          </Button>
                        </Link>
                      </td>
                    </motion.tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

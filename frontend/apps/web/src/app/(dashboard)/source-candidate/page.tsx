"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Database,
  Loader2,
  Sparkles,
  UserRound,
  CheckCircle2,
  ChevronRight,
  ExternalLink,
  Telescope,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useJobs, useShortlistSourcedCandidate } from "@/lib/hooks";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils/cn";

// Recruiter Source Candidate workspace.
//
// Layout:
//   * Top: job picker (used by Shortlist + Explain context) + search.
//   * "Candidates From Our Database" — Explain + Shortlist per row.
//     (The LinkedIn Open-To-Work fetch tab was removed; previously imported
//     candidates keep their provenance label on the card.)

interface DatabaseCandidate {
  candidate_id: string;
  full_name: string;
  current_title: string | null;
  location_text: string | null;
  headline: string | null;
  summary: string | null;
  years_experience: number | null;
  skills: string[];
  source_type: string | null;
  source_platform: string | null;
  status: string | null;
  profile_completion_status: string | null;
  created_at: string | null;
}

interface DatabaseCandidateList {
  total: number;
  items: DatabaseCandidate[];
}

interface ExplainResponse {
  candidate_id: string;
  summary: string;
  fit_explanation: string;
  strengths: string[];
  gaps: string[];
  risks: string[];
  recommended_action:
    | "Shortlist"
    | "Review manually"
    | "Request more information"
    | "Reject for now";
  confidence: number;
  used_fallback: boolean;
}

const API_BASE = "/api/v1/recruiter/source-candidate";

export default function SourceCandidatePage() {
  const qc = useQueryClient();
  const { data: jobs = [] } = useJobs({ limit: 100 });
  const [selectedJobId, setSelectedJobId] = useState<string>("");
  const resolvedJobId = selectedJobId || (jobs[0] ? String(jobs[0].id) : "");

  const [q, setQ] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [shortlistingId, setShortlistingId] = useState<string | null>(null);
  const [shortlistedIds, setShortlistedIds] = useState<Set<string>>(new Set());
  const [explainById, setExplainById] = useState<
    Record<string, ExplainResponse | "loading">
  >({});
  const [toast, setToast] = useState<{
    kind: "success" | "duplicate" | "error";
    text: string;
  } | null>(null);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4500);
    return () => clearTimeout(t);
  }, [toast]);

  // ── Seed shortlisted set from server when the job changes ──────────────
  const shortlistedQuery = useQuery({
    queryKey: ["source-candidate", "shortlisted-for-job", resolvedJobId],
    queryFn: () =>
      api.get<string[]>(
        `/api/v1/sourcing/jobs/${encodeURIComponent(resolvedJobId)}/shortlisted`,
      ),
    enabled: Boolean(resolvedJobId),
    staleTime: 30_000,
  });
  useEffect(() => {
    if (!shortlistedQuery.data) return;
    setShortlistedIds((prev) => new Set([...prev, ...shortlistedQuery.data!]));
  }, [shortlistedQuery.data]);

  // ── Section 1: real candidates from the DB ─────────────────────────────
  const dbQuery = useQuery({
    queryKey: ["source-candidate", "database", q],
    queryFn: () =>
      api.get<DatabaseCandidateList>(
        `${API_BASE}/database${q ? `?q=${encodeURIComponent(q)}` : ""}`,
      ),
    staleTime: 30_000,
  });

  // ── Explain ────────────────────────────────────────────────────────────
  const explainMutation = useMutation({
    mutationFn: async (vars: { candidateId: string; jobId?: string }) =>
      api.post<ExplainResponse>(
        `/api/v1/sourcing/candidates/${encodeURIComponent(vars.candidateId)}/explain`,
        { job_id: vars.jobId || null, source: "database" },
      ),
  });

  async function onExplain(candidateId: string) {
    setActionError(null);
    setExplainById((prev) => ({ ...prev, [candidateId]: "loading" }));
    try {
      const res = await explainMutation.mutateAsync({
        candidateId,
        jobId: resolvedJobId || undefined,
      });
      setExplainById((prev) => ({ ...prev, [candidateId]: res }));
    } catch (err) {
      setExplainById((prev) => {
        const next = { ...prev };
        delete next[candidateId];
        return next;
      });
      setActionError(
        err instanceof Error ? err.message : "Failed to generate explanation.",
      );
    }
  }

  // ── Shortlist ──────────────────────────────────────────────────────────
  const shortlistMutation = useShortlistSourcedCandidate();
  async function onShortlist(candidateId: string) {
    setActionError(null);
    if (!resolvedJobId) {
      setActionError("Pick a job above to shortlist candidates against.");
      return;
    }
    if (shortlistedIds.has(candidateId)) return;
    setShortlistingId(candidateId);
    try {
      await shortlistMutation.mutateAsync({
        jobId: resolvedJobId,
        candidateId,
        stageCode: "sourced",
      });
      setShortlistedIds((prev) => {
        const next = new Set(prev);
        next.add(candidateId);
        return next;
      });
      setToast({ kind: "success", text: "Candidate shortlisted to the selected job." });
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "Failed to shortlist candidate.",
      );
    } finally {
      setShortlistingId(null);
    }
  }

  return (
    <div className="h-full overflow-y-auto p-6 space-y-5 max-w-5xl">
      {/* Page header + job picker */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2 text-primary">
            <Telescope className="h-4 w-4" />
            <span className="text-[11px] font-semibold uppercase tracking-widest">
              Source Candidate
            </span>
          </div>
          <h1 className="font-heading text-xl font-bold tracking-tight text-foreground mt-1">
            Source Candidate
          </h1>
          <p className="text-sm text-muted-foreground">
            Manage, score and shortlist the candidates in your database.
          </p>
        </div>

        <div className="flex flex-wrap items-end gap-2">
          <div>
            <label className="block text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-1">
              Active job
            </label>
            <select
              value={resolvedJobId}
              onChange={(e) => setSelectedJobId(e.target.value)}
              className="rounded-md border border-border bg-background px-3 py-2 text-sm min-w-[16rem]"
              aria-label="Active job context"
            >
              <option value="">No job selected</option>
              {jobs.map((j) => (
                <option key={String(j.id)} value={String(j.id)}>
                  {j.title}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="glass rounded-xl p-4">
        <Input
          placeholder="Search candidates by name, title, headline or location…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>

      {actionError && (
        <p className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {actionError}
        </p>
      )}

      {/* ── Candidates From Our Database ─────────────────────────────── */}
      <div className="mt-2 space-y-3">
        <p className="text-xs text-muted-foreground">
          Total Candidates: {dbQuery.data?.total ?? 0}
        </p>
        {dbQuery.isLoading ? (
          <LoadingRow label="Loading candidates…" />
        ) : dbQuery.isError ? (
          <ErrorRow label="Failed to load candidates." />
        ) : (dbQuery.data?.items.length ?? 0) === 0 ? (
          <EmptyRow label="No candidates in your database yet." />
        ) : (
          dbQuery.data!.items.map((c) => (
            <DatabaseCard
              key={c.candidate_id}
              candidate={c}
              shortlisted={shortlistedIds.has(c.candidate_id)}
              shortlisting={shortlistingId === c.candidate_id}
              canShortlist={Boolean(resolvedJobId)}
              explanation={explainById[c.candidate_id]}
              onExplain={() => onExplain(c.candidate_id)}
              onShortlist={() => onShortlist(c.candidate_id)}
            />
          ))
        )}
      </div>

      {toast && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className={cn(
            "fixed bottom-6 right-6 z-30 rounded-lg px-4 py-3 text-sm shadow-lg",
            toast.kind === "success" &&
              "border border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
            toast.kind === "duplicate" &&
              "border border-amber-500/40 bg-amber-500/10 text-amber-200",
            toast.kind === "error" &&
              "border border-destructive/40 bg-destructive/10 text-destructive",
          )}
        >
          {toast.text}
        </motion.div>
      )}
    </div>
  );
}

// ── Cards ────────────────────────────────────────────────────────────────

function DatabaseCard(props: {
  candidate: DatabaseCandidate;
  shortlisted: boolean;
  shortlisting: boolean;
  canShortlist: boolean;
  explanation: ExplainResponse | "loading" | undefined;
  onExplain: () => void;
  onShortlist: () => void;
}) {
  const c = props.candidate;
  const sourceLabel = sourceBadgeLabel(c.source_type, c.source_platform);
  return (
    <motion.div layout className="glass rounded-xl p-4 space-y-2">
      <div className="flex items-baseline justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="font-semibold text-sm text-foreground">
            {c.full_name || "—"}
          </p>
          <Badge
            variant="outline"
            className="border-primary/30 bg-primary/10 text-primary text-[10px]"
          >
            Database
          </Badge>
          {sourceLabel && (
            <Badge
              variant="outline"
              className="border-sky-500/40 bg-sky-500/10 text-sky-300 text-[10px]"
            >
              {sourceLabel}
            </Badge>
          )}
          <StatusBadge shortlisted={props.shortlisted} />
          {c.profile_completion_status === "incomplete" && (
            <Badge
              variant="outline"
              className="border-amber-500/40 bg-amber-500/10 text-amber-300 text-[10px]"
            >
              Profile incomplete
            </Badge>
          )}
        </div>
      </div>
      <p className="text-[12px] text-muted-foreground">
        {c.current_title || c.headline || "—"}
        {c.location_text ? ` · ${c.location_text}` : ""}
        {typeof c.years_experience === "number"
          ? ` · ${c.years_experience} yrs`
          : ""}
      </p>
      {c.summary && (
        <p className="text-[13px] text-foreground/80 line-clamp-3">
          {c.summary}
        </p>
      )}
      <SkillsRow skills={c.skills} />
      <ActionRow
        profileHref={`/candidates/${encodeURIComponent(c.candidate_id)}`}
        shortlisted={props.shortlisted}
        shortlisting={props.shortlisting}
        canShortlist={props.canShortlist}
        onExplain={props.onExplain}
        onShortlist={props.onShortlist}
      />
      <ExplanationBlock state={props.explanation} />
    </motion.div>
  );
}

// ── Shared row pieces ────────────────────────────────────────────────────

function ActionRow(props: {
  profileHref: string;
  shortlisted: boolean;
  shortlisting: boolean;
  canShortlist: boolean;
  onExplain: () => void;
  onShortlist: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 pt-1">
      <Button size="sm" variant="ghost" asChild>
        <Link href={props.profileHref}>
          <UserRound className="h-3.5 w-3.5" /> View Profile
        </Link>
      </Button>
      <Button size="sm" variant="ghost" onClick={props.onExplain}>
        <Sparkles className="h-3.5 w-3.5" /> Explain
      </Button>
      <Button
        size="sm"
        disabled={
          !props.canShortlist || props.shortlisted || props.shortlisting
        }
        onClick={props.onShortlist}
        title={!props.canShortlist ? "Pick a job above first" : undefined}
      >
        {props.shortlisting ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : props.shortlisted ? (
          <CheckCircle2 className="h-3.5 w-3.5" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5" />
        )}
        {props.shortlisted ? "Shortlisted" : "Shortlist"}
      </Button>
    </div>
  );
}

function ExplanationBlock({
  state,
}: {
  state: ExplainResponse | "loading" | undefined;
}) {
  if (!state) return null;
  if (state === "loading") {
    return (
      <div className="mt-2 flex items-center gap-2 rounded-lg border border-border/60 bg-muted/30 px-3 py-2 text-[12px] text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" /> Generating explanation…
      </div>
    );
  }
  const pct = Math.round(state.confidence * 100);
  return (
    <div className="mt-2 space-y-1.5 rounded-lg border border-border/60 bg-muted/30 p-3 text-[12px]">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <p className="text-[10px] uppercase tracking-widest text-primary/80">
          {state.recommended_action} · confidence {pct}%
        </p>
        {state.used_fallback && (
          <span className="text-[10px] text-amber-400">
            Generated using fallback logic — agent unavailable.
          </span>
        )}
      </div>
      <p className="text-foreground/90">{state.summary}</p>
      {state.fit_explanation && state.fit_explanation !== state.summary && (
        <p className="text-foreground/70">{state.fit_explanation}</p>
      )}
      {state.strengths.length > 0 && (
        <p className="text-emerald-400/90">+ {state.strengths.join(" · ")}</p>
      )}
      {state.gaps.length > 0 && (
        <p className="text-amber-400/90">– {state.gaps.join(" · ")}</p>
      )}
      {state.risks.length > 0 && (
        <p className="text-red-400/90">! {state.risks.join(" · ")}</p>
      )}
    </div>
  );
}

function StatusBadge({ shortlisted }: { shortlisted: boolean }) {
  if (shortlisted) {
    return (
      <Badge
        variant="outline"
        className="border-emerald-500/40 bg-emerald-500/10 text-emerald-400 text-[10px]"
      >
        Shortlisted
      </Badge>
    );
  }
  return null;
}

function SkillsRow({ skills }: { skills: string[] }) {
  if (!skills?.length) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {skills.slice(0, 10).map((s) => (
        <Badge key={s} variant="outline" className="text-[10px]">
          {s}
        </Badge>
      ))}
    </div>
  );
}

function LoadingRow({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" /> {label}
    </div>
  );
}

function ErrorRow({ label }: { label: string }) {
  return <p className="text-sm text-red-400">{label}</p>;
}

function EmptyRow({ label }: { label: string }) {
  return (
    <div className="glass rounded-xl p-6 text-sm text-muted-foreground">
      {label}
    </div>
  );
}

function sourceBadgeLabel(
  source_type: string | null,
  source_platform: string | null,
): string | null {
  if (
    source_platform === "linkedin_mcp" ||
    source_platform === "linkedin_open_to_work"
  ) {
    return "Source: LinkedIn Open-To-Work";
  }
  if (source_platform === "csv_export") {
    return "Source: External Recruitment Platform";
  }
  if (source_type === "sourced") {
    return "Source: External";
  }
  return null;
}

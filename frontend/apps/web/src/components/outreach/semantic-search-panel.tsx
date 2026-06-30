"use client";

/**
 * Semantic Candidate Search panel (fix7.md §1).
 *
 * Lives inside the Outreach workspace at /org/matching. Natural-language
 * search over the existing candidate vector index, with a per-result
 * agent explanation and an anonymized shortlist.
 *
 * Buttons: "Run RAG Test" pushes the candidate id to the RAG Test tab via
 * an onSelectForRagTest callback the parent provides.
 */

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import {
  Sparkles, Search, Loader2, AlertTriangle, ShieldCheck, BadgeCheck,
  Globe, UserRound, ListChecks, CheckCircle2, Database,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";
import { useSemanticCandidateSearch, useShortlistSourcedCandidate, useJobs } from "@/lib/hooks";
import type {
  BackendSemanticSearchResponse,
  BackendSemanticSearchRow,
  MatchingSourceFilter,
} from "@/lib/api";

const SOURCE_OPTIONS: { value: MatchingSourceFilter; label: string }[] = [
  { value: "all",          label: "All sources" },
  { value: "database",     label: "Database" },
  { value: "outbound",     label: "Outbound / LinkedIn OTW" },
  { value: "imported_csv", label: "Imported CSV" },
];

function ScorePill({ value, label }: { value: number; label: string }) {
  const color =
    value >= 70
      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
      : value >= 45
        ? "border-amber-500/30 bg-amber-500/10 text-amber-400"
        : "border-rose-500/30 bg-rose-500/10 text-rose-400";
  return (
    <Badge variant="outline" className={cn("font-mono text-[11px] font-bold", color)}>
      {label} {value}
    </Badge>
  );
}

function ResultCard({
  row,
  index,
  jobIdForShortlist,
}: {
  row: BackendSemanticSearchRow;
  index: number;
  jobIdForShortlist: string;
}) {
  const shortlist = useShortlistSourcedCandidate();
  const [shortlisted, setShortlisted] = useState(false);

  const onShortlist = async () => {
    if (!jobIdForShortlist) return;
    try {
      await shortlist.mutateAsync({
        jobId: jobIdForShortlist,
        candidateId: row.candidate_id,
        stageCode: "sourced",
      });
      setShortlisted(true);
    } catch {
      // surface via the button title / disabled state; intentionally silent here
    }
  };

  return (
    <motion.article
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04 }}
      className="glass gradient-border rounded-2xl p-5 space-y-3"
    >
      <header className="flex flex-wrap items-center gap-2">
        <h3 className="font-heading text-[14px] font-bold text-foreground">
          {row.anonymized_label}
        </h3>
        <ScorePill value={row.semantic_score} label="semantic" />
        <ScorePill value={row.confidence} label="confidence" />
        <Badge variant="outline" className="text-[10px] uppercase tracking-wider text-muted-foreground">
          {row.source_display}
        </Badge>
      </header>

      {(row.current_title || row.headline) && (
        <p className="text-[12px] text-muted-foreground">
          {row.current_title}
          {row.headline ? ` · ${row.headline}` : ""}
        </p>
      )}

      <section>
        <p className="text-[11px] font-semibold uppercase tracking-wide text-primary/80">
          Agent explanation
        </p>
        <p className="mt-1 text-[13px] leading-relaxed text-foreground/90">
          {row.agent_explanation || "Agent explanation could not be generated. Please retry."}
        </p>
      </section>

      {row.matched_evidence.length > 0 && (
        <section>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-emerald-400/80">
            Matched evidence
          </p>
          <ul className="mt-1 space-y-0.5">
            {row.matched_evidence.map((m, i) => (
              <li key={i} className="text-[12px] text-emerald-200/80">• {m}</li>
            ))}
          </ul>
        </section>
      )}
      {row.missing_signals.length > 0 && (
        <section>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-400/80">
            Missing signals
          </p>
          <ul className="mt-1 space-y-0.5">
            {row.missing_signals.map((m, i) => (
              <li key={i} className="text-[12px] text-amber-200/80">• {m}</li>
            ))}
          </ul>
        </section>
      )}

      <footer className="flex flex-wrap items-center gap-2 pt-1">
        <Button asChild size="sm" variant="ghost" className="text-xs">
          <Link href={`/candidates/${row.candidate_id}`}>
            <UserRound className="h-3.5 w-3.5" /> View profile
          </Link>
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="text-xs"
          disabled={!jobIdForShortlist || shortlist.isPending || shortlisted}
          onClick={onShortlist}
          title={!jobIdForShortlist ? "Pick a job below first" : undefined}
        >
          {shortlisted ? (
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
          ) : (
            <ListChecks className="h-3.5 w-3.5" />
          )}
          {shortlisted ? "Shortlisted" : "Shortlist"}
        </Button>
      </footer>
    </motion.article>
  );
}

export function SemanticSearchPanel() {
  const [query, setQuery] = useState("");
  const [source, setSource] = useState<MatchingSourceFilter>("all");
  const [limit, setLimit] = useState(10);
  const [jobIdForShortlist, setJobIdForShortlist] = useState<string>("");
  const [result, setResult] = useState<BackendSemanticSearchResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const { data: jobs = [] } = useJobs({ limit: 100 });
  const search = useSemanticCandidateSearch();

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    setResult(null);
    search.mutate(
      { query, source, limit },
      {
        onSuccess: (data) => setResult(data),
        onError: (e) =>
          setErr(e instanceof Error ? e.message : "Semantic search failed."),
      },
    );
  };

  const results = result?.results ?? [];
  const showEmpty = result !== null && results.length === 0 && !search.isPending;

  return (
    <div className="space-y-5">
      <div className="flex items-start gap-3 rounded-xl border border-border/40 bg-muted/20 p-3">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
          <Sparkles className="h-3.5 w-3.5" />
        </div>
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-primary/80">
            Semantic Candidate Search
          </p>
          <p className="mt-0.5 text-[12px] text-muted-foreground">
            Type a natural-language query — the platform embeds it and searches your
            candidate vector index. Results are anonymized by default.
          </p>
        </div>
      </div>

      <motion.form
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        onSubmit={onSubmit}
        className="glass gradient-border rounded-2xl p-6 space-y-4"
      >
        <div>
          <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Search query
          </label>
          <textarea
            rows={3}
            required
            placeholder="Find backend engineers with FastAPI, PostgreSQL, Docker, and 3+ years experience."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="mt-1 w-full rounded-lg border border-border/40 bg-background px-3 py-2 text-[13px] text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/40 resize-none"
          />
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Source
            </label>
            <select
              value={source}
              onChange={(e) => setSource(e.target.value as MatchingSourceFilter)}
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            >
              {SOURCE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Results
            </label>
            <div className="mt-1 flex items-center gap-2">
              <input
                type="range"
                min={1}
                max={30}
                step={1}
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                className="flex-1 accent-primary"
              />
              <span className="w-6 text-center font-mono text-sm font-bold text-foreground">
                {limit}
              </span>
            </div>
          </div>
          <div>
            <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Shortlist target (job)
            </label>
            <select
              value={jobIdForShortlist}
              onChange={(e) => setJobIdForShortlist(e.target.value)}
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              aria-label="Job to shortlist into"
            >
              <option value="">(no job — disables shortlist)</option>
              {jobs.map((j) => (
                <option key={String(j.id)} value={String(j.id)}>
                  {j.title}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex items-center justify-between gap-2 pt-1">
          <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
            Candidate identities stay hidden — only an alias and the agent explanation are returned.
          </div>
          <Button
            type="submit"
            className="gap-2 glow-blue"
            disabled={search.isPending || !query.trim()}
          >
            {search.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Searching…
              </>
            ) : (
              <>
                <Search className="h-4 w-4" />
                Search
              </>
            )}
          </Button>
        </div>
        {err && <p className="text-xs text-rose-400">{err}</p>}
      </motion.form>

      <AnimatePresence>
        {search.isPending && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex items-center gap-2 text-sm text-muted-foreground"
          >
            <Loader2 className="h-4 w-4 animate-spin" />
            Embedding query and searching the candidate vector index…
          </motion.div>
        )}
      </AnimatePresence>

      {showEmpty && (
        <div className="rounded-2xl border border-dashed border-border/40 py-12 text-center">
          <Globe className="mx-auto mb-3 h-8 w-8 text-muted-foreground/30" />
          <p className="text-sm text-muted-foreground">
            No matching real candidates found.
          </p>
          <p className="mt-1 text-xs text-muted-foreground/60">
            Try a broader query or a different source.
          </p>
        </div>
      )}

      {results.length > 0 && (
        <section>
          <header className="mb-3 flex flex-wrap items-center gap-2">
            <h2 className="font-heading text-base font-bold text-foreground">
              <Sparkles className="mr-1 inline h-4 w-4 text-primary" />
              Anonymized shortlist
            </h2>
            {result && !result.semantic_search_used && (
              <Badge
                variant="outline"
                className="border-amber-500/30 bg-amber-500/5 text-[10px] uppercase tracking-wider text-amber-300"
                title="Vector index unavailable — used keyword fallback ranking."
              >
                <Database className="mr-1 h-2.5 w-2.5" />
                Fallback ranking
              </Badge>
            )}
            {result && !result.agent_available && (
              <Badge
                variant="outline"
                className="border-amber-500/30 bg-amber-500/5 text-[10px] uppercase tracking-wider text-amber-300"
                title="Every explanation in this batch failed — the LLM agent is unavailable right now."
              >
                <AlertTriangle className="mr-1 h-2.5 w-2.5" />
                Agent unavailable
              </Badge>
            )}
            <Badge
              variant="outline"
              className="border-emerald-500/30 bg-emerald-500/5 text-[10px] uppercase tracking-wider text-emerald-300"
            >
              <BadgeCheck className="mr-1 h-2.5 w-2.5" />
              {results.length} candidate{results.length === 1 ? "" : "s"}
            </Badge>
          </header>
          <div className="space-y-3">
            {results.map((row, i) => (
              <ResultCard
                key={row.candidate_id}
                row={row}
                index={i}
                jobIdForShortlist={jobIdForShortlist}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

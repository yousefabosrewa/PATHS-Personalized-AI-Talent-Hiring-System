"use client";

/**
 * Find Talent panel (Candidates → Find Talent).
 *
 * One search that sources outbound candidates live from LinkedIn (via the
 * LinkedIn MCP server) and, when "All sources" is chosen, also folds in the
 * org's database candidates via semantic (vector) search. An agent distills a
 * concise LinkedIn query from the (possibly long) requirements brief, verifies
 * each candidate's public "Open to work" badge + real skills from their
 * profile, then ranks the pool against the target job — Open-to-Work first.
 */

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import {
  Search, Loader2, AlertTriangle, Globe, Database, MapPin,
  ExternalLink, UserPlus, CheckCircle2, Sparkles, Users, BadgeCheck, BriefcaseBusiness,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";
import { useFindTalent, useImportExternalCandidate, useJobs } from "@/lib/hooks";
import type {
  BackendFindTalentCandidate,
  BackendFindTalentResponse,
  FindTalentSource,
} from "@/lib/api";

const SOURCE_OPTIONS: { value: FindTalentSource; label: string }[] = [
  { value: "linkedin", label: "LinkedIn (outbound)" },
  { value: "all", label: "All sources (LinkedIn + database)" },
];

function ScorePill({ value }: { value: number }) {
  const color =
    value >= 80
      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
      : value >= 55
        ? "border-amber-500/30 bg-amber-500/10 text-amber-400"
        : "border-rose-500/30 bg-rose-500/10 text-rose-400";
  return (
    <Badge variant="outline" className={cn("font-mono text-[11px] font-bold", color)}>
      {Math.round(value)} fit
    </Badge>
  );
}

function SourceBadge({ source }: { source: "linkedin" | "database" }) {
  return source === "linkedin" ? (
    <Badge variant="outline" className="gap-1 border-sky-500/30 bg-sky-500/10 text-[10px] uppercase tracking-wider text-sky-300">
      <Globe className="h-2.5 w-2.5" /> LinkedIn
    </Badge>
  ) : (
    <Badge variant="outline" className="gap-1 border-violet-500/30 bg-violet-500/10 text-[10px] uppercase tracking-wider text-violet-300">
      <Database className="h-2.5 w-2.5" /> Database
    </Badge>
  );
}

function OtwBadge({
  status,
  evidence,
}: {
  status: BackendFindTalentCandidate["open_to_work_status"];
  evidence: string | null;
}) {
  if (status === "verified") {
    return (
      <Badge
        variant="outline"
        className="gap-1 border-emerald-500/40 bg-emerald-500/10 text-[10px] font-semibold uppercase tracking-wider text-emerald-300"
        title={evidence || "Public 'Open to work' badge found on their LinkedIn profile."}
      >
        <BriefcaseBusiness className="h-2.5 w-2.5" /> Open to work
      </Badge>
    );
  }
  if (status === "not_detected") {
    return (
      <Badge
        variant="outline"
        className="gap-1 border-border/50 bg-muted/20 text-[10px] uppercase tracking-wider text-muted-foreground"
        title="No public Open-to-Work badge found (they may have it set to recruiters-only, which a standard account can't see)."
      >
        OTW not detected
      </Badge>
    );
  }
  return null; // unverified — don't show a badge
}

function ResultCard({ row, index }: { row: BackendFindTalentCandidate; index: number }) {
  const importMut = useImportExternalCandidate();
  const [imported, setImported] = useState(
    row.import_status === "imported" || row.import_status === "in_database",
  );
  const [importedId, setImportedId] = useState<string | null>(
    row.imported_candidate_id ?? row.candidate_id ?? null,
  );

  const onImport = async () => {
    if (!row.external_candidate_id) return;
    try {
      const res = await importMut.mutateAsync(row.external_candidate_id);
      setImported(true);
      setImportedId(res.candidate_id);
    } catch {
      /* surfaced via button disabled state */
    }
  };

  return (
    <motion.article
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.03 }}
      className={cn(
        "glass gradient-border rounded-2xl p-5 space-y-3",
        row.open_to_work && "ring-1 ring-emerald-500/30",
      )}
    >
      <header className="flex flex-wrap items-center gap-2">
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-[11px] font-bold text-primary">
          {row.rank}
        </span>
        <h3 className="font-heading text-[14px] font-bold text-foreground">
          {row.full_name || "Unnamed candidate"}
        </h3>
        <ScorePill value={row.score} />
        <OtwBadge status={row.open_to_work_status} evidence={row.open_to_work_evidence} />
        <SourceBadge source={row.source} />
      </header>

      {(row.current_title || row.headline) && (
        <p className="text-[12px] text-muted-foreground">
          {row.current_title || row.headline}
          {row.current_company ? ` · ${row.current_company}` : ""}
        </p>
      )}
      {row.location && (
        <p className="flex items-center gap-1 text-[11px] text-muted-foreground/80">
          <MapPin className="h-3 w-3" /> {row.location}
        </p>
      )}

      <section>
        <p className="text-[11px] font-semibold uppercase tracking-wide text-primary/80">
          Why this match
        </p>
        <p className="mt-1 text-[13px] leading-relaxed text-foreground/90">
          {row.explanation || "Ranked by the sourcing agent against the target role."}
        </p>
      </section>

      {row.matched_skills.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {row.matched_skills.map((s, i) => (
            <Badge key={i} variant="outline" className="border-emerald-500/30 bg-emerald-500/5 text-[10px] text-emerald-300">
              {s}
            </Badge>
          ))}
        </div>
      )}
      {row.missing_skills.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {row.missing_skills.map((s, i) => (
            <Badge key={i} variant="outline" className="border-amber-500/30 bg-amber-500/5 text-[10px] text-amber-300">
              missing: {s}
            </Badge>
          ))}
        </div>
      )}

      <footer className="flex flex-wrap items-center gap-2 pt-1">
        {row.profile_url && (
          <Button asChild size="sm" variant="ghost" className="text-xs">
            <a href={row.profile_url} target="_blank" rel="noreferrer">
              <ExternalLink className="h-3.5 w-3.5" /> View on LinkedIn
            </a>
          </Button>
        )}
        {importedId && (
          <Button asChild size="sm" variant="ghost" className="text-xs">
            <Link href={`/candidates/${importedId}`}>
              <Users className="h-3.5 w-3.5" /> View profile
            </Link>
          </Button>
        )}
        {row.source === "linkedin" && !imported && (
          <Button
            size="sm"
            variant="outline"
            className="text-xs"
            disabled={importMut.isPending || !row.external_candidate_id}
            onClick={onImport}
          >
            {importMut.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <UserPlus className="h-3.5 w-3.5" />
            )}
            Import to database
          </Button>
        )}
        {imported && (
          <span className="flex items-center gap-1 text-[11px] text-emerald-400">
            <CheckCircle2 className="h-3.5 w-3.5" />
            {row.source === "database" ? "In your database" : "Imported"}
          </span>
        )}
      </footer>
    </motion.article>
  );
}

export function FindTalentPanel() {
  const [query, setQuery] = useState("");
  const [source, setSource] = useState<FindTalentSource>("linkedin");
  const [jobId, setJobId] = useState<string>("");
  const [count, setCount] = useState(8);
  const [location, setLocation] = useState("");
  const [verifyOtw, setVerifyOtw] = useState(true);
  const [result, setResult] = useState<BackendFindTalentResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const { data: jobs = [] } = useJobs({ limit: 100 });
  const findTalent = useFindTalent();

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (!query.trim()) {
      setErr("Enter a search query first (e.g. a role or skills).");
      return;
    }
    setResult(null);
    findTalent.mutate(
      {
        query: query.trim(),
        source,
        job_id: jobId || null,
        count,
        location: location.trim() || null,
        verify_open_to_work: verifyOtw,
      },
      {
        onSuccess: (data) => setResult(data),
        onError: (e) =>
          setErr(e instanceof Error ? e.message : "Find Talent search failed."),
      },
    );
  };

  const results = result?.results ?? [];
  const showEmpty = result !== null && results.length === 0 && !findTalent.isPending;
  const otwCount = results.filter((r) => r.open_to_work).length;

  return (
    <div className="space-y-5">
      <div className="flex items-start gap-3 rounded-xl border border-border/40 bg-muted/20 p-3">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
          <Sparkles className="h-3.5 w-3.5" />
        </div>
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-primary/80">
            Find Talent
          </p>
          <p className="mt-0.5 text-[12px] text-muted-foreground">
            Paste a full role brief — requirements and skills. The agent distills
            a LinkedIn search, verifies each candidate&apos;s Open-to-Work badge,
            pulls their real skills, and ranks them against your requirements —
            Open-to-Work first.
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
            Search query · requirements &amp; skills
          </label>
          <textarea
            rows={5}
            required
            maxLength={6000}
            placeholder={
              "Describe the role, requirements and must-have skills — be as detailed as you like.\n\n" +
              "e.g. Senior Machine Learning Engineer. 5+ yrs building production ML. Strong Python, " +
              "PyTorch, NLP/LLMs, RAG, vector databases. Experience deploying models on AWS/GCP with " +
              "Docker & CI/CD. Bonus: MLOps, model monitoring, distributed training."
            }
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="mt-1 w-full resize-y rounded-lg border border-border/40 bg-background px-3 py-2 text-[13px] leading-relaxed text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/40"
          />
          <p className="mt-1 text-[11px] text-muted-foreground/70">
            {query.length.toLocaleString()} / 6,000 — the agent distills a concise
            LinkedIn search from this and uses the full text for semantic ranking.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Sources
            </label>
            <select
              value={source}
              onChange={(e) => setSource(e.target.value as FindTalentSource)}
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            >
              {SOURCE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Target job (rank against)
            </label>
            <select
              value={jobId}
              onChange={(e) => setJobId(e.target.value)}
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            >
              <option value="">(no job — rank against the query)</option>
              {jobs.map((j) => (
                <option key={String(j.id)} value={String(j.id)}>
                  {j.title}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Location (optional)
            </label>
            <input
              type="text"
              placeholder="e.g. Cairo, Remote"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground/40"
            />
          </div>
          <div>
            <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Number of results
            </label>
            <div className="mt-1 flex items-center gap-2">
              <input
                type="range"
                min={1}
                max={10}
                step={1}
                value={count}
                onChange={(e) => setCount(Number(e.target.value))}
                className="flex-1 accent-primary"
              />
              <span className="w-6 text-center font-mono text-sm font-bold text-foreground">
                {count}
              </span>
            </div>
          </div>
        </div>

        <label className="flex cursor-pointer items-start gap-2 rounded-lg border border-border/40 bg-muted/10 p-3">
          <input
            type="checkbox"
            checked={verifyOtw}
            onChange={(e) => setVerifyOtw(e.target.checked)}
            className="mt-0.5 accent-primary"
          />
          <span className="text-[12px] text-foreground/90">
            <span className="font-semibold">Verify “Open to work”</span> — read each
            candidate&apos;s profile to confirm the public Open-to-Work badge and pull
            their real skills, then sort verified candidates first.
            <span className="block text-[11px] text-muted-foreground/70">
              More accurate but slower (reads each profile). Only publicly-shared
              badges are visible to a standard account. Uncheck for a faster search.
            </span>
          </span>
        </label>

        <div className="flex items-center justify-end pt-1">
          <Button
            type="submit"
            className="gap-2 glow-blue"
            disabled={findTalent.isPending || !query.trim()}
          >
            {findTalent.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                {verifyOtw ? "Verifying & ranking…" : "Sourcing & ranking…"}
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
        {findTalent.isPending && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex items-center gap-2 text-sm text-muted-foreground"
          >
            <Loader2 className="h-4 w-4 animate-spin" />
            {verifyOtw
              ? "Searching LinkedIn, verifying Open-to-Work, and ranking — this can take a minute or two…"
              : "Searching LinkedIn and ranking candidates — this can take up to a minute…"}
          </motion.div>
        )}
      </AnimatePresence>

      {result && !result.provider_available && (
        <div className="flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-[12px] text-amber-200">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            {result.message ||
              "The LinkedIn sourcing provider is unavailable right now. Make sure the LinkedIn MCP server is running and your account is connected."}
          </span>
        </div>
      )}

      {showEmpty && result?.provider_available && (
        <div className="rounded-2xl border border-dashed border-border/40 py-12 text-center">
          <Users className="mx-auto mb-3 h-8 w-8 text-muted-foreground/30" />
          <p className="mx-auto max-w-md text-sm text-muted-foreground">
            {result.message || "No candidates found for this search."}
          </p>
          {!result.message && (
            <p className="mt-1 text-xs text-muted-foreground/60">
              Try a broader query or a different source.
            </p>
          )}
        </div>
      )}

      {results.length > 0 && (
        <section>
          <header className="mb-3 flex flex-wrap items-center gap-2">
            <h2 className="font-heading text-base font-bold text-foreground">
              <Sparkles className="mr-1 inline h-4 w-4 text-primary" />
              Ranked candidates
            </h2>
            <Badge
              variant="outline"
              className="border-emerald-500/30 bg-emerald-500/5 text-[10px] uppercase tracking-wider text-emerald-300"
            >
              <BadgeCheck className="mr-1 h-2.5 w-2.5" />
              {results.length} result{results.length === 1 ? "" : "s"}
            </Badge>
            {verifyOtw && (
              <Badge
                variant="outline"
                className="border-emerald-500/40 bg-emerald-500/10 text-[10px] uppercase tracking-wider text-emerald-300"
              >
                <BriefcaseBusiness className="mr-1 h-2.5 w-2.5" />
                {otwCount} open to work
              </Badge>
            )}
          </header>
          <div className="space-y-3">
            {results.map((row, i) => (
              <ResultCard
                key={row.external_candidate_id || row.candidate_id || `${row.rank}-${i}`}
                row={row}
                index={i}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

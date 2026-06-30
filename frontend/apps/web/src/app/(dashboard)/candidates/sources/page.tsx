"use client";

/**
 * Candidate Sources — consolidated page (fix2.md §2 / §3 / §4 / §5 / §6 / §7 / §8).
 *
 * The single place where a recruiter:
 *   • Toggles which candidate sources feed every job by default
 *   • Uploads a candidate CSV (with optional `cv_url` column)
 *   • Uploads a Job-Fair CSV (same flow, but tagged `source_type=job_fair`)
 *   • Reviews duplicate candidates flagged by the identity-resolution agent
 *   • Browses candidates with incomplete profiles
 *   • Sets default matching parameters that flow into every new job
 *
 * This page replaces three old sidebar entries:
 *   /candidate-sources           → here
 *   /org/cv-ingestion            → CSV upload section below
 *   /org/identity-resolution     → Review Duplicates section below
 */

import { useMemo, useRef, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  AlertTriangle, ArrowRight, CheckCircle2, FileSearch, GitMerge,
  Info, Loader2, Save, Settings2, Sparkles, Telescope, Upload,
  Calendar as JobFairIcon, Globe2, Database, UserPlus2, Users,
  RefreshCw, XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { CandidatesTabBar } from "@/components/features/candidates/CandidatesTabBar";
import {
  useSourceCatalog, useOrgSourceSettings, useUpdateOrgSourceSettings,
  useSourceCounts,
  useDuplicates, useScanDuplicates, useApproveMerge, useRejectMerge,
} from "@/lib/hooks";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type {
  OrgSourceSettings,
  OrgSourceSettingsUpdate,
  SourceTypeKey,
} from "@/lib/api";
import { candidateImportApi } from "@/lib/api";
import { cn } from "@/lib/utils/cn";

const SOURCES: {
  key: SourceTypeKey;
  flag: keyof OrgSourceSettings;
  icon: React.ElementType;
}[] = [
  { key: "paths_profile",    flag: "use_paths_profiles_default",    icon: Globe2 },
  { key: "sourced",          flag: "use_sourced_candidates_default", icon: Telescope },
  { key: "company_uploaded", flag: "use_uploaded_candidates_default", icon: Upload },
  { key: "job_fair",         flag: "use_job_fair_candidates_default", icon: JobFairIcon },
  { key: "ats_import",       flag: "use_ats_candidates_default",      icon: Database },
];

type FormState = Pick<
  OrgSourceSettings,
  | "use_paths_profiles_default"
  | "use_sourced_candidates_default"
  | "use_uploaded_candidates_default"
  | "use_job_fair_candidates_default"
  | "use_ats_candidates_default"
  | "default_top_k"
  | "default_min_profile_completeness"
  | "default_min_evidence_confidence"
>;

// ────────────────────────────────────────────────────────────────────────────
// CSV upload widget — used for both "Company candidates" and "Job-Fair"
// flows.  Same backend endpoint; the only difference is the source_type tag.
// ────────────────────────────────────────────────────────────────────────────

function CsvUploadCard({
  variant,
  title,
  description,
  icon: Icon,
}: {
  variant: "company_uploaded" | "job_fair";
  title: string;
  description: string;
  icon: React.ElementType;
}) {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  type ImportResult = Awaited<ReturnType<typeof candidateImportApi.importCsv>>;
  const [lastResult, setLastResult] = useState<ImportResult | null>(null);

  const mutation = useMutation({
    mutationFn: (csv: File) => candidateImportApi.importCsv(csv, variant),
    onSuccess: (res) => {
      setLastResult(res);
      toast.success(
        `Imported ${res.imported} new · ${res.updated} updated · ${res.failed} failed`,
      );
      // Refresh anything that lists candidates so the new ones show up.
      qc.invalidateQueries({ queryKey: ["applications"] });
      qc.invalidateQueries({ queryKey: ["candidates"] });
      qc.invalidateQueries({ queryKey: ["source-counts"] });
      qc.invalidateQueries({ queryKey: ["incomplete-profiles"] });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Import failed"),
  });

  function onPick() {
    inputRef.current?.click();
  }
  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".csv")) {
      toast.error("Please pick a .csv file");
      return;
    }
    setFileName(f.name);
    mutation.mutate(f);
  }

  return (
    <div className="glass rounded-xl p-5 space-y-3">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="font-heading text-[14px] font-semibold text-foreground">{title}</h3>
          <p className="mt-1 text-[12px] text-muted-foreground">{description}</p>
        </div>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".csv,text/csv"
        className="hidden"
        onChange={onFile}
      />
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          variant="outline"
          className="gap-1.5"
          onClick={onPick}
          disabled={mutation.isPending}
        >
          {mutation.isPending
            ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
            : <Upload className="h-3.5 w-3.5" />}
          {mutation.isPending ? "Uploading…" : "Choose CSV"}
        </Button>
        {fileName && (
          <span className="text-[11px] text-muted-foreground truncate">{fileName}</span>
        )}
      </div>

      {lastResult && (
        <div className="rounded-lg border border-border/40 bg-muted/15 p-3 text-[12px] space-y-1">
          <p className="font-semibold text-foreground">Import summary</p>
          <p className="text-muted-foreground">
            Rows seen: <span className="text-foreground font-mono">{lastResult.total_rows}</span>{" "}
            · Valid: <span className="text-foreground font-mono">{lastResult.valid_rows}</span>{" "}
            · Created: <span className="text-emerald-400 font-mono">{lastResult.imported}</span>{" "}
            · Updated: <span className="text-amber-400 font-mono">{lastResult.updated}</span>{" "}
            · Failed: <span className="text-rose-400 font-mono">{lastResult.failed}</span>
          </p>
          {variant === "job_fair" && lastResult.imported + lastResult.updated > 0 && (
            <p className="text-amber-400 text-[11px] italic">
              Tagged as <code className="font-mono">source_type=job_fair</code> — they
              will show a Job Fair badge in the pipeline.
            </p>
          )}
        </div>
      )}

      <p className="text-[10px] text-muted-foreground">
        CSV columns supported (any subset): <code>full_name, email, phone,
        current_position, skills, years_of_experience, education, linkedin_url,
        github_url, portfolio_url, cv_url, source, notes</code>.  When
        <code>cv_url</code> is set the file is downloaded and parsed through
        the same CV ingestion pipeline used by direct uploads.
      </p>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Review Duplicates section
// ────────────────────────────────────────────────────────────────────────────

function DuplicatesSection() {
  const [statusFilter, setStatusFilter] = useState<string>("pending");
  const { data, isLoading, refetch } = useDuplicates(statusFilter);
  const scan = useScanDuplicates();
  const approve = useApproveMerge();
  const reject = useRejectMerge();

  const items = data?.items ?? [];

  // Group entries by match_reason so the UI shows the three categories the
  // brief asked for: same email / same name / same main position.
  const groups = useMemo(() => {
    const by: Record<string, typeof items> = {};
    for (const d of items) {
      const key = d.match_reason || "other";
      (by[key] ?? (by[key] = [])).push(d);
    }
    return by;
  }, [items]);

  const groupOrder = ["email", "linkedin", "github", "phone", "name", "title", "other"];
  const groupLabels: Record<string, string> = {
    email:    "Same email",
    linkedin: "Same LinkedIn URL",
    github:   "Same GitHub URL",
    phone:    "Same phone number",
    name:     "Same name",
    title:    "Same main position",
    other:    "Other duplicate signal",
  };

  return (
    <div className="glass rounded-xl p-5 space-y-4">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <GitMerge className="h-4 w-4 text-primary" />
          <h2 className="font-heading text-[15px] font-semibold text-foreground">
            Review duplicates
          </h2>
          {data && (
            <Badge variant="outline" className="text-[10px]">
              {items.length} {statusFilter}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-8 rounded-md border border-border/60 bg-muted/30 px-2 text-[12px] text-foreground"
          >
            <option value="pending">Pending review</option>
            <option value="approved">Merged</option>
            <option value="rejected">Marked not-duplicate</option>
            <option value="">All</option>
          </select>
          <Button
            size="sm"
            variant="ghost"
            className="gap-1.5 text-xs"
            onClick={() => scan.mutate(undefined, { onSuccess: () => refetch() })}
            disabled={scan.isPending}
          >
            {scan.isPending
              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
              : <RefreshCw className="h-3.5 w-3.5" />}
            Re-scan
          </Button>
        </div>
      </div>

      {isLoading ? (
        <p className="text-[12px] text-muted-foreground">Loading duplicate suggestions…</p>
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border/40 px-4 py-8 text-center text-[12px] text-muted-foreground">
          <CheckCircle2 className="mx-auto h-6 w-6 text-emerald-400/50 mb-2" />
          No {statusFilter || ""} duplicate suggestions.  Click <strong>Re-scan</strong>{" "}
          to look for new ones.
        </div>
      ) : (
        <div className="space-y-4">
          {groupOrder.map((g) => {
            const rows = groups[g];
            if (!rows || rows.length === 0) return null;
            return (
              <div key={g} className="space-y-2">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60">
                  {groupLabels[g] ?? g} <span className="ml-1 text-muted-foreground/50">({rows.length})</span>
                </p>
                <div className="space-y-2">
                  {rows.map((d) => (
                    <div
                      key={d.id}
                      className="rounded-lg border border-border/40 bg-muted/10 p-3 flex items-center gap-3 flex-wrap"
                    >
                      <div className="flex-1 min-w-0 grid sm:grid-cols-2 gap-2">
                        <Link
                          href={`/candidates/${d.candidate_id_a}`}
                          className="rounded-md border border-border/30 bg-background/40 px-2.5 py-1.5 hover:border-primary/40 transition-colors"
                        >
                          <p className="text-[12px] font-semibold text-foreground truncate">
                            Candidate A
                          </p>
                          <p className="text-[10px] text-muted-foreground font-mono truncate">
                            {d.candidate_id_a.slice(0, 8)}…
                          </p>
                        </Link>
                        <Link
                          href={`/candidates/${d.candidate_id_b}`}
                          className="rounded-md border border-border/30 bg-background/40 px-2.5 py-1.5 hover:border-primary/40 transition-colors"
                        >
                          <p className="text-[12px] font-semibold text-foreground truncate">
                            Candidate B
                          </p>
                          <p className="text-[10px] text-muted-foreground font-mono truncate">
                            {d.candidate_id_b.slice(0, 8)}…
                          </p>
                        </Link>
                      </div>
                      <div className="flex flex-col items-end gap-1 shrink-0">
                        {d.match_value && (
                          <span className="text-[10px] text-muted-foreground truncate max-w-[180px]">
                            {d.match_value}
                          </span>
                        )}
                        {d.confidence != null && (
                          <span className="text-[10px] text-muted-foreground">
                            confidence: {Math.round(d.confidence * 100)}%
                          </span>
                        )}
                      </div>
                      {statusFilter === "pending" && (
                        <div className="flex items-center gap-1.5">
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 gap-1 text-[11px] text-emerald-400 border-emerald-500/20 hover:bg-emerald-500/10"
                            disabled={approve.isPending}
                            onClick={() => approve.mutate({ id: d.id })}
                          >
                            <CheckCircle2 className="h-3 w-3" /> Merge
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 gap-1 text-[11px] text-muted-foreground"
                            disabled={reject.isPending}
                            onClick={() => reject.mutate({ id: d.id })}
                          >
                            <XCircle className="h-3 w-3" /> Not a duplicate
                          </Button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Incomplete Profiles section
// ────────────────────────────────────────────────────────────────────────────

function IncompleteProfilesSection() {
  const { data, isLoading } = useQuery({
    queryKey: ["incomplete-profiles"],
    queryFn: () => candidateImportApi.listIncomplete(100),
  });
  const items = data?.items ?? [];

  return (
    <div className="glass rounded-xl p-5 space-y-4">
      <div className="flex items-center gap-2">
        <FileSearch className="h-4 w-4 text-primary" />
        <h2 className="font-heading text-[15px] font-semibold text-foreground">
          Incomplete profiles
        </h2>
        {data && (
          <Badge variant="outline" className="text-[10px]">{items.length} need attention</Badge>
        )}
      </div>
      <p className="text-[12px] text-muted-foreground">
        Only candidates with missing important fields appear here — those whose
        profile is already complete are hidden.
      </p>

      {isLoading ? (
        <p className="text-[12px] text-muted-foreground">Scanning candidate database…</p>
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-dashed border-emerald-500/30 bg-emerald-500/5 px-4 py-6 text-center text-[12px] text-emerald-400/90">
          <CheckCircle2 className="mx-auto h-6 w-6 mb-2" />
          Every candidate profile is complete.
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((c) => (
            <Link
              key={c.candidate_id}
              href={`/candidates/${c.candidate_id}`}
              className="block rounded-lg border border-border/40 bg-muted/10 p-3 hover:border-primary/40 transition-colors"
            >
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] font-semibold text-foreground truncate">
                    {c.name || "Unnamed candidate"}
                  </p>
                  <p className="text-[11px] text-muted-foreground truncate">
                    {[c.email, c.current_title].filter(Boolean).join(" · ") || "—"}
                    {c.source ? <> · <span className="italic">{c.source}</span></> : null}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <p className={cn(
                    "font-mono text-sm font-bold",
                    c.completion >= 75 ? "text-emerald-400"
                    : c.completion >= 50 ? "text-amber-400"
                    : "text-rose-400",
                  )}>{c.completion}%</p>
                  <p className="text-[10px] text-muted-foreground">complete</p>
                </div>
              </div>
              <div className="mt-2 flex flex-wrap gap-1">
                {c.missing.map((m) => (
                  <span
                    key={m}
                    className="rounded-full bg-rose-500/10 border border-rose-500/20 px-2 py-0.5 text-[10px] text-rose-400"
                  >
                    Missing: {m}
                  </span>
                ))}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Main page
// ────────────────────────────────────────────────────────────────────────────

export default function CandidateSourcesPage() {
  const catalog = useSourceCatalog();
  const settings = useOrgSourceSettings();
  const counts = useSourceCounts();
  const update = useUpdateOrgSourceSettings();

  const initial: FormState | null = useMemo(() => {
    if (!settings.data) return null;
    const s = settings.data;
    return {
      use_paths_profiles_default: s.use_paths_profiles_default,
      use_sourced_candidates_default: s.use_sourced_candidates_default,
      use_uploaded_candidates_default: s.use_uploaded_candidates_default,
      use_job_fair_candidates_default: s.use_job_fair_candidates_default,
      use_ats_candidates_default: s.use_ats_candidates_default,
      default_top_k: s.default_top_k,
      default_min_profile_completeness: s.default_min_profile_completeness,
      default_min_evidence_confidence: s.default_min_evidence_confidence,
    };
  }, [settings.data]);

  const [draft, setDraft] = useState<FormState | null>(null);
  const [savedTick, setSavedTick] = useState(false);
  const form = draft ?? initial;

  const dirty = useMemo(() => {
    if (!draft || !initial) return false;
    const keys = Object.keys(initial) as (keyof FormState)[];
    return keys.some((k) => draft[k] !== initial[k]);
  }, [draft, initial]);

  const onToggle = (flag: keyof FormState, value: boolean) => {
    const base = draft ?? initial;
    if (!base) return;
    setDraft({ ...base, [flag]: value });
  };
  const onNumber = (flag: keyof FormState, value: number) => {
    const base = draft ?? initial;
    if (!base) return;
    setDraft({ ...base, [flag]: value });
  };
  const onSave = async () => {
    if (!form) return;
    const payload: OrgSourceSettingsUpdate = { ...form };
    await update.mutateAsync(payload);
    setDraft(null);
    setSavedTick(true);
    setTimeout(() => setSavedTick(false), 2000);
    toast.success("Default matching parameters saved");
  };

  const loading =
    catalog.isLoading || settings.isLoading || counts.isLoading || form === null;
  const fatal = settings.isError;

  const cards = useMemo(() => {
    if (!form || !catalog.data) return [];
    const labels = Object.fromEntries(
      catalog.data.sources.map((s) => [s.source_type, s.label]),
    );
    const descs = Object.fromEntries(
      catalog.data.sources.map((s) => [s.source_type, s.description]),
    );
    const countMap = Object.fromEntries(
      counts.data?.counts.map((c) => [c.source_type, c.count]) ?? [],
    );
    return SOURCES.map((s) => ({
      ...s,
      label: labels[s.key] ?? s.key,
      description: descs[s.key] ?? "",
      count: countMap[s.key] ?? 0,
      enabled: !!form[s.flag as keyof FormState],
    }));
  }, [form, catalog.data, counts.data]);

  return (
    <div className="h-full overflow-y-auto">
      {/* Page header with tab bar */}
      <div className="border-b border-border/50 bg-background/60 backdrop-blur-sm px-6 py-4">
        <div className="flex items-center justify-between gap-4 mb-3">
          <div>
            <h1 className="font-heading text-xl font-bold tracking-tight text-foreground">
              Candidates
            </h1>
            <p className="text-sm text-muted-foreground">
              Control where candidates come from across every job.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {dirty && (
              <Badge variant="outline" className="text-[10px] border-amber-500/30 text-amber-400">
                Unsaved
              </Badge>
            )}
            {savedTick && (
              <Badge variant="outline" className="text-[10px] border-emerald-500/30 text-emerald-400 gap-1">
                <CheckCircle2 className="h-3 w-3" /> Saved
              </Badge>
            )}
            <Button size="sm" onClick={onSave} disabled={!dirty || update.isPending} className="gap-2">
              {update.isPending
                ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                : <Save className="h-3.5 w-3.5" />}
              Save defaults
            </Button>
          </div>
        </div>
        <CandidatesTabBar />
      </div>

      <div className="p-6 space-y-6 max-w-5xl">
        {loading && !fatal && (
          <div className="glass rounded-xl p-6 flex items-center gap-3 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading source settings…
          </div>
        )}

        {fatal && (
          <div className="glass rounded-2xl p-6 space-y-3 border border-amber-500/30 bg-amber-500/5">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-400" />
              <h2 className="text-base font-semibold text-foreground">
                Source settings backend not reachable
              </h2>
            </div>
            <p className="text-sm text-muted-foreground">
              Toggles are disabled until the source-settings backend is reachable.
            </p>
          </div>
        )}

        {!loading && !fatal && form && (
          <>
            {/* ── Source toggles ──────────────────────────────────── */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {cards.map((c, i) => {
                const Icon = c.icon;
                return (
                  <motion.div
                    key={c.key}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.04 * i }}
                    className={cn(
                      "glass rounded-xl p-5 space-y-3 transition-colors",
                      !c.enabled && "opacity-70",
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-3">
                        <div className={cn(
                          "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
                          c.enabled ? "bg-primary/10 text-primary" : "bg-muted/30 text-muted-foreground",
                        )}>
                          <Icon className="h-4 w-4" />
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <h3 className="font-heading text-[14px] font-semibold text-foreground">
                              {c.label}
                            </h3>
                            <Badge variant="outline" className="text-[10px] font-mono">
                              {c.count} candidate{c.count === 1 ? "" : "s"}
                            </Badge>
                          </div>
                          <p className="mt-1 text-[12px] text-muted-foreground">
                            {c.description}
                          </p>
                        </div>
                      </div>
                      <Switch
                        checked={c.enabled}
                        onCheckedChange={(v) => onToggle(c.flag as keyof FormState, v)}
                      />
                    </div>
                  </motion.div>
                );
              })}
            </div>

            {/* ── Bring in more candidates: CSV upload widgets ────── */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <CsvUploadCard
                variant="company_uploaded"
                title="Upload candidate CSV"
                description="Bulk import candidates with optional cv_url column.  CV links are downloaded + parsed automatically and merged into the candidate profile."
                icon={Upload}
              />
              <CsvUploadCard
                variant="job_fair"
                title="Upload Job-Fair CSV"
                description="Same flow as the candidate CSV — but every row is tagged source_type=job_fair so they appear with a Job Fair badge in the pipeline."
                icon={JobFairIcon}
              />
            </div>

            {/* ── Default matching parameters ─────────────────────── */}
            <div className="glass rounded-xl p-5 space-y-4">
              <div className="flex items-center gap-2">
                <Settings2 className="h-4 w-4 text-primary" />
                <h2 className="font-heading text-[15px] font-semibold text-foreground">
                  Default matching parameters
                </h2>
              </div>
              <p className="text-[12px] text-muted-foreground">
                Applied to every new job&apos;s candidate pool.  Saved per
                organization — every recruiter in the org sees the same values.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="space-y-1.5">
                  <Label className="text-[11px] uppercase tracking-wider text-muted-foreground">
                    Top K candidates
                  </Label>
                  <Input
                    type="number"
                    min={1}
                    max={500}
                    value={form.default_top_k}
                    onChange={(e) => onNumber("default_top_k", Math.max(1, Math.min(500, +e.target.value || 1)))}
                    className="h-9"
                  />
                  <p className="text-[10px] text-muted-foreground">
                    How many candidates the screening agent returns per job.
                  </p>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-[11px] uppercase tracking-wider text-muted-foreground">
                    Min profile completeness
                  </Label>
                  <Input
                    type="number"
                    min={0}
                    max={100}
                    value={form.default_min_profile_completeness}
                    onChange={(e) => onNumber("default_min_profile_completeness", Math.max(0, Math.min(100, +e.target.value || 0)))}
                    className="h-9"
                  />
                  <p className="text-[10px] text-muted-foreground">
                    0–100. Candidates below this are excluded from the pool.
                  </p>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-[11px] uppercase tracking-wider text-muted-foreground">
                    Min evidence confidence
                  </Label>
                  <Input
                    type="number"
                    min={0}
                    max={100}
                    value={form.default_min_evidence_confidence}
                    onChange={(e) => onNumber("default_min_evidence_confidence", Math.max(0, Math.min(100, +e.target.value || 0)))}
                    className="h-9"
                  />
                  <p className="text-[10px] text-muted-foreground">
                    0–100.  Candidates below this confidence are excluded.
                  </p>
                </div>
              </div>
            </div>

            {/* ── Review Duplicates ──────────────────────────────── */}
            <DuplicatesSection />

            {/* ── Incomplete Profiles ────────────────────────────── */}
            <IncompleteProfilesSection />

            {/* ── Outbound sourcing / shortcuts ──────────────────── */}
            <div className="glass rounded-xl p-5 space-y-3">
              <div className="flex items-center gap-2">
                <UserPlus2 className="h-4 w-4 text-primary" />
                <h2 className="font-heading text-[15px] font-semibold text-foreground">
                  Other ways to bring in candidates
                </h2>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <Link
                  href="/sourcing"
                  className="group flex items-start gap-3 rounded-lg border border-border/40 bg-background/40 px-3.5 py-3 transition-all hover:border-primary/40 hover:bg-primary/5"
                >
                  <Telescope className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground group-hover:text-primary" />
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-semibold text-foreground">Run outbound sourcing</p>
                    <p className="text-[11px] text-muted-foreground">Discover candidates on external platforms.</p>
                  </div>
                  <ArrowRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground/40 group-hover:text-primary" />
                </Link>
                <Link
                  href="/candidates"
                  className="group flex items-start gap-3 rounded-lg border border-border/40 bg-background/40 px-3.5 py-3 transition-all hover:border-primary/40 hover:bg-primary/5"
                >
                  <Users className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground group-hover:text-primary" />
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-semibold text-foreground">Browse PATHS profiles</p>
                    <p className="text-[11px] text-muted-foreground">Candidates with PATHS accounts who fit your jobs.</p>
                  </div>
                  <ArrowRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground/40 group-hover:text-primary" />
                </Link>
              </div>
            </div>

            {/* ── Info footer ────────────────────────────────────── */}
            <div className="glass rounded-xl p-5 space-y-2 border border-primary/15 bg-primary/5">
              <div className="flex items-center gap-2">
                <Info className="h-4 w-4 text-primary" />
                <h2 className="text-[13px] font-semibold text-foreground">
                  How candidate pools are built
                </h2>
              </div>
              <p className="text-[12px] text-muted-foreground leading-relaxed">
                When you create a job, the platform copies these defaults into
                the job&apos;s pool config.  The Candidate Pool Builder fetches
                candidates only from sources you have enabled, applies tenant
                isolation, deduplicates by email/phone, and excludes candidates
                whose profile completeness or evidence confidence is below the
                minimums above.  The matching agent then ranks the eligible pool.
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

"use client";

import { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import Link from "next/link";
import {
  Search, MapPin, Briefcase, Users, SlidersHorizontal, X,
  Clock, ArrowRight, Loader2, CheckCircle2, AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { usePublicJobs, useApplyToJob } from "@/lib/hooks";
import { useAuthStore } from "@/lib/stores/auth.store";
import { ApiError } from "@/lib/api/client";
import { cn } from "@/lib/utils/cn";

/* ─── Types & constants ────────────────────────────────────────────────── */

const workModeColors = {
  remote: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  hybrid: "border-amber-500/30 bg-amber-500/10 text-amber-400",
  onsite: "border-blue-500/30 bg-blue-500/10 text-blue-400",
};

const levelColors = {
  Junior: "border-slate-500/30 bg-slate-500/10 text-slate-400",
  Mid:    "border-primary/30 bg-primary/10 text-primary",
  Senior: "border-violet-500/30 bg-violet-500/10 text-violet-400",
  Lead:   "border-amber-500/30 bg-amber-500/10 text-amber-400",
};

const workModes = ["All", "Remote", "Hybrid", "Onsite"];
const levels    = ["All", "Junior", "Mid", "Senior", "Lead"];

/* ─── Apply button — the real fix ──────────────────────────────────────── */

type ApplyState = "idle" | "loading" | "success" | "already_applied" | "wrong_role" | "error";

function ApplyButton({ jobId, applicationMode, externalApplyUrl }: { jobId: string; applicationMode: string; externalApplyUrl: string | null }) {
  const router  = useRouter();
  const { isAuthenticated, _hasHydrated, user } = useAuthStore();
  const { mutateAsync: applyToJob } = useApplyToJob();
  const [applyState, setApplyState] = useState<ApplyState>("idle");
  const [errorMsg,   setErrorMsg]   = useState("");

  /* ── External job — direct redirect ─── */
  if (applicationMode === "external_redirect" && externalApplyUrl) {
    return (
      <Button size="sm" className="mt-3 gap-1.5" variant="outline" asChild>
        <a href={externalApplyUrl} target="_blank" rel="noopener noreferrer">
          Apply externally <ArrowRight className="h-3.5 w-3.5" />
        </a>
      </Button>
    );
  }

  /* ── Step 1: still hydrating from localStorage ─── */
  if (!_hasHydrated) {
    return (
      <Button size="sm" disabled className="mt-3 gap-1.5 opacity-60">
        <Loader2 className="h-3.5 w-3.5 animate-spin" /> Apply
      </Button>
    );
  }

  /* ── Step 2: not authenticated — preserve job intent, go to signup ─── */
  if (!isAuthenticated) {
    return (
      <Button size="sm" className="mt-3 gap-1.5 glow-blue" asChild>
        <Link href={`/candidate-signup?redirectTo=/careers&jobId=${jobId}`}>
          Apply <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </Button>
    );
  }

  /* ── Step 3: wrong role (recruiter / org member) ─── */
  const isCandidate =
    user?.accountType === "candidate" || user?.role === "candidate";
  if (!isCandidate) {
    return (
      <Button size="sm" variant="outline" disabled className="mt-3 gap-1.5 cursor-not-allowed opacity-60">
        Recruiter account
      </Button>
    );
  }

  /* ── Terminal states ─── */
  if (applyState === "success") {
    return (
      <div className="mt-3 flex items-center gap-1.5 text-[12px] font-semibold text-emerald-500">
        <CheckCircle2 className="h-3.5 w-3.5 shrink-0" /> Application sent!
      </div>
    );
  }

  if (applyState === "already_applied") {
    return (
      <div className="mt-3 flex items-center gap-1.5 text-[12px] font-semibold text-emerald-500">
        <CheckCircle2 className="h-3.5 w-3.5 shrink-0" /> Already applied
      </div>
    );
  }

  if (applyState === "error") {
    return (
      <div className="mt-3 space-y-1.5">
        <div className="flex items-start gap-1.5 text-[11px] text-destructive">
          <AlertCircle className="mt-0.5 h-3 w-3 shrink-0" />
          <span>{errorMsg}</span>
        </div>
        <Button
          size="sm"
          variant="outline"
          className="h-7 gap-1 text-xs"
          onClick={() => setApplyState("idle")}
        >
          Retry
        </Button>
      </div>
    );
  }

  /* ── Step 4: submit application ─── */
  const handleApply = async () => {
    setApplyState("loading");
    setErrorMsg("");
    try {
      await applyToJob(jobId);
      setApplyState("success");
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setApplyState("already_applied");
          return;
        }
        if (err.status === 401 || err.status === 403) {
          // Session expired or token invalid — send to login preserving intent
          router.push(`/login?next=/careers`);
          return;
        }
        if (err.status === 404 && err.detail.includes("profile")) {
          // Profile not set up — redirect to profile completion
          router.push("/candidate/profile/edit?redirectTo=/careers");
          return;
        }
      }
      setApplyState("error");
      setErrorMsg(
        err instanceof Error ? err.message : "Could not submit application. Please try again.",
      );
    }
  };

  return (
    <Button
      size="sm"
      className="mt-3 gap-1.5 glow-blue"
      onClick={handleApply}
      disabled={applyState === "loading"}
    >
      {applyState === "loading" ? (
        <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Applying…</>
      ) : (
        <>Apply <ArrowRight className="h-3.5 w-3.5" /></>
      )}
    </Button>
  );
}

/* ─── Page ──────────────────────────────────────────────────────────────── */

export default function JobsPage() {
  const [query,    setQuery]    = useState("");
  const [workMode, setWorkMode] = useState("All");
  const [level,    setLevel]    = useState("All");
  const { data: jobs = [] } = usePublicJobs();

  const filtered = useMemo(() => {
    return jobs.filter((job) => {
      const q         = query.toLowerCase();
      const matchesQ  = !q || job.title.toLowerCase().includes(q) || job.company.toLowerCase().includes(q) || job.skills.some((s) => s.toLowerCase().includes(q));
      const matchesMode  = workMode === "All" || job.workMode === workMode.toLowerCase();
      const matchesLevel = level   === "All" || job.level    === level;
      return matchesQ && matchesMode && matchesLevel;
    });
  }, [query, workMode, level]);

  const hasFilters = query || workMode !== "All" || level !== "All";

  return (
    <div className="min-h-screen px-6 py-16">
      <div className="mx-auto max-w-5xl">

        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mb-10 text-center">
          <Badge variant="outline" className="mb-4 border-primary/25 bg-primary/8 text-primary">
            Open Positions
          </Badge>
          <h1 className="font-heading text-4xl font-bold text-foreground">
            Find your next opportunity
          </h1>
          <p className="mt-3 text-muted-foreground">
            {jobs.length} open positions across MENA and globally.{" "}
            <Link href="/candidate-signup" className="text-primary hover:underline">
              Create a profile to apply.
            </Link>
          </p>
        </motion.div>

        {/* Search + filters */}
        <div className="mb-8 space-y-4">
          <div className="relative">
            <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search by title, company, or skill…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="h-12 pl-10 pr-4 text-sm"
            />
            {query && (
              <button
                onClick={() => setQuery("")}
                className="absolute right-3.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-1.5">
              <SlidersHorizontal className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Work Mode
              </span>
            </div>
            {workModes.map((m) => (
              <button
                key={m}
                onClick={() => setWorkMode(m)}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs font-medium transition-all",
                  workMode === m
                    ? "border-primary/40 bg-primary/15 text-primary"
                    : "border-border/50 text-muted-foreground hover:border-border hover:text-foreground",
                )}
              >
                {m}
              </button>
            ))}
            <div className="ml-4 flex items-center gap-1.5">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Level
              </span>
            </div>
            {levels.map((l) => (
              <button
                key={l}
                onClick={() => setLevel(l)}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs font-medium transition-all",
                  level === l
                    ? "border-primary/40 bg-primary/15 text-primary"
                    : "border-border/50 text-muted-foreground hover:border-border hover:text-foreground",
                )}
              >
                {l}
              </button>
            ))}
            {hasFilters && (
              <button
                onClick={() => { setQuery(""); setWorkMode("All"); setLevel("All"); }}
                className="ml-auto flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
              >
                <X className="h-3 w-3" /> Clear all
              </button>
            )}
          </div>
        </div>

        {/* Results count */}
        <p className="mb-5 text-sm text-muted-foreground">
          {filtered.length} {filtered.length === 1 ? "position" : "positions"} found
        </p>

        {/* Job cards */}
        <div className="space-y-4">
          {filtered.map((job, i) => (
            <motion.div
              key={job.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
              className="glass gradient-border rounded-2xl p-6 transition-all hover:ring-1 hover:ring-primary/20"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    <h2 className="font-heading text-[16px] font-bold text-foreground">{job.title}</h2>
                    <Badge
                      variant="outline"
                      className={cn("text-[10px]", levelColors[job.level as keyof typeof levelColors] ?? "")}
                    >
                      {job.level}
                    </Badge>
                    <Badge
                      variant="outline"
                      className={cn("text-[10px]", workModeColors[job.workMode as keyof typeof workModeColors] ?? "")}
                    >
                      {job.workMode}
                    </Badge>
                    {job.applicationMode === "external_redirect" && (
                      <Badge variant="outline" className="text-[10px] border-amber-500/30 bg-amber-500/10 text-amber-400">
                        External
                      </Badge>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center gap-4 text-[12px] text-muted-foreground">
                    <span className="flex items-center gap-1.5">
                      <Briefcase className="h-3 w-3" />{job.company}
                    </span>
                    <span className="flex items-center gap-1.5">
                      <MapPin className="h-3 w-3" />{job.location}
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Users className="h-3 w-3" />{job.applicants} applicants
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Clock className="h-3 w-3" />{job.postedAt}
                    </span>
                  </div>

                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {job.skills.map((s) => (
                      <span key={s} className="evidence-pill">{s}</span>
                    ))}
                  </div>
                </div>

                <div className="shrink-0 text-right">
                  <p className="text-[13px] font-semibold text-foreground">{job.salary}</p>
                  <ApplyButton jobId={job.id} applicationMode={job.applicationMode} externalApplyUrl={job.externalApplyUrl} />
                </div>
              </div>
            </motion.div>
          ))}

          {filtered.length === 0 && (
            <div className="rounded-2xl border border-dashed border-border/40 p-16 text-center">
              <Search className="mx-auto mb-3 h-10 w-10 text-muted-foreground/30" />
              <p className="text-sm font-medium text-muted-foreground">No jobs match your filters</p>
              <button
                onClick={() => { setQuery(""); setWorkMode("All"); setLevel("All"); }}
                className="mt-3 text-xs text-primary hover:underline"
              >
                Clear all filters
              </button>
            </div>
          )}
        </div>

        {/* Bottom CTA */}
        <div className="glass gradient-border mt-16 rounded-2xl p-8 text-center">
          <h3 className="font-heading text-xl font-bold text-foreground">Don&apos;t see the right role?</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Create a profile and we&apos;ll match you automatically when new roles appear.
          </p>
          <Button className="mt-5 gap-2 glow-blue" asChild>
            <Link href="/candidate-signup">
              Create Profile <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}

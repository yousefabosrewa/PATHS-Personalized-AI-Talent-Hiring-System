"use client";

/**
 * Candidate Job Description Analysis (fix8&9 Update 1).
 *
 * The candidate pastes a job description; the PATHS agent compares it
 * against their own profile/CV/skills/experience and returns a
 * personalised analysis (fit score, gaps, improvement actions, interview
 * preparation, learning roadmap).
 *
 * Lives under the Candidate Profile area, NOT the organisation pages.
 */

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import {
  FileSearch, Loader2, Sparkles, AlertTriangle, ArrowLeft, BookOpen,
  Lightbulb, Target, ChevronRight, ChevronDown, History,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils/cn";
import { useCandidateJdAnalysis, useCandidateJdAnalyses } from "@/lib/hooks";
import type { BackendJdAnalysisResponse } from "@/lib/api";

function ScoreRing({ value }: { value: number }) {
  const v = Math.max(0, Math.min(100, value));
  const color =
    v >= 70
      ? "border-emerald-400/40 text-emerald-300"
      : v >= 45
        ? "border-amber-400/40 text-amber-300"
        : "border-rose-400/40 text-rose-300";
  return (
    <div className={cn(
      "flex h-20 w-20 shrink-0 items-center justify-center rounded-full border-4 font-heading text-2xl font-bold",
      color,
    )}>
      {v}
    </div>
  );
}

function SkillList({
  label,
  items,
  variant,
}: {
  label: string;
  items: string[];
  variant: "matching" | "missing" | "weak";
}) {
  if (items.length === 0) return null;
  const pillClass =
    variant === "matching"
      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
      : variant === "missing"
        ? "border-rose-500/30 bg-rose-500/10 text-rose-300"
        : "border-amber-500/30 bg-amber-500/10 text-amber-300";
  return (
    <section>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        {label} ({items.length})
      </p>
      <div className="mt-1 flex flex-wrap gap-1">
        {items.map((s, i) => (
          <span
            key={`${s}-${i}`}
            className={cn(
              "rounded-full border px-2 py-0.5 text-[11px] font-medium",
              pillClass,
            )}
          >
            {s}
          </span>
        ))}
      </div>
    </section>
  );
}

function BulletList({
  label,
  items,
  Icon,
  accent,
}: {
  label: string;
  items: string[];
  Icon: typeof Lightbulb;
  accent: string;
}) {
  if (items.length === 0) return null;
  return (
    <section>
      <p className={cn(
        "flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide",
        accent,
      )}>
        <Icon className="h-3.5 w-3.5" />
        {label}
      </p>
      <ul className="mt-1 space-y-1">
        {items.map((it, i) => (
          <li key={i} className="flex gap-1.5 text-[13px] text-foreground/85">
            <ChevronRight className="mt-0.5 h-3 w-3 shrink-0 text-muted-foreground/60" />
            <span>{it}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function AlignmentBlock({ label, text }: { label: string; text: string }) {
  if (!text || !text.trim()) return null;
  return (
    <section>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-primary/80">
        {label}
      </p>
      <p className="mt-1 text-[13px] leading-relaxed text-foreground/90">{text}</p>
    </section>
  );
}

function ResultCard({ data }: { data: BackendJdAnalysisResponse }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass gradient-border rounded-2xl p-6 space-y-5"
    >
      <header className="flex items-start gap-4">
        <ScoreRing value={data.overall_fit_score} />
        <div className="flex-1 min-w-0 space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="font-heading text-base font-bold text-foreground">
              Overall fit
            </h2>
            <Badge variant="outline" className="text-[10px] uppercase tracking-wider text-muted-foreground">
              {data.overall_fit_score}/100
            </Badge>
            {data.used_fallback && (
              <Badge
                variant="outline"
                className="border-amber-500/30 bg-amber-500/5 text-[10px] uppercase tracking-wider text-amber-300"
                title="The AI coach is currently unavailable; this analysis is based on keyword overlap."
              >
                <AlertTriangle className="mr-1 h-2.5 w-2.5" />
                Fallback
              </Badge>
            )}
          </div>
          <p className="text-[13px] leading-relaxed text-foreground/85">
            {data.summary || "No summary returned."}
          </p>
        </div>
      </header>

      <SkillList label="Matching skills"  items={data.matching_skills}  variant="matching" />
      <SkillList label="Missing skills"   items={data.missing_skills}   variant="missing" />
      <SkillList label="Weak signals"     items={data.weak_skills}      variant="weak" />

      <AlignmentBlock label="Experience alignment" text={data.experience_alignment} />
      <AlignmentBlock label="Project alignment"    text={data.project_alignment} />
      <AlignmentBlock label="Education alignment"  text={data.education_alignment} />

      <BulletList
        label="How to qualify for this role"
        items={data.recommended_improvements}
        Icon={Lightbulb}
        accent="text-primary/80"
      />
      <BulletList
        label="Interview preparation"
        items={data.interview_preparation}
        Icon={Target}
        accent="text-emerald-400/80"
      />
      <BulletList
        label="Learning recommendations"
        items={data.learning_recommendations}
        Icon={BookOpen}
        accent="text-sky-400/80"
      />
    </motion.div>
  );
}

function firstLine(text: string): string {
  const t = (text || "").trim().replace(/\s+/g, " ");
  return t.length > 90 ? `${t.slice(0, 90)}…` : t || "Untitled analysis";
}

function ScorePill({ value }: { value: number }) {
  const v = Math.max(0, Math.min(100, value));
  const tone =
    v >= 70 ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
    : v >= 45 ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
    : "border-rose-500/30 bg-rose-500/10 text-rose-300";
  return (
    <span className={cn("inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border text-[12px] font-bold tabular-nums", tone)}>
      {v}
    </span>
  );
}

export default function CandidateJdAnalysisPage() {
  const [jd, setJd] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [pendingExpand, setPendingExpand] = useState(false);

  const analyse = useCandidateJdAnalysis();
  const { data: history, isLoading: histLoading } = useCandidateJdAnalyses();
  const items = history?.items ?? [];

  // After a successful analysis the list refetches; expand the new (top) one
  // and clear the box so it's obvious the new analysis appeared above the rest.
  useEffect(() => {
    if (pendingExpand && items.length > 0) {
      setExpandedId(items[0].id);
      setPendingExpand(false);
      setJd("");
    }
  }, [items, pendingExpand]);

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    const text = jd.trim();
    if (text.length < 30) {
      setErr("Paste at least a paragraph of the job description.");
      return;
    }
    analyse.mutate(
      { job_description_text: text },
      {
        onSuccess: () => setPendingExpand(true),
        onError: (e) => setErr(e instanceof Error ? e.message : "Analysis failed."),
      },
    );
  };

  const onFile = async (f: File | null) => {
    if (!f) return;
    setErr(null);
    try {
      const t = await f.text();
      setJd(t.slice(0, 15000));
    } catch {
      setErr("Could not read that file. Try pasting the text instead.");
    }
  };

  return (
    <div className="min-h-screen px-6 py-8">
      <div className="mx-auto max-w-3xl space-y-6">
        {/* Header */}
        <motion.header
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-start justify-between gap-3 flex-wrap"
        >
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 ring-1 ring-primary/20">
              <FileSearch className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h1 className="font-heading text-2xl font-bold text-foreground">
                Job Description Analysis
              </h1>
              <p className="text-sm text-muted-foreground">
                Paste a job description — PATHS compares it to your profile. Every
                analysis is saved here; click one to see what you wrote and the result.
              </p>
            </div>
          </div>
          <Button asChild variant="ghost" size="sm">
            <Link href="/candidate/profile">
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to profile
            </Link>
          </Button>
        </motion.header>

        {/* Past analyses — newest first; click to expand. */}
        <section className="space-y-3">
          <h2 className="flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
            <History className="h-3.5 w-3.5" /> Your analyses
          </h2>

          {analyse.isPending && (
            <div className="flex items-center gap-2 rounded-xl border border-primary/20 bg-primary/5 px-4 py-3 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Comparing your profile to the job… this usually takes 1–5 minutes. It&apos;ll appear at the top.
            </div>
          )}

          {histLoading ? (
            <div className="rounded-2xl border border-dashed border-border/40 p-6 text-center text-[12px] text-muted-foreground">
              <Loader2 className="mx-auto mb-2 h-5 w-5 animate-spin text-muted-foreground/50" />
              Loading your past analyses…
            </div>
          ) : items.length === 0 ? (
            !analyse.isPending && (
              <div className="rounded-2xl border border-dashed border-border/40 p-6 text-center text-[12px] text-muted-foreground">
                <History className="mx-auto mb-2 h-6 w-6 text-muted-foreground/40" />
                No analyses yet — run one below and it&apos;ll be saved here.
              </div>
            )
          ) : (
            <div className="space-y-3">
              {items.map((it) => {
                const open = expandedId === it.id;
                const score = it.result.overall_fit_score;
                return (
                  <motion.div
                    key={it.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={cn(
                      "glass rounded-2xl overflow-hidden transition-all",
                      open ? "gradient-border ring-1 ring-primary/15" : "border border-border/40",
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => setExpandedId(open ? null : it.id)}
                      className="flex w-full items-center gap-3 p-4 text-left transition-colors hover:bg-muted/20"
                    >
                      <ScorePill value={score} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[13px] font-semibold text-foreground">
                          {firstLine(it.job_description_text)}
                        </p>
                        <p className="text-[11px] text-muted-foreground">
                          {it.created_at ? new Date(it.created_at).toLocaleString() : ""} · Fit {score}/100
                          {it.result.used_fallback ? " · fallback" : ""}
                        </p>
                      </div>
                      <ChevronDown
                        className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")}
                      />
                    </button>
                    {open && (
                      <div className="space-y-4 border-t border-border/30 p-4">
                        <section>
                          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                            What you wrote
                          </p>
                          <p className="mt-1 max-h-48 overflow-y-auto whitespace-pre-wrap rounded-md border border-border/30 bg-muted/10 p-2 text-[12px] text-foreground/80">
                            {it.job_description_text}
                          </p>
                        </section>
                        <ResultCard data={it.result} />
                      </div>
                    )}
                  </motion.div>
                );
              })}
            </div>
          )}
        </section>

        {/* New analysis — under the past conversations. */}
        <motion.form
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          onSubmit={onSubmit}
          className="glass gradient-border rounded-2xl p-6 space-y-4"
        >
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            <h2 className="font-heading text-sm font-bold text-foreground">New analysis</h2>
          </div>
          <div>
            <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Job description
            </label>
            <textarea
              rows={10}
              required
              placeholder="Paste the job description here…"
              value={jd}
              onChange={(e) => setJd(e.target.value)}
              className="mt-1 w-full resize-y rounded-lg border border-border/40 bg-background px-3 py-2 text-[13px] text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/40"
            />
            <p className="mt-1 text-[10px] text-muted-foreground/60">
              {jd.length} characters · min 30 to analyse.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border/50 px-3 py-1.5 text-[12px] hover:bg-muted/20">
              Upload .txt / .md
              <input
                type="file"
                className="hidden"
                accept=".txt,.md,.markdown,text/plain"
                onChange={(e) => onFile(e.target.files?.[0] ?? null)}
              />
            </label>
            <p className="text-[10px] text-muted-foreground/60">Or paste the text above.</p>
            <Button
              type="submit"
              size="sm"
              className="ml-auto gap-1.5 glow-blue"
              disabled={analyse.isPending || jd.trim().length < 30}
            >
              {analyse.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Sparkles className="h-3.5 w-3.5" />
              )}
              Analyse
            </Button>
          </div>

          {err && <p className="text-xs text-rose-400">{err}</p>}
        </motion.form>
      </div>
    </div>
  );
}

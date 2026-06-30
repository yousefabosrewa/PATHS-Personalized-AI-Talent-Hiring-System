"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import { toast } from "sonner";
import {
  ArrowRight, CheckCircle2, Clock, Briefcase, User, FileText,
  TrendingUp, Bell, Zap, Sparkles, ExternalLink, Loader2,
  ChevronDown, Lightbulb, Target, Calendar, Video,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  useCandidateProfile, useCandidateApplications,
  useCandidateMatchingJobs, useExplainJobMatch, useApplyToJob,
  useCandidateInterviews,
} from "@/lib/hooks";
import type {
  BackendMatchingJob, BackendJdAnalysisResponse, BackendCandidateInterview,
} from "@/lib/api";
import type { CandidateProfile } from "@/types/candidate-profile.types";
import { createEmptyCandidateProfile } from "@/lib/candidate/portal-profile";
import { cn } from "@/lib/utils/cn";

const statusColors: Record<string, string> = {
  applied:     "border-slate-500/30 bg-slate-500/10 text-slate-400",
  screening:   "border-primary/30 bg-primary/10 text-primary",
  interview:   "border-amber-500/30 bg-amber-500/10 text-amber-400",
  offered:     "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  rejected:    "border-rose-500/30 bg-rose-500/10 text-rose-400",
  withdrawn:   "border-muted/30 bg-muted/10 text-muted-foreground",
};

const workModeColors: Record<string, string> = {
  remote: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  hybrid: "border-amber-500/30 bg-amber-500/10 text-amber-400",
  onsite: "border-blue-500/30 bg-blue-500/10 text-blue-400",
};

function profileCompletionPct(profile: CandidateProfile) {
  let score = 0;
  if (profile.fullName)       score += 15;
  if (profile.currentTitle)   score += 10;
  if (profile.summary)        score += 10;
  if (profile.email)          score += 10;
  if (profile.education.length > 0) score += 15;
  if (profile.experiences.length > 0) score += 15;
  if (profile.skills.length > 0) score += 10;
  if (profile.cvDocument)     score += 10;
  if (profile.links.linkedin || profile.links.github) score += 5;
  return Math.min(score, 100);
}

// ── Top match card with on-demand AI explanation ──────────────────────────
function MatchJobCard({ job }: { job: BackendMatchingJob }) {
  const [open, setOpen] = useState(false);
  const [explanation, setExplanation] = useState<BackendJdAnalysisResponse | null>(null);
  const explain = useExplainJobMatch();
  const { mutateAsync: applyToJob, isPending: applying } = useApplyToJob();

  const toggleExplain = () => {
    const next = !open;
    setOpen(next);
    if (next && !explanation && !explain.isPending) {
      explain.mutate(job.job_id, {
        onSuccess: (data) => setExplanation(data),
        onError: (e) =>
          toast.error(e instanceof Error ? e.message : "Could not load explanation."),
      });
    }
  };

  const handleApply = async () => {
    try {
      await applyToJob(job.job_id);
      toast.success("Application submitted!");
    } catch (err: unknown) {
      const status = (err as { status?: number })?.status;
      if (status === 409) toast.info("You've already applied to this job.");
      else toast.error("Failed to submit application. Please try again.");
    }
  };

  const scoreColor =
    job.match_score >= 85 ? "text-emerald-400" : "text-primary";

  return (
    <div className="glass gradient-border rounded-2xl p-5">
      <div className="flex items-start gap-4 flex-wrap">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            {job.source_url ? (
              <a
                href={job.source_url}
                target="_blank"
                rel="noreferrer"
                title="Open the original posting on the source site"
                className="group inline-flex items-center gap-1.5 font-heading text-sm font-bold text-foreground hover:text-primary hover:underline"
              >
                {job.title}
                <ExternalLink className="h-3 w-3 opacity-50 group-hover:opacity-100" />
              </a>
            ) : (
              <p className="font-heading text-sm font-bold text-foreground">{job.title}</p>
            )}
            {job.workplace_type && (
              <Badge variant="outline" className={cn("text-[10px]", workModeColors[job.workplace_type] ?? "")}>
                {job.workplace_type}
              </Badge>
            )}
            {job.seniority_level && (
              <Badge variant="outline" className="text-[10px] text-muted-foreground">
                {job.seniority_level}
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            {[job.company_name, job.location_text].filter(Boolean).join(" · ") || "—"}
          </p>
          {job.salary_text && (
            <p className="text-[11px] text-foreground/70 mt-1">{job.salary_text}</p>
          )}
          {job.matched_skills.length > 0 && (
            <p className="mt-1.5 flex flex-wrap items-center gap-1 text-[11px] text-muted-foreground">
              <span className="text-emerald-400/80">Matches your:</span>
              {job.matched_skills.map((s) => (
                <span key={s} className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] text-emerald-300">
                  {s}
                </span>
              ))}
            </p>
          )}
        </div>
        <div className="text-right shrink-0">
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground/60">Match</p>
          <p className={cn("font-heading text-2xl font-bold", scoreColor)}>{job.match_score}%</p>
        </div>
      </div>

      <div className="mt-3 flex items-center gap-2 flex-wrap">
        <Button size="sm" variant="ghost" className="h-8 gap-1.5 px-2 text-xs" onClick={toggleExplain}>
          <Sparkles className="h-3.5 w-3.5 text-primary" />
          Why this match?
          <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")} />
        </Button>
        <div className="ml-auto flex items-center gap-2">
          {job.application_mode === "external_redirect" && job.external_apply_url ? (
            <a href={job.external_apply_url} target="_blank" rel="noreferrer">
              <Button size="sm" variant="outline" className="h-8 gap-1.5 text-xs">
                <ExternalLink className="h-3 w-3" /> Apply
              </Button>
            </a>
          ) : job.already_applied ? (
            <Badge variant="outline" className="border-emerald-500/30 bg-emerald-500/10 text-[10px] text-emerald-400">
              <CheckCircle2 className="mr-1 h-3 w-3" /> Applied
            </Badge>
          ) : (
            <Button size="sm" className="h-8 gap-1.5 text-xs glow-blue" onClick={handleApply} disabled={applying}>
              {applying ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Briefcase className="h-3.5 w-3.5" />}
              Apply Now
            </Button>
          )}
        </div>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-3 border-t border-border/40 pt-3 space-y-3">
              {explain.isPending && (
                <p className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  The PATHS coach is analysing this job against your profile… (up to a minute)
                </p>
              )}
              {explanation && (
                <>
                  <p className="text-[13px] leading-relaxed text-foreground/85">{explanation.summary}</p>
                  {explanation.matching_skills.length > 0 && (
                    <div>
                      <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-400/80">
                        <CheckCircle2 className="h-3 w-3" /> Why you fit
                      </p>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {explanation.matching_skills.slice(0, 10).map((s, i) => (
                          <span key={`${s}-${i}`} className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-300">{s}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {explanation.missing_skills.length > 0 && (
                    <div>
                      <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-amber-400/80">
                        <Target className="h-3 w-3" /> To strengthen
                      </p>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {explanation.missing_skills.slice(0, 8).map((s, i) => (
                          <span key={`${s}-${i}`} className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[11px] text-amber-300">{s}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {explanation.recommended_improvements.length > 0 && (
                    <div>
                      <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-primary/80">
                        <Lightbulb className="h-3 w-3" /> Tips
                      </p>
                      <ul className="mt-1 space-y-1">
                        {explanation.recommended_improvements.slice(0, 3).map((it, i) => (
                          <li key={i} className="text-[12px] text-foreground/80">• {it}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Interview invite card (title + time + join + reminder) ────────────────
const INTERVIEW_TYPE_LABELS: Record<string, string> = {
  hr: "HR Interview",
  technical: "Technical Interview",
  mixed: "Interview",
};

function InterviewInviteCard({ iv }: { iv: BackendCandidateInterview }) {
  const when = iv.scheduled_start_time ? new Date(iv.scheduled_start_time) : null;
  const typeLabel = INTERVIEW_TYPE_LABELS[iv.interview_type] ?? "Interview";
  const title = [iv.job_title, typeLabel].filter(Boolean).join(" — ") || typeLabel;
  const noShow = iv.status === "no_show";

  return (
    <div
      className={`rounded-xl border p-4 ${
        noShow ? "border-red-500/30 bg-red-500/5" : "border-border/40 bg-muted/10"
      }`}
    >
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-heading text-sm font-bold text-foreground">{title}</p>
            {iv.status === "rescheduled" && (
              <Badge variant="outline" className="border-amber-500/30 bg-amber-500/10 text-[10px] text-amber-400">
                Rescheduled
              </Badge>
            )}
            {noShow && (
              <Badge variant="outline" className="border-red-500/30 bg-red-500/10 text-[10px] text-red-400">
                Cancelled — no one joined
              </Badge>
            )}
          </div>
          {iv.company_name && (
            <p className="text-xs text-muted-foreground mt-0.5">{iv.company_name}</p>
          )}
          <p className="mt-1.5 flex items-center gap-1.5 text-[12px] text-foreground/85">
            <Clock className="h-3.5 w-3.5 text-muted-foreground" />
            {when
              ? when.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
              : "Time to be confirmed"}
            {iv.timezone ? ` · ${iv.timezone}` : ""}
          </p>
        </div>
        {noShow ? (
          <Button size="sm" variant="outline" disabled className="gap-1.5 shrink-0">
            <Video className="h-3.5 w-3.5" /> Meeting expired
          </Button>
        ) : iv.meeting_url ? (
          <a href={iv.meeting_url} target="_blank" rel="noreferrer" className="shrink-0">
            <Button size="sm" className="gap-1.5 glow-blue">
              <Video className="h-3.5 w-3.5" /> Join meeting
            </Button>
          </a>
        ) : (
          <Button size="sm" variant="outline" disabled className="gap-1.5 shrink-0">
            <Video className="h-3.5 w-3.5" /> Link coming soon
          </Button>
        )}
      </div>
      {noShow ? (
        <p className="mt-2.5 flex items-center gap-1.5 text-[11px] font-medium text-red-400/90">
          <Bell className="h-3 w-3" /> The interview time passed and no one joined — it is scored 0
          unless the recruiter reschedules it.
        </p>
      ) : (
        <p className="mt-2.5 flex items-center gap-1.5 text-[11px] font-medium text-amber-500/90">
          <Bell className="h-3 w-3" /> Don&apos;t forget to attend this meeting.
        </p>
      )}
    </div>
  );
}

export default function CandidateDashboard() {
  const { data: profile = createEmptyCandidateProfile(), isLoading: profileLoading } = useCandidateProfile();
  const { data: apps = [] } = useCandidateApplications();
  const { data: matches = [], isLoading: matchesLoading } = useCandidateMatchingJobs({ minScore: 70, limit: 5 });
  const { data: interviews = [] } = useCandidateInterviews();
  const completion = profileCompletionPct(profile);
  const [showInterviews, setShowInterviews] = useState(false);

  // Profile Views removed — three meaningful, real metrics only.
  const stats: {
    label: string; value: string | number; Icon: typeof Bell; color: string;
    onClick?: () => void;
  }[] = [
    { label: "Active Applications", value: apps.length,        Icon: Briefcase,  color: "text-primary"     },
    {
      label: "Interview Invites",   value: interviews.length,  Icon: Bell,        color: "text-amber-500",
      onClick: () => setShowInterviews((v) => !v),
    },
    { label: "Profile Completion",  value: `${completion}%`,   Icon: TrendingUp,  color: "text-emerald-500" },
  ];

  return (
    <div className="min-h-screen px-6 py-8">
      <div className="mx-auto max-w-4xl">
        {/* Welcome */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
          <p className="text-sm text-muted-foreground">Welcome back,</p>
          <h1 className="font-heading text-3xl font-bold text-foreground">
            {profileLoading ? "…" : profile.fullName.trim() || "Candidate"}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {[profile.currentTitle, profile.locationText].filter(Boolean).join(" · ") || "—"}
          </p>
        </motion.div>

        {/* Profile completion banner */}
        {completion < 100 && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}
            className="mb-6 glass gradient-border rounded-2xl p-5 flex items-center gap-4"
          >
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10">
              <Zap className="h-5 w-5 text-primary" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-foreground">Your profile is {completion}% complete</p>
              <p className="text-xs text-muted-foreground mt-0.5">Complete your profile to get better match scores and more visibility.</p>
              <div className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-muted/30">
                <div className="h-full bg-primary transition-all duration-700" style={{ width: `${completion}%` }} />
              </div>
            </div>
            <Button size="sm" className="shrink-0 gap-1.5 glow-blue" asChild>
              <Link href="/candidate/profile/edit">Complete <ArrowRight className="h-3.5 w-3.5" /></Link>
            </Button>
          </motion.div>
        )}

        {/* Stats */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
          className="mb-8 grid grid-cols-3 gap-4"
        >
          {stats.map((s) => {
            const inner = (
              <>
                <s.Icon className={cn("mx-auto h-5 w-5 mb-2", s.color)} />
                <p className="font-heading text-2xl font-bold text-foreground">{s.value}</p>
                <p className="text-[11px] text-muted-foreground mt-0.5 flex items-center justify-center gap-1">
                  {s.label}
                  {s.onClick && (
                    <ChevronDown className={cn("h-3 w-3 transition-transform", showInterviews && "rotate-180")} />
                  )}
                </p>
              </>
            );
            return s.onClick ? (
              <button
                key={s.label}
                type="button"
                onClick={s.onClick}
                className="glass rounded-2xl p-4 text-center transition-all hover:ring-1 hover:ring-amber-500/40"
              >
                {inner}
              </button>
            ) : (
              <div key={s.label} className="glass rounded-2xl p-4 text-center">{inner}</div>
            );
          })}
        </motion.div>

        {/* Interview invites panel (toggled by the stat above) */}
        <AnimatePresence>
          {showInterviews && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden"
            >
              <div className="mb-8 glass gradient-border rounded-2xl p-5">
                <div className="mb-3 flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-amber-500" />
                  <h3 className="font-heading text-sm font-bold text-foreground">Your Interview Invites</h3>
                </div>
                {interviews.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    You have no interview invites yet. When a recruiter schedules one, it shows here with the time and a join link.
                  </p>
                ) : (
                  <div className="space-y-3">
                    {interviews.map((iv) => <InterviewInviteCard key={iv.id} iv={iv} />)}
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Recent applications */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-heading text-lg font-bold text-foreground">Recent Applications</h2>
            <Link href="/candidate/applications" className="text-xs text-primary hover:underline flex items-center gap-1">
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </div>

          {apps.length === 0 ? (
            <div className="glass rounded-2xl p-12 text-center">
              <Briefcase className="mx-auto mb-3 h-10 w-10 text-muted-foreground/30" />
              <p className="text-sm font-medium text-muted-foreground">No applications yet</p>
              <Button className="mt-4 gap-2 glow-blue" size="sm" asChild>
                <Link href="/candidate/discover">Browse Jobs <ArrowRight className="h-3.5 w-3.5" /></Link>
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {apps.slice(0, 4).map((app) => (
                <div key={app.id} className="glass gradient-border rounded-2xl p-5 flex items-center gap-4 flex-wrap">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="font-heading text-sm font-bold text-foreground">{app.jobTitle}</p>
                      <Badge variant="outline" className={cn("text-[10px]", statusColors[app.status] ?? "")}>
                        {app.stage}
                      </Badge>
                      <Badge variant="outline" className={cn("text-[10px]", workModeColors[app.workMode] ?? "")}>
                        {app.workMode}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">{app.companyName} · {app.location}</p>
                    <p className="text-[11px] text-muted-foreground/60 mt-1 flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      Applied {new Date(app.appliedAt).toLocaleDateString()}
                    </p>
                  </div>
                  {app.matchScore && (
                    <div className="text-right shrink-0">
                      <p className="text-[11px] text-muted-foreground/60">Match Score</p>
                      <p className="font-heading text-2xl font-bold text-primary">{app.matchScore}%</p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </motion.div>

        {/* Top matches for you */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.18 }} className="mt-8">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="font-heading text-lg font-bold text-foreground flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" /> Top Matches for You
              </h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Your strongest fits — only jobs matching 70%+ of your skills and experience.
              </p>
            </div>
            <Link href="/candidate/discover" className="text-xs text-primary hover:underline flex items-center gap-1 shrink-0">
              See all jobs <ArrowRight className="h-3 w-3" />
            </Link>
          </div>

          {matchesLoading ? (
            <div className="glass rounded-2xl p-10 text-center">
              <Loader2 className="mx-auto mb-3 h-6 w-6 animate-spin text-muted-foreground/40" />
              <p className="text-sm text-muted-foreground">Finding your best matches…</p>
            </div>
          ) : matches.length === 0 ? (
            (() => {
              const hasProfileData =
                Boolean(profile.cvDocument) ||
                profile.skills.length > 0 ||
                Boolean(profile.currentTitle);
              return (
                <div className="glass rounded-2xl p-10 text-center">
                  <Sparkles className="mx-auto mb-3 h-8 w-8 text-muted-foreground/30" />
                  <p className="text-sm font-medium text-muted-foreground">
                    {hasProfileData ? "No strong matches in the current openings" : "No strong matches yet"}
                  </p>
                  <p className="text-xs text-muted-foreground/70 mt-1">
                    {hasProfileData
                      ? "We couldn't find a close fit among the jobs posted right now. We'll keep matching you as new roles come in — browse all openings meanwhile."
                      : "Upload your CV and complete your profile so we can match you to open jobs."}
                  </p>
                  <Button className="mt-4 gap-2" size="sm" variant="outline" asChild>
                    <Link href={hasProfileData ? "/candidate/discover" : "/candidate/documents"}>
                      {hasProfileData ? "Browse all jobs" : "Manage Documents"} <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  </Button>
                </div>
              );
            })()
          ) : (
            <div className="space-y-3">
              {matches.map((job) => <MatchJobCard key={job.job_id} job={job} />)}
            </div>
          )}
        </motion.div>

        {/* Quick links */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.22 }}
          className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-3"
        >
          {[
            { href: "/candidate/profile",   label: "View My Profile",  Icon: User,      desc: "See how recruiters see you" },
            { href: "/candidate/documents", label: "Manage Documents", Icon: FileText,  desc: "Upload or update your CV" },
            { href: "/candidate/discover",  label: "Browse Jobs",      Icon: Briefcase, desc: "Find new opportunities" },
          ].map((item) => (
            <Link key={item.href} href={item.href}
              className="glass rounded-xl p-4 flex items-start gap-3 hover:ring-1 hover:ring-primary/20 transition-all"
            >
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                <item.Icon className="h-4 w-4 text-primary" />
              </div>
              <div>
                <p className="text-sm font-semibold text-foreground">{item.label}</p>
                <p className="text-[11px] text-muted-foreground">{item.desc}</p>
              </div>
            </Link>
          ))}
        </motion.div>
      </div>
    </div>
  );
}

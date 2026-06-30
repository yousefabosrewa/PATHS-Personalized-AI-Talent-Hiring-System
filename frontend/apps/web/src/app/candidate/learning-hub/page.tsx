"use client";

/**
 * PATHS — Candidate Learning Hub.
 *
 * A personalised career-development page: role roadmaps, skill roadmaps,
 * project ideas, and best practices, each linking out to roadmap.sh. Data
 * comes from GET /api/v1/candidates/{id}/learning-hub.
 */

import { useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import {
  AlertCircle,
  Compass,
  ExternalLink,
  GraduationCap,
  Layers,
  Lightbulb,
  RefreshCw,
  Route,
  ShieldCheck,
  Sparkles,
  Target,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useCandidateProfile } from "@/lib/hooks";
import { useLearningHub } from "@/lib/hooks/candidate.hooks";
import { cn } from "@/lib/utils/cn";
import type {
  LearningHubResponse,
  LearningRecommendation,
  RecommendationType,
} from "@/types/learning-hub.types";

// ── Display maps ──────────────────────────────────────────────────────────────

const PRIORITY_STYLES: Record<string, string> = {
  high: "border-rose-500/30 bg-rose-500/10 text-rose-400",
  medium: "border-amber-500/30 bg-amber-500/10 text-amber-400",
  low: "border-slate-500/30 bg-slate-500/10 text-slate-400",
};

const DIFFICULTY_STYLES: Record<string, string> = {
  beginner: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  intermediate: "border-blue-500/30 bg-blue-500/10 text-blue-400",
  advanced: "border-purple-500/30 bg-purple-500/10 text-purple-400",
};

const TYPE_LABELS: Record<RecommendationType, string> = {
  role: "Role Roadmap",
  skill: "Skill Roadmap",
  project: "Project Ideas",
  best_practice: "Best Practice",
};

interface SectionDef {
  type: RecommendationType;
  label: string;
  Icon: typeof Route;
  cta: string;
  blurb: string;
}

const SECTIONS: SectionDef[] = [
  {
    type: "role",
    label: "Role Roadmaps",
    Icon: Route,
    cta: "Open Roadmap",
    blurb: "End-to-end roadmaps for the roles that best fit your profile.",
  },
  {
    type: "skill",
    label: "Skill Roadmaps",
    Icon: Layers,
    cta: "Open Roadmap",
    blurb: "Focused roadmaps that close your individual skill gaps.",
  },
  {
    type: "project",
    label: "Projects",
    Icon: Lightbulb,
    cta: "Open Project Ideas",
    blurb: "Practical builds that turn what you learn into portfolio evidence.",
  },
  {
    type: "best_practice",
    label: "Best Practices",
    Icon: ShieldCheck,
    cta: "Open Best Practice",
    blurb: "Production-grade habits employers expect at the next level.",
  },
];

// ── Recommendation card ─────────────────────────────────────────────────────────

function RecommendationCard({
  rec,
  cta,
}: {
  rec: LearningRecommendation;
  cta: string;
}) {
  const matchPct = Math.round(rec.score * 100);

  return (
    <div className="glass gradient-border flex flex-col rounded-2xl p-5">
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-heading text-[15px] font-bold leading-snug text-foreground">
          {rec.title}
        </h3>
        <Badge
          variant="outline"
          className={cn(
            "shrink-0 text-[10px] capitalize",
            PRIORITY_STYLES[rec.priority] ?? "",
          )}
        >
          {rec.priority} priority
        </Badge>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <Badge
          variant="outline"
          className="border-primary/30 bg-primary/10 text-[10px] text-primary"
        >
          {TYPE_LABELS[rec.type]}
        </Badge>
        <Badge
          variant="outline"
          className={cn(
            "text-[10px] capitalize",
            DIFFICULTY_STYLES[rec.difficulty] ?? "",
          )}
        >
          {rec.difficulty}
        </Badge>
        <span className="ml-auto flex items-center gap-1 text-[11px] font-medium text-muted-foreground">
          <Sparkles className="h-3 w-3 text-primary" />
          {matchPct}% match
        </span>
      </div>

      <p className="mt-3 text-[13px] leading-relaxed text-muted-foreground">
        {rec.reason}
      </p>

      {rec.relatedSkills.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {rec.relatedSkills.map((skill) => (
            <span
              key={skill}
              className="rounded-full border border-border/40 bg-muted/30 px-2 py-0.5 text-[10px] text-muted-foreground"
            >
              {skill}
            </span>
          ))}
        </div>
      )}

      <div className="mt-auto pt-4">
        <a
          href={rec.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-[12px] font-semibold text-primary-foreground transition-all hover:bg-primary/85"
        >
          {cta}
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
      </div>
    </div>
  );
}

// ── Summary cards ───────────────────────────────────────────────────────────────

function SummaryCards({
  summary,
}: {
  summary: LearningHubResponse["summary"];
}) {
  const recommendedPath = summary.recommendedRole
    ? summary.recommendedRole.replace(/ Roadmap$/, "")
    : "—";

  const cards = [
    { label: "Recommended Path", value: recommendedPath, Icon: Compass },
    { label: "Top Skill Focus", value: summary.topSkillGap ?? "—", Icon: Target },
    {
      label: "Suggested Project Level",
      value: summary.recommendedProjectLevel,
      Icon: Layers,
    },
    {
      label: "Recommendations",
      value: String(summary.totalRecommendations),
      Icon: Sparkles,
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {cards.map((card) => (
        <div key={card.label} className="glass rounded-2xl p-4">
          <card.Icon className="mb-2 h-5 w-5 text-primary" />
          <p className="font-heading text-[15px] font-bold leading-tight text-foreground">
            {card.value}
          </p>
          <p className="mt-0.5 text-[11px] text-muted-foreground">
            {card.label}
          </p>
        </div>
      ))}
    </div>
  );
}

// ── State views ─────────────────────────────────────────────────────────────────

function LoadingState() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-[88px] rounded-2xl" />
        ))}
      </div>
      <Skeleton className="h-9 w-full max-w-md rounded-lg" />
      <div className="grid gap-4 sm:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-56 rounded-2xl" />
        ))}
      </div>
      <p className="text-center text-sm text-muted-foreground">
        Building personalized learning recommendations…
      </p>
    </div>
  );
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="glass rounded-2xl p-12 text-center">
      <AlertCircle className="mx-auto mb-3 h-10 w-10 text-rose-400/60" />
      <p className="text-sm font-semibold text-foreground">
        Could not load Learning Hub recommendations.
      </p>
      <p className="mt-1 text-xs text-muted-foreground">Please try again.</p>
      <Button
        size="sm"
        variant="outline"
        className="mt-4 gap-1.5"
        onClick={onRetry}
      >
        <RefreshCw className="h-3.5 w-3.5" /> Retry
      </Button>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="glass rounded-2xl p-12 text-center">
      <GraduationCap className="mx-auto mb-3 h-10 w-10 text-muted-foreground/30" />
      <p className="text-sm font-semibold text-foreground">
        No personalized recommendations yet
      </p>
      <p className="mx-auto mt-1 max-w-sm text-xs text-muted-foreground">
        Add skills, interests, or a target role to your profile to generate a
        personalized learning path.
      </p>
      <Button size="sm" className="glow-blue mt-4 gap-1.5" asChild>
        <Link href="/candidate/profile/edit">Update Profile</Link>
      </Button>
    </div>
  );
}

// ── Hub content (success state) ──────────────────────────────────────────────────

function HubContent({ data }: { data: LearningHubResponse }) {
  const [active, setActive] = useState<RecommendationType>("role");

  const counts: Record<RecommendationType, number> = {
    role: 0,
    skill: 0,
    project: 0,
    best_practice: 0,
  };
  for (const rec of data.recommendations) {
    counts[rec.type] += 1;
  }

  const section = SECTIONS.find((s) => s.type === active) ?? SECTIONS[0];
  const recs = data.recommendations.filter((r) => r.type === active);

  return (
    <div className="space-y-6">
      <SummaryCards summary={data.summary} />

      {/* Section switcher */}
      <div className="flex flex-wrap gap-2">
        {SECTIONS.map((s) => (
          <button
            key={s.type}
            type="button"
            onClick={() => setActive(s.type)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-[12px] font-medium transition-all",
              active === s.type
                ? "border-primary/40 bg-primary/10 text-primary"
                : "border-border/40 text-muted-foreground hover:bg-muted/30 hover:text-foreground",
            )}
          >
            <s.Icon className="h-3.5 w-3.5" />
            {s.label}
            <span className="text-[10px] opacity-70">{counts[s.type]}</span>
          </button>
        ))}
      </div>

      {/* Active section */}
      <div>
        <p className="mb-4 text-sm text-muted-foreground">{section.blurb}</p>
        {recs.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/40 py-14 text-center">
            <section.Icon className="mx-auto mb-2 h-8 w-8 text-muted-foreground/30" />
            <p className="mx-auto max-w-sm text-sm text-muted-foreground">
              No {section.label.toLowerCase()} to show yet. Add more detail to
              your profile for tailored picks.
            </p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {recs.map((rec) => (
              <RecommendationCard key={rec.id} rec={rec} cta={section.cta} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────────

export default function LearningHubPage() {
  const { data: profile, isLoading: profileLoading } = useCandidateProfile();
  const candidateId = profile?.id || undefined;
  // Empty string = let the backend auto-detect; a role id = manual override.
  const [target, setTarget] = useState<string>("");
  const hub = useLearningHub(candidateId, target || undefined);

  const data = hub.data;
  const name = (data?.candidateName || profile?.fullName || "").trim();
  const currentPosition = (
    data?.currentPosition ||
    profile?.currentTitle ||
    ""
  ).trim();
  const targetRole = (
    data?.targetRole ||
    profile?.preferences?.desiredRoles?.[0] ||
    ""
  ).trim();
  const availableTargets = data?.availableTargets ?? [];
  const activeTarget = target || data?.targetRoleId || "";

  // Loading until we either have data or a definite error.
  const loading =
    profileLoading || (!!candidateId && !data && !hub.isError);

  let body: React.ReactNode;
  if (loading) {
    body = <LoadingState />;
  } else if (hub.isError) {
    body = <ErrorState onRetry={() => hub.refetch()} />;
  } else if (!data || data.recommendations.length === 0) {
    body = <EmptyState />;
  } else {
    body = <HubContent data={data} />;
  }

  return (
    <div className="min-h-screen px-6 py-8">
      <div className="mx-auto max-w-5xl">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <div className="flex items-center gap-2 text-primary">
            <GraduationCap className="h-5 w-5" />
            <span className="text-[11px] font-semibold uppercase tracking-wider">
              Career Development
            </span>
          </div>
          <h1 className="mt-1.5 font-heading text-3xl font-bold text-foreground">
            Learning Hub
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Personalized learning recommendations based on your skills,
            interests, and career goals.
          </p>
          {(name || currentPosition || targetRole || availableTargets.length > 0) && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {name && (
                <span className="text-sm font-semibold text-foreground">
                  {name}
                </span>
              )}
              {currentPosition && (
                <Badge
                  variant="outline"
                  className="border-border/50 text-[11px] text-muted-foreground"
                >
                  Current: {currentPosition}
                </Badge>
              )}
              {availableTargets.length > 0 ? (
                <div className="inline-flex items-center gap-1.5 rounded-md border border-primary/30 bg-primary/10 px-2 py-1">
                  <Target className="h-3.5 w-3.5 text-primary" />
                  <span className="text-[11px] text-primary/80">Target:</span>
                  <select
                    value={activeTarget}
                    onChange={(e) => setTarget(e.target.value)}
                    aria-label="Choose your target role"
                    className="cursor-pointer bg-transparent text-[11px] font-semibold text-primary focus:outline-none"
                  >
                    {!activeTarget && (
                      <option value="" className="bg-background text-foreground">
                        Choose a role…
                      </option>
                    )}
                    {availableTargets.map((o) => (
                      <option
                        key={o.id}
                        value={o.id}
                        className="bg-background text-foreground"
                      >
                        {o.label}
                      </option>
                    ))}
                  </select>
                  {hub.isFetching && (
                    <RefreshCw className="h-3 w-3 animate-spin text-primary/70" />
                  )}
                </div>
              ) : targetRole ? (
                <Badge
                  variant="outline"
                  className="border-primary/30 bg-primary/10 text-[11px] text-primary"
                >
                  Target: {targetRole}
                </Badge>
              ) : null}
            </div>
          )}
        </motion.div>

        {/* Body */}
        {body}
      </div>
    </div>
  );
}

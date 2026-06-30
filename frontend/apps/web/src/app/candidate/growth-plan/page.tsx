"use client";

import { useState } from "react";
import {
  BookOpen,
  CheckCircle2,
  ChevronDown,
  Clock,
  ExternalLink,
  Lightbulb,
  Loader2,
  Sparkles,
  Target,
  TrendingUp,
} from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { useCandidateProfile } from "@/lib/hooks";

// ── Types ─────────────────────────────────────────────────────────────────────

interface SkillGap {
  skill: string;
  gap_level: "low" | "medium" | "high";
  priority: number;
  resources?: Resource[];
}

interface Resource {
  title: string;
  url?: string;
  type: "course" | "book" | "video" | "article" | "platform";
  estimated_hours?: number;
}

interface Milestone {
  label: string;
  goals: string[];
  success_criteria: string;
}

interface GrowthPlan {
  skill_gaps: SkillGap[];
  learning_resources: Resource[];
  milestones: Milestone[];
  overall_completion: number;
  candidate_facing_message?: string;
  status: "draft" | "active" | "completed";
}

// ── Demo plan (shown when no real plan is available) ─────────────────────────

const DEMO_PLAN: GrowthPlan = {
  status: "active",
  overall_completion: 25,
  candidate_facing_message:
    "Welcome! Your personalised growth plan is ready. It outlines your first 90 days and the resources prepared to help you succeed.",
  skill_gaps: [
    { skill: "System Design", gap_level: "medium", priority: 1 },
    { skill: "CI/CD & DevOps", gap_level: "low", priority: 2 },
    { skill: "Technical Leadership", gap_level: "high", priority: 3 },
  ],
  learning_resources: [
    {
      title: "Designing Data-Intensive Applications",
      type: "book",
      estimated_hours: 20,
    },
    {
      title: "GitHub Actions Fundamentals",
      type: "course",
      estimated_hours: 8,
    },
    {
      title: "O'Reilly Learning Platform — 6-month access",
      type: "platform",
      estimated_hours: 40,
    },
  ],
  milestones: [
    {
      label: "30-day",
      goals: ["Complete onboarding", "Meet the team", "Shadow key processes"],
      success_criteria: "Onboarding checklist 100% complete",
    },
    {
      label: "60-day",
      goals: [
        "Own first deliverable",
        "Resolve first ticket independently",
        "Attend team retro",
      ],
      success_criteria: "First PR merged with < 2 revisions",
    },
    {
      label: "90-day",
      goals: [
        "Full autonomy on role scope",
        "Present team retrospective",
        "Mentor a junior team member",
      ],
      success_criteria: "Peer review score ≥ 4/5",
    },
  ],
};

// ── Sub-components ────────────────────────────────────────────────────────────

const GAP_COLORS: Record<string, string> = {
  low:    "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  medium: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  high:   "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
};

const RESOURCE_ICONS: Record<string, React.ReactNode> = {
  course:   <BookOpen className="h-4 w-4 text-blue-500" />,
  book:     <BookOpen className="h-4 w-4 text-purple-500" />,
  video:    <Sparkles className="h-4 w-4 text-amber-500" />,
  article:  <Lightbulb className="h-4 w-4 text-green-500" />,
  platform: <TrendingUp className="h-4 w-4 text-primary" />,
};

function MilestoneCard({ milestone, index }: { milestone: Milestone; index: number }) {
  const [expanded, setExpanded] = useState(index === 0);
  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-muted/30 transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary text-sm font-bold">
            {index + 1}
          </div>
          <span className="font-semibold">{milestone.label} Milestone</span>
        </div>
        <ChevronDown
          className={cn(
            "h-4 w-4 text-muted-foreground transition-transform",
            expanded && "rotate-180",
          )}
        />
      </button>
      {expanded && (
        <div className="border-t border-border/40 p-4 space-y-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground/70 mb-2">
              Goals
            </p>
            <ul className="space-y-1.5">
              {milestone.goals.map((g, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <CheckCircle2 className="h-4 w-4 text-muted-foreground/50 shrink-0 mt-0.5" />
                  {g}
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-lg bg-primary/5 border border-primary/10 p-3">
            <p className="text-xs font-semibold text-primary/70 mb-1">Success Criteria</p>
            <p className="text-sm">{milestone.success_criteria}</p>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function GrowthPlanPage() {
  const { data: profile, isLoading } = useCandidateProfile();

  // In production this would fetch the growth plan from the API.
  // For the demo we show the DEMO_PLAN as a placeholder.
  const plan: GrowthPlan = DEMO_PLAN;
  const candidateName = profile?.fullName?.split(" ")[0] ?? "there";

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-24 w-full rounded-xl" />
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-32 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  if (!plan) {
    return (
      <div className="flex flex-col items-center gap-4 p-6 py-24 text-center">
        <Target className="h-12 w-12 text-muted-foreground/30" />
        <div>
          <p className="font-semibold">No growth plan yet</p>
          <p className="text-sm text-muted-foreground mt-1">
            Your personalised plan will appear here after a hiring decision is made.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 p-6 max-w-3xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <TrendingUp className="h-6 w-6 text-primary" />
          Your Growth Plan
        </h1>
        <p className="text-muted-foreground mt-1">
          Hi {candidateName} — here's your personalised 90-day development roadmap.
        </p>
      </div>

      {/* Welcome message */}
      {plan.candidate_facing_message && (
        <div className="rounded-xl border border-primary/20 bg-primary/5 p-4">
          <p className="text-sm leading-relaxed">{plan.candidate_facing_message}</p>
        </div>
      )}

      {/* Overall progress */}
      <div className="rounded-xl border border-border bg-card p-5 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">Overall Completion</h3>
          <span className="text-sm font-bold text-primary">
            {plan.overall_completion}%
          </span>
        </div>
        <Progress value={plan.overall_completion} className="h-2" />
        <p className="text-xs text-muted-foreground">
          Keep going — you're making great progress!
        </p>
      </div>

      {/* Skill gaps */}
      <div className="space-y-3">
        <h2 className="text-base font-semibold flex items-center gap-2">
          <Target className="h-4 w-4 text-primary" />
          Skill Development Areas
        </h2>
        <div className="space-y-2">
          {plan.skill_gaps.map((gap, i) => (
            <div
              key={i}
              className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-3"
            >
              <span className="text-sm font-medium flex-1">{gap.skill}</span>
              <span
                className={cn(
                  "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                  GAP_COLORS[gap.gap_level] ?? GAP_COLORS.medium,
                )}
              >
                {gap.gap_level} priority
              </span>
            </div>
          ))}
        </div>
      </div>

      <Separator />

      {/* Learning resources */}
      <div className="space-y-3">
        <h2 className="text-base font-semibold flex items-center gap-2">
          <BookOpen className="h-4 w-4 text-primary" />
          Learning Resources
        </h2>
        <div className="space-y-2">
          {plan.learning_resources.map((res, i) => (
            <div
              key={i}
              className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-3"
            >
              {RESOURCE_ICONS[res.type] ?? RESOURCE_ICONS.course}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{res.title}</p>
                <p className="text-xs text-muted-foreground capitalize">
                  {res.type}
                  {res.estimated_hours ? ` · ~${res.estimated_hours}h` : ""}
                </p>
              </div>
              {res.url && (
                <a href={res.url} target="_blank" rel="noreferrer">
                  <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
                    <ExternalLink className="h-3.5 w-3.5" />
                  </Button>
                </a>
              )}
            </div>
          ))}
        </div>
      </div>

      <Separator />

      {/* 30/60/90-day milestones */}
      <div className="space-y-3">
        <h2 className="text-base font-semibold flex items-center gap-2">
          <Clock className="h-4 w-4 text-primary" />
          30 / 60 / 90 Day Milestones
        </h2>
        <div className="space-y-3">
          {plan.milestones.map((m, i) => (
            <MilestoneCard key={i} milestone={m} index={i} />
          ))}
        </div>
      </div>
    </div>
  );
}

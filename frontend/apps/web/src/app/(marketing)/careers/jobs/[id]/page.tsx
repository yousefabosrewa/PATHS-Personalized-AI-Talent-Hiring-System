"use client";

import { use } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Briefcase,
  Check,
  MapPin,
  Sparkles,
  Star,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { usePublicJobDetail } from "@/lib/hooks";

interface Props {
  params: Promise<{ id: string }>;
}

function fmtSalary(min: number | null, max: number | null, currency: string | null) {
  if (!min && !max) return null;
  const fmt = (n: number) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency ?? "USD",
      maximumFractionDigits: 0,
    }).format(n);
  if (min && max) return `${fmt(min)} – ${fmt(max)}`;
  if (min) return `From ${fmt(min)}`;
  return `Up to ${fmt(max!)}`;
}

const WORK_MODE_COLORS: Record<string, string> = {
  remote: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  hybrid: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  onsite: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
};

export default function PublicJobDetailPage({ params }: Props) {
  const { id } = use(params);
  const { data: job, isLoading } = usePublicJobDetail(id);

  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-16 space-y-4">
        <Skeleton className="h-8 w-48 rounded" />
        <Skeleton className="h-32 w-full rounded-xl" />
        <Skeleton className="h-48 w-full rounded-xl" />
      </div>
    );
  }

  if (!job) {
    return (
      <div className="flex flex-col items-center gap-4 py-24 text-center">
        <Briefcase className="h-10 w-10 text-muted-foreground/30" />
        <p className="font-semibold">Job not found</p>
        <Link href="/careers/jobs">
          <Button variant="outline" size="sm">Browse Jobs</Button>
        </Link>
      </div>
    );
  }

  const salary = fmtSalary(job.salary_min, job.salary_max, job.currency);

  // ── schema.org JobPosting JSON-LD ────────────────────────────────────────
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "JobPosting",
    title: job.title,
    description: job.description_full ?? job.description_preview ?? "",
    hiringOrganization: {
      "@type": "Organization",
      name: job.company,
    },
    jobLocation: {
      "@type": "Place",
      address: { "@type": "PostalAddress", addressLocality: job.location },
    },
    employmentType: job.employment_type ?? "FULL_TIME",
    datePosted: job.date_posted ?? new Date().toISOString().split("T")[0],
    validThrough: job.valid_through ?? undefined,
    baseSalary: salary
      ? {
          "@type": "MonetaryAmount",
          currency: job.currency ?? "USD",
          value: {
            "@type": "QuantitativeValue",
            minValue: job.salary_min,
            maxValue: job.salary_max,
            unitText: "YEAR",
          },
        }
      : undefined,
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-16 space-y-6">
      {/* schema.org JSON-LD */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      {/* Back */}
      <Link
        href="/careers/jobs"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Jobs
      </Link>

      {/* Header card */}
      <div className="rounded-xl border border-border bg-card p-6 space-y-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="space-y-2">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-2xl font-bold">{job.title}</h1>
              {job.work_mode && (
                <span
                  className={cn(
                    "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                    WORK_MODE_COLORS[job.work_mode] ?? WORK_MODE_COLORS.onsite,
                  )}
                >
                  {job.work_mode.replace("_", "-")}
                </span>
              )}
            </div>
            <p className="text-base text-muted-foreground">{job.company}</p>
            <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
              {job.location && (
                <span className="flex items-center gap-1">
                  <MapPin className="h-3.5 w-3.5" />
                  {job.location}
                </span>
              )}
              {job.level && (
                <span className="flex items-center gap-1">
                  <Star className="h-3.5 w-3.5" />
                  {job.level}
                </span>
              )}
              {salary && (
                <span className="font-medium text-foreground">{salary}</span>
              )}
            </div>
          </div>

          <Link href="/candidate-signup">
            <Button className="gap-2 shrink-0">
              <Sparkles className="h-4 w-4" />
              Apply Now
            </Button>
          </Link>
        </div>
      </div>

      {/* Description */}
      {(job.description_full ?? job.description_preview) && (
        <div className="rounded-xl border border-border bg-card p-6 space-y-3">
          <h2 className="font-semibold">About This Role</h2>
          <Separator />
          <p className="text-sm leading-relaxed whitespace-pre-line">
            {job.description_full ?? job.description_preview}
          </p>
        </div>
      )}

      {/* Skills */}
      {(job.required_skills?.length > 0 || job.preferred_skills?.length > 0) && (
        <div className="rounded-xl border border-border bg-card p-6 space-y-4">
          {job.required_skills?.length > 0 && (
            <div className="space-y-2">
              <h3 className="font-semibold text-sm">Required Skills</h3>
              <div className="flex flex-wrap gap-2">
                {job.required_skills.map((s) => (
                  <Badge key={s} className="gap-1 text-xs">
                    <Check className="h-3 w-3" />
                    {s}
                  </Badge>
                ))}
              </div>
            </div>
          )}
          {job.preferred_skills?.length > 0 && (
            <div className="space-y-2">
              <h3 className="font-semibold text-sm text-muted-foreground">Nice to Have</h3>
              <div className="flex flex-wrap gap-2">
                {job.preferred_skills.map((s) => (
                  <Badge key={s} variant="outline" className="text-xs">
                    {s}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Apply CTA */}
      <div className="rounded-xl border border-primary/20 bg-primary/5 p-5 flex items-center justify-between gap-4">
        <div>
          <p className="font-semibold">Ready to apply?</p>
          <p className="text-sm text-muted-foreground">
            Create a free PATHS profile and apply in minutes.
          </p>
        </div>
        <Link href="/candidate-signup">
          <Button className="gap-2 shrink-0">
            <Sparkles className="h-4 w-4" />
            Apply Now
          </Button>
        </Link>
      </div>
    </div>
  );
}

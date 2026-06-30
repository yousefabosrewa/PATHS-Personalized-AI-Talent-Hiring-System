"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Briefcase,
  MapPin,
  Search,
  Sparkles,
  Star,
  Loader2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { usePublicJobsList } from "@/lib/hooks";

const WORK_MODE_COLORS: Record<string, string> = {
  remote: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  hybrid: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  onsite: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
};

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

export default function PublicJobsPage() {
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");

  const { data: jobs = [], isLoading } = usePublicJobsList(
    submitted ? { q: submitted } : undefined,
  );

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setSubmitted(query);
  }

  return (
    <div className="flex flex-col gap-8 px-4 py-16 max-w-5xl mx-auto">
      {/* Header */}
      <div className="text-center space-y-3">
        <Badge variant="outline" className="text-xs">Job Board</Badge>
        <h1 className="text-4xl font-bold tracking-tight">Discover Opportunities</h1>
        <p className="text-muted-foreground">
          Jobs from companies using PATHS — AI-matched and fairly screened.
        </p>
      </div>

      {/* Search */}
      <form onSubmit={handleSearch} className="flex gap-2 max-w-2xl mx-auto w-full">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Search by title, company, or location…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <Button type="submit">Search</Button>
      </form>

      {/* Results */}
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full rounded-xl" />
          ))}
        </div>
      ) : jobs.length === 0 ? (
        <div className="flex flex-col items-center gap-4 py-24 text-center">
          <Briefcase className="h-12 w-12 text-muted-foreground/30" />
          <div>
            <p className="font-semibold">No jobs found</p>
            <p className="text-sm text-muted-foreground mt-1">
              Try a different search term or check back later.
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => {
            const salary = fmtSalary(job.salary_min, job.salary_max, job.currency);
            return (
              <Link
                key={job.id}
                href={`/careers/jobs/${job.slug}`}
                className="block rounded-xl border border-border bg-card p-5 hover:shadow-sm transition-shadow"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0 space-y-1.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-semibold text-base">{job.title}</h3>
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
                    <p className="text-sm text-muted-foreground">{job.company}</p>
                    <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                      {job.location && (
                        <span className="flex items-center gap-1">
                          <MapPin className="h-3 w-3" />
                          {job.location}
                        </span>
                      )}
                      {job.level && (
                        <span className="flex items-center gap-1">
                          <Star className="h-3 w-3" />
                          {job.level}
                        </span>
                      )}
                      {salary && <span className="font-medium text-foreground">{salary}</span>}
                    </div>
                    {job.description_preview && (
                      <p className="text-xs text-muted-foreground line-clamp-2">
                        {job.description_preview}
                      </p>
                    )}
                  </div>
                  <Button size="sm" className="shrink-0 gap-1.5 text-xs">
                    <Sparkles className="h-3.5 w-3.5" />
                    View
                  </Button>
                </div>
              </Link>
            );
          })}
        </div>
      )}

      <p className="text-xs text-muted-foreground text-center pt-4">
        Showing {jobs.length} open positions
      </p>
    </div>
  );
}

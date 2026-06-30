"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { motion } from "framer-motion";
import { ArrowLeft, ArrowRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useOnboardingStore } from "@/lib/stores/onboarding.store";
import type { JobType, WorkplaceType } from "@/types/candidate-profile.types";
import { cn } from "@/lib/utils/cn";

const JOB_TYPES: { value: JobType; label: string }[] = [
  { value: "full_time",   label: "Full-Time"   },
  { value: "part_time",   label: "Part-Time"   },
  { value: "contract",    label: "Contract"    },
  { value: "freelance",   label: "Freelance"   },
  { value: "internship",  label: "Internship"  },
];

const WORKPLACE_TYPES: { value: WorkplaceType; label: string }[] = [
  { value: "remote",  label: "Remote"  },
  { value: "hybrid",  label: "Hybrid"  },
  { value: "onsite",  label: "On-site" },
];

const NOTICE_PERIODS = [
  { value: 0,   label: "Available immediately" },
  { value: 1,   label: "1 week"               },
  { value: 2,   label: "2 weeks"              },
  { value: 4,   label: "1 month"              },
  { value: 8,   label: "2 months"             },
  { value: 12,  label: "3 months"             },
];

function ToggleChip<T extends string>({
  value, label, selected, onToggle,
}: { value: T; label: string; selected: boolean; onToggle: (v: T) => void }) {
  return (
    <button
      type="button"
      onClick={() => onToggle(value)}
      className={cn(
        "rounded-full border px-4 py-1.5 text-sm font-medium transition-all",
        selected
          ? "border-primary/40 bg-primary/15 text-primary"
          : "border-border/50 text-muted-foreground hover:border-border hover:text-foreground"
      )}
    >
      {label}
    </button>
  );
}

export default function PreferencesPage() {
  const router = useRouter();
  const { draft, updateDraft, markStepComplete, saveDraft } = useOnboardingStore();
  const prefs = draft.preferences!;

  const [jobTypes, setJobTypes]     = useState<JobType[]>(prefs.jobTypes ?? []);
  const [workplaces, setWorkplaces] = useState<WorkplaceType[]>(prefs.workplaceTypes ?? []);
  const [openToRelocation, setOpenToRelocation] = useState(prefs.openToRelocation ?? false);
  const [salaryMin, setSalaryMin]   = useState(prefs.desiredSalaryMin?.toString() ?? "");
  const [salaryMax, setSalaryMax]   = useState(prefs.desiredSalaryMax?.toString() ?? "");
  const [currency, setCurrency]     = useState(prefs.salaryCurrency ?? "USD");
  const [noticePeriod, setNoticePeriod] = useState(prefs.noticePeriodWeeks ?? 0);
  const [roleInput, setRoleInput]   = useState("");
  const [desiredRoles, setDesiredRoles] = useState<string[]>(prefs.desiredRoles ?? []);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleJobType = (v: JobType) =>
    setJobTypes((prev) => prev.includes(v) ? prev.filter((x) => x !== v) : [...prev, v]);

  const toggleWorkplace = (v: WorkplaceType) =>
    setWorkplaces((prev) => prev.includes(v) ? prev.filter((x) => x !== v) : [...prev, v]);

  const addRole = () => {
    const r = roleInput.trim();
    if (r && !desiredRoles.includes(r)) setDesiredRoles((prev) => [...prev, r]);
    setRoleInput("");
  };

  const onSubmit = async () => {
    if (jobTypes.length === 0) { setError("Select at least one job type."); return; }
    if (workplaces.length === 0) { setError("Select at least one workplace type."); return; }
    setError(null);
    setIsSubmitting(true);
    updateDraft({
      preferences: {
        desiredRoles,
        jobTypes,
        workplaceTypes: workplaces,
        preferredLocations: [],
        openToRelocation,
        desiredSalaryMin: salaryMin ? Number(salaryMin) : undefined,
        desiredSalaryMax: salaryMax ? Number(salaryMax) : undefined,
        salaryCurrency: currency,
        noticePeriodWeeks: noticePeriod,
      },
    });
    markStepComplete("preferences");
    await saveDraft();
    router.push("/onboarding/review");
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="mx-auto max-w-2xl px-6 py-10"
    >
      <div className="mb-8">
        <p className="text-xs font-semibold uppercase tracking-widest text-primary">Step 8 of 9</p>
        <h1 className="mt-1 font-heading text-3xl font-bold text-foreground">Job Preferences</h1>
        <p className="mt-2 text-sm text-muted-foreground">Tell us what you&apos;re looking for so we can match you to the right roles.</p>
      </div>

      <div className="space-y-8">
        {/* Desired roles */}
        <div className="space-y-2">
          <Label className="text-sm font-medium">Desired Roles</Label>
          <div className="flex gap-2">
            <Input
              placeholder="e.g. Senior Backend Engineer"
              value={roleInput}
              onChange={(e) => setRoleInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addRole(); } }}
              className="h-10"
            />
            <Button type="button" variant="outline" onClick={addRole} className="h-10 shrink-0">Add</Button>
          </div>
          {desiredRoles.length > 0 && (
            <div className="flex flex-wrap gap-2 pt-1">
              {desiredRoles.map((r) => (
                <span key={r} className="flex items-center gap-1 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs text-primary">
                  {r}
                  <button type="button" onClick={() => setDesiredRoles((p) => p.filter((x) => x !== r))} className="ml-1 opacity-60 hover:opacity-100">×</button>
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Job types */}
        <div className="space-y-2">
          <Label className="text-sm font-medium">Job Types <span className="text-destructive">*</span></Label>
          <div className="flex flex-wrap gap-2">
            {JOB_TYPES.map((t) => (
              <ToggleChip key={t.value} value={t.value} label={t.label} selected={jobTypes.includes(t.value)} onToggle={toggleJobType} />
            ))}
          </div>
        </div>

        {/* Workplace types */}
        <div className="space-y-2">
          <Label className="text-sm font-medium">Workplace <span className="text-destructive">*</span></Label>
          <div className="flex flex-wrap gap-2">
            {WORKPLACE_TYPES.map((t) => (
              <ToggleChip key={t.value} value={t.value} label={t.label} selected={workplaces.includes(t.value)} onToggle={toggleWorkplace} />
            ))}
          </div>
        </div>

        {/* Open to relocation */}
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={openToRelocation}
            onChange={(e) => setOpenToRelocation(e.target.checked)}
            className="h-4 w-4 rounded border-border accent-primary"
          />
          <span className="text-sm text-foreground">I&apos;m open to relocation</span>
        </label>

        {/* Salary */}
        <div className="space-y-2">
          <Label className="text-sm font-medium">Desired Salary Range <span className="text-muted-foreground/60">(optional)</span></Label>
          <div className="flex items-center gap-2">
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="h-10 rounded-lg border border-border bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {["USD", "EGP", "EUR", "GBP", "AED", "SAR"].map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <Input
              type="number"
              min={0}
              placeholder="Min"
              value={salaryMin}
              onChange={(e) => setSalaryMin(e.target.value)}
              className="h-10"
            />
            <span className="text-muted-foreground text-sm">–</span>
            <Input
              type="number"
              min={0}
              placeholder="Max"
              value={salaryMax}
              onChange={(e) => setSalaryMax(e.target.value)}
              className="h-10"
            />
          </div>
          <p className="text-[11px] text-muted-foreground/60">Annual gross salary</p>
        </div>

        {/* Notice period */}
        <div className="space-y-2">
          <Label className="text-sm font-medium">Notice Period</Label>
          <div className="flex flex-wrap gap-2">
            {NOTICE_PERIODS.map((n) => (
              <button
                key={n.value}
                type="button"
                onClick={() => setNoticePeriod(n.value)}
                className={cn(
                  "rounded-full border px-4 py-1.5 text-sm font-medium transition-all",
                  noticePeriod === n.value
                    ? "border-primary/40 bg-primary/15 text-primary"
                    : "border-border/50 text-muted-foreground hover:border-border hover:text-foreground"
                )}
              >
                {n.label}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-2 text-xs text-destructive">{error}</p>
        )}

        <div className="flex items-center justify-between pt-2">
          <Button type="button" variant="ghost" className="gap-2" onClick={() => router.push("/onboarding/links")}>
            <ArrowLeft className="h-4 w-4" /> Back
          </Button>
          <Button type="button" className="gap-2 glow-blue" disabled={isSubmitting} onClick={onSubmit}>
            {isSubmitting ? <><Loader2 className="h-4 w-4 animate-spin" /> Saving…</> : <>Save &amp; Continue <ArrowRight className="h-4 w-4" /></>}
          </Button>
        </div>
      </div>
    </motion.div>
  );
}

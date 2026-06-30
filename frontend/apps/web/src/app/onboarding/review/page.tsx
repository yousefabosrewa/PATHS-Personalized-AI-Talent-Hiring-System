"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  ArrowLeft, Loader2, CheckCircle2, User, Phone, GraduationCap,
  Briefcase, Code2, Upload, Link2, Settings, Edit2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { useOnboardingStore } from "@/lib/stores/onboarding.store";
import { ONBOARDING_STEPS } from "@/types/candidate-profile.types";
import { cn } from "@/lib/utils/cn";

const stepIcons = {
  "basic-info":  User,
  "contact":     Phone,
  "education":   GraduationCap,
  "experience":  Briefcase,
  "skills":      Code2,
  "cv-upload":   Upload,
  "links":       Link2,
  "preferences": Settings,
};

function Section({ title, href, children }: { title: string; href: string; children: React.ReactNode }) {
  return (
    <div className="glass gradient-border rounded-2xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-heading text-sm font-semibold text-foreground">{title}</h3>
        <Link href={href} className="flex items-center gap-1 text-xs text-primary hover:underline">
          <Edit2 className="h-3 w-3" /> Edit
        </Link>
      </div>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div className="flex items-start gap-3">
      <span className="w-28 shrink-0 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground/60">{label}</span>
      <span className="text-sm text-foreground">{value}</span>
    </div>
  );
}

export default function ReviewPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const { draft, completedSteps, submitProfile, markStepComplete, postOnboardingRedirect, setPostOnboardingRedirect } = useOnboardingStore();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const stepsBeforeReview = ONBOARDING_STEPS.filter((s) => s.key !== "review");
  const allComplete = stepsBeforeReview.every((s) => completedSteps.has(s.key));

  const onSubmit = async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      markStepComplete("review");
      await submitProfile();
      await qc.invalidateQueries({ queryKey: ["candidate-profile"] });
      await qc.invalidateQueries({ queryKey: ["candidate-applications"] });

      // Honour the intent URL captured at the start of onboarding (e.g. the
      // job page that originally triggered the signup flow). Clear it first so
      // a second visit to the review page doesn't reuse a stale redirect.
      const destination = postOnboardingRedirect ?? "/candidate/dashboard";
      setPostOnboardingRedirect(null);
      router.push(destination);
    } catch {
      setError("Something went wrong. Please try again.");
      setIsSubmitting(false);
    }
  };

  const prefs = draft.preferences;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="mx-auto max-w-2xl px-6 py-10"
    >
      <div className="mb-8">
        <p className="text-xs font-semibold uppercase tracking-widest text-primary">Step 9 of 9</p>
        <h1 className="mt-1 font-heading text-3xl font-bold text-foreground">Review &amp; Submit</h1>
        <p className="mt-2 text-sm text-muted-foreground">Check everything looks right before submitting your profile.</p>
      </div>

      {/* Completion status */}
      <div className="mb-6 glass rounded-xl p-4">
        <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground/50">Step Completion</p>
        <div className="flex flex-wrap gap-2">
          {stepsBeforeReview.map((step) => {
            const done = completedSteps.has(step.key);
            return (
              <Link
                key={step.key}
                href={`/onboarding/${step.key}`}
                className={cn(
                  "flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-medium transition-colors",
                  done
                    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                    : "border-amber-500/30 bg-amber-500/10 text-amber-400"
                )}
              >
                {done ? <CheckCircle2 className="h-3 w-3" /> : <Edit2 className="h-3 w-3" />}
                {step.label}
              </Link>
            );
          })}
        </div>
        {!allComplete && (
          <p className="mt-3 text-[11px] text-amber-400">Some steps are incomplete. You can submit anyway — just complete them from your profile later.</p>
        )}
      </div>

      <div className="space-y-4">
        {/* Basic Info */}
        <Section title="Basic Information" href="/onboarding/basic-info">
          <div className="space-y-2">
            <Row label="Name"       value={draft.fullName} />
            <Row label="Title"      value={draft.currentTitle} />
            <Row label="Level"      value={draft.careerLevel} />
            <Row label="Experience" value={draft.yearsExperience != null ? `${draft.yearsExperience} years` : null} />
            {draft.summary && (
              <div className="mt-2 rounded-lg bg-muted/20 p-3 text-[13px] text-muted-foreground leading-relaxed">
                {draft.summary}
              </div>
            )}
          </div>
        </Section>

        {/* Contact */}
        <Section title="Contact" href="/onboarding/contact">
          <div className="space-y-2">
            <Row label="Email"    value={draft.email} />
            <Row label="Phone"    value={draft.phone} />
            <Row label="Location" value={draft.locationText} />
          </div>
        </Section>

        {/* Education */}
        <Section title="Education" href="/onboarding/education">
          {draft.education && draft.education.length > 0 ? (
            <div className="space-y-3">
              {draft.education.map((edu) => (
                <div key={edu.id} className="rounded-lg bg-muted/10 p-3">
                  <p className="text-sm font-semibold text-foreground">{edu.degree} · {edu.fieldOfStudy}</p>
                  <p className="text-xs text-muted-foreground">{edu.institution} · {edu.startYear}–{edu.isOngoing ? "Present" : edu.endYear}</p>
                  {edu.gpa && <p className="text-xs text-muted-foreground/60">GPA: {edu.gpa}</p>}
                </div>
              ))}
            </div>
          ) : <p className="text-sm text-muted-foreground/60">No education entries</p>}
        </Section>

        {/* Experience */}
        <Section title="Work Experience" href="/onboarding/experience">
          {draft.experiences && draft.experiences.length > 0 ? (
            <div className="space-y-3">
              {draft.experiences.map((exp) => (
                <div key={exp.id} className="rounded-lg bg-muted/10 p-3">
                  <p className="text-sm font-semibold text-foreground">{exp.title} · {exp.companyName}</p>
                  <p className="text-xs text-muted-foreground">{exp.startDate} – {exp.isCurrent ? "Present" : exp.endDate ?? "—"}</p>
                  {exp.location && <p className="text-xs text-muted-foreground/60">{exp.location}</p>}
                </div>
              ))}
            </div>
          ) : <p className="text-sm text-muted-foreground/60">No experience entries</p>}
        </Section>

        {/* Skills */}
        <Section title="Skills" href="/onboarding/skills">
          {draft.skills && draft.skills.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {draft.skills.map((sk) => (
                <span key={sk.id} className="evidence-pill">{sk.name} · {sk.proficiency}</span>
              ))}
            </div>
          ) : <p className="text-sm text-muted-foreground/60">No skills added</p>}
        </Section>

        {/* CV */}
        <Section title="CV / Resume" href="/onboarding/cv-upload">
          {draft.cvDocument ? (
            <div className="flex items-center gap-3">
              <Upload className="h-4 w-4 text-emerald-400" />
              <div>
                <p className="text-sm font-medium text-foreground">{draft.cvDocument.fileName}</p>
                <p className="text-xs text-muted-foreground">{(draft.cvDocument.fileSize / 1024).toFixed(1)} KB · {draft.cvDocument.status}</p>
              </div>
            </div>
          ) : <p className="text-sm text-muted-foreground/60">No CV uploaded</p>}
        </Section>

        {/* Links */}
        <Section title="Professional Links" href="/onboarding/links">
          {draft.links && Object.keys(draft.links).length > 0 ? (
            <div className="space-y-1.5">
              {Object.entries(draft.links).filter(([, v]) => v).map(([k, v]) => (
                <div key={k} className="flex items-center gap-2">
                  <span className="w-20 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground/60 capitalize">{k}</span>
                  <a href={v as string} target="_blank" rel="noopener noreferrer" className="text-xs text-primary hover:underline truncate">{v as string}</a>
                </div>
              ))}
            </div>
          ) : <p className="text-sm text-muted-foreground/60">No links added</p>}
        </Section>

        {/* Preferences */}
        <Section title="Job Preferences" href="/onboarding/preferences">
          {prefs ? (
            <div className="space-y-2">
              {prefs.jobTypes?.length > 0 && (
                <div className="flex gap-2 flex-wrap">
                  {prefs.jobTypes.map((t) => <span key={t} className="evidence-pill capitalize">{t.replace("_", "-")}</span>)}
                </div>
              )}
              {prefs.workplaceTypes?.length > 0 && (
                <div className="flex gap-2 flex-wrap">
                  {prefs.workplaceTypes.map((t) => <span key={t} className="evidence-pill capitalize">{t}</span>)}
                </div>
              )}
              {(prefs.desiredSalaryMin || prefs.desiredSalaryMax) && (
                <p className="text-sm text-muted-foreground">
                  Salary: {prefs.salaryCurrency} {prefs.desiredSalaryMin?.toLocaleString()} – {prefs.desiredSalaryMax?.toLocaleString()}
                </p>
              )}
            </div>
          ) : <p className="text-sm text-muted-foreground/60">No preferences set</p>}
        </Section>
      </div>

      {error && (
        <div className="mt-6 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">{error}</div>
      )}

      <div className="mt-8 flex items-center justify-between">
        <Button type="button" variant="ghost" className="gap-2" onClick={() => router.push("/onboarding/preferences")}>
          <ArrowLeft className="h-4 w-4" /> Back
        </Button>
        <Button
          type="button"
          size="lg"
          className="gap-2 glow-blue px-8"
          disabled={isSubmitting}
          onClick={onSubmit}
        >
          {isSubmitting ? (
            <><Loader2 className="h-4 w-4 animate-spin" /> Submitting Profile…</>
          ) : (
            <><CheckCircle2 className="h-4 w-4" /> Submit Profile</>
          )}
        </Button>
      </div>

      <p className="mt-4 text-center text-[11px] text-muted-foreground/60">
        By submitting you agree to our Terms of Service and Privacy Policy. Your profile will be visible to companies using PATHS.
      </p>
    </motion.div>
  );
}

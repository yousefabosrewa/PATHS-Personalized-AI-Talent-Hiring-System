"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowLeft, ArrowRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useOnboardingStore } from "@/lib/stores/onboarding.store";
import { cn } from "@/lib/utils/cn";

const schema = z.object({
  fullName:        z.string().min(2, "Full name must be at least 2 characters"),
  currentTitle:    z.string().min(2, "Current title is required"),
  summary:         z.string().min(50, "Summary must be at least 50 characters").max(1000),
  careerLevel:     z.enum(["junior", "mid", "senior", "lead", "manager", "director", "executive"]),
  yearsExperience: z.number().min(0).max(50),
});

type FormValues = z.infer<typeof schema>;

const careerLevels = [
  { value: "junior",    label: "Junior"    },
  { value: "mid",       label: "Mid-level" },
  { value: "senior",    label: "Senior"    },
  { value: "lead",      label: "Lead"      },
  { value: "manager",   label: "Manager"   },
  { value: "director",  label: "Director"  },
  { value: "executive", label: "Executive" },
];

function BasicInfoForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { draft, updateDraft, markStepComplete, saveDraft, setPostOnboardingRedirect } = useOnboardingStore();

  // Capture the intent URL once, on mount — persisted in the store so it
  // survives the entire 9-step onboarding flow and is available on review.
  useEffect(() => {
    const redirectTo = searchParams.get("redirectTo");
    if (redirectTo) setPostOnboardingRedirect(decodeURIComponent(redirectTo));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      fullName:        draft.fullName        ?? "",
      currentTitle:    draft.currentTitle    ?? "",
      summary:         draft.summary         ?? "",
      careerLevel:     draft.careerLevel     ?? "mid",
      yearsExperience: draft.yearsExperience ?? 0,
    },
  });

  const onSubmit = async (data: FormValues) => {
    updateDraft(data);
    markStepComplete("basic-info");
    await saveDraft();
    router.push("/onboarding/contact");
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="mx-auto max-w-2xl px-6 py-10"
    >
      <div className="mb-8">
        <p className="text-xs font-semibold uppercase tracking-widest text-primary">Step 2 of 9</p>
        <h1 className="mt-1 font-heading text-3xl font-bold text-foreground">Basic Information</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Review what we read from your CV and fix anything that&apos;s off.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Full name */}
        <div className="space-y-1.5">
          <Label htmlFor="fullName" className="text-sm font-medium">Full Name</Label>
          <Input
            id="fullName"
            placeholder="Your full name"
            autoFocus
            {...register("fullName")}
            className={cn("h-11", errors.fullName && "border-destructive")}
          />
          {errors.fullName && <p className="text-xs text-destructive">{errors.fullName.message}</p>}
        </div>

        {/* Current title */}
        <div className="space-y-1.5">
          <Label htmlFor="currentTitle" className="text-sm font-medium">Current / Most Recent Title</Label>
          <Input
            id="currentTitle"
            placeholder="Senior Software Engineer"
            {...register("currentTitle")}
            className={cn("h-11", errors.currentTitle && "border-destructive")}
          />
          {errors.currentTitle && <p className="text-xs text-destructive">{errors.currentTitle.message}</p>}
        </div>

        {/* Career level + years */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="careerLevel" className="text-sm font-medium">Career Level</Label>
            <select
              id="careerLevel"
              {...register("careerLevel")}
              className={cn(
                "flex h-11 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                errors.careerLevel && "border-destructive"
              )}
            >
              {careerLevels.map((l) => (
                <option key={l.value} value={l.value}>{l.label}</option>
              ))}
            </select>
            {errors.careerLevel && <p className="text-xs text-destructive">{errors.careerLevel.message}</p>}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="yearsExperience" className="text-sm font-medium">Years of Experience</Label>
            <Input
              id="yearsExperience"
              type="number"
              min={0}
              max={50}
              placeholder="5"
              {...register("yearsExperience", { valueAsNumber: true })}
              className={cn("h-11", errors.yearsExperience && "border-destructive")}
            />
            {errors.yearsExperience && <p className="text-xs text-destructive">{errors.yearsExperience.message}</p>}
          </div>
        </div>

        {/* Professional summary */}
        <div className="space-y-1.5">
          <Label htmlFor="summary" className="text-sm font-medium">Professional Summary</Label>
          <textarea
            id="summary"
            rows={5}
            placeholder="Write 2–4 sentences describing your background, key skills, and what you're looking for in your next role…"
            {...register("summary")}
            className={cn(
              "flex min-h-[120px] w-full resize-y rounded-lg border border-border bg-background px-3 py-2.5 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              errors.summary && "border-destructive"
            )}
          />
          {errors.summary && <p className="text-xs text-destructive">{errors.summary.message}</p>}
          <p className="text-[11px] text-muted-foreground/60">Minimum 50 characters. This becomes your AI-generated pitch to recruiters.</p>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between pt-2">
          <Button type="button" variant="ghost" className="gap-2" onClick={() => router.push("/onboarding/cv-upload")}>
            <ArrowLeft className="h-4 w-4" /> Back
          </Button>
          <Button type="submit" className="gap-2 glow-blue" disabled={isSubmitting}>
            {isSubmitting ? (
              <><Loader2 className="h-4 w-4 animate-spin" /> Saving…</>
            ) : (
              <>Save &amp; Continue <ArrowRight className="h-4 w-4" /></>
            )}
          </Button>
        </div>
      </form>
    </motion.div>
  );
}

export default function BasicInfoPage() {
  return (
    <Suspense>
      <BasicInfoForm />
    </Suspense>
  );
}

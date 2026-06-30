"use client";

import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowLeft, ArrowRight, Plus, Trash2, Loader2, Briefcase } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useOnboardingStore } from "@/lib/stores/onboarding.store";
import { cn } from "@/lib/utils/cn";

const expSchema = z.object({
  id:          z.string(),
  companyName: z.string().min(1, "Company name is required"),
  title:       z.string().min(1, "Job title is required"),
  location:    z.string().optional(),
  startDate:   z.string().min(1, "Start date is required"),
  endDate:     z.string().nullable(),
  isCurrent:   z.boolean(),
  description: z.string().optional(),
});

const schema = z.object({ experiences: z.array(expSchema) });
type FormValues = z.infer<typeof schema>;

function newExp() {
  return {
    id: crypto.randomUUID(),
    companyName: "", title: "", location: "",
    startDate: "", endDate: null, isCurrent: false, description: "",
  };
}

export default function ExperiencePage() {
  const router = useRouter();
  const { draft, updateDraft, markStepComplete, saveDraft } = useOnboardingStore();

  const { register, control, handleSubmit, watch, setValue, formState: { errors, isSubmitting } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      experiences: draft.experiences && draft.experiences.length > 0
        ? draft.experiences
        : [newExp()],
    },
  });

  const { fields, append, remove } = useFieldArray({ control, name: "experiences" });

  const onSubmit = async (data: FormValues) => {
    updateDraft({ experiences: data.experiences });
    markStepComplete("experience");
    await saveDraft();
    router.push("/onboarding/education");
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="mx-auto max-w-2xl px-6 py-10"
    >
      <div className="mb-8">
        <p className="text-xs font-semibold uppercase tracking-widest text-primary">Step 5 of 9</p>
        <h1 className="mt-1 font-heading text-3xl font-bold text-foreground">Work Experience</h1>
        <p className="mt-2 text-sm text-muted-foreground">Add your work history, most recent first.</p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        <AnimatePresence>
          {fields.map((field, i) => {
            const isCurrent = watch(`experiences.${i}.isCurrent`);
            const errs = errors.experiences?.[i];
            return (
              <motion.div
                key={field.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="glass gradient-border rounded-2xl p-6 space-y-4"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Briefcase className="h-4 w-4 text-primary" />
                    <span className="text-sm font-semibold text-foreground">Position {i + 1}</span>
                    {isCurrent && <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-400">Current</span>}
                  </div>
                  {fields.length > 1 && (
                    <button type="button" onClick={() => remove(i)} className="text-muted-foreground/60 hover:text-destructive transition-colors">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>

                {/* Title + Company */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label className="text-sm font-medium">Job Title</Label>
                    <Input placeholder="Software Engineer" {...register(`experiences.${i}.title`)} className={cn("h-10", errs?.title && "border-destructive")} />
                    {errs?.title && <p className="text-xs text-destructive">{errs.title.message}</p>}
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-sm font-medium">Company</Label>
                    <Input placeholder="Acme Corp" {...register(`experiences.${i}.companyName`)} className={cn("h-10", errs?.companyName && "border-destructive")} />
                    {errs?.companyName && <p className="text-xs text-destructive">{errs.companyName.message}</p>}
                  </div>
                </div>

                {/* Location */}
                <div className="space-y-1.5">
                  <Label className="text-sm font-medium">Location <span className="text-muted-foreground/60">(optional)</span></Label>
                  <Input placeholder="Cairo, Egypt · Remote" {...register(`experiences.${i}.location`)} className="h-10" />
                </div>

                {/* Dates */}
                <div className="grid grid-cols-3 gap-3 items-end">
                  <div className="space-y-1.5">
                    <Label className="text-sm font-medium">Start</Label>
                    <Input type="month" {...register(`experiences.${i}.startDate`)} className={cn("h-10", errs?.startDate && "border-destructive")} />
                    {errs?.startDate && <p className="text-xs text-destructive">{errs.startDate.message}</p>}
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-sm font-medium">End</Label>
                    <Input
                      type="month"
                      disabled={isCurrent}
                      {...register(`experiences.${i}.endDate`)}
                      className={cn("h-10", isCurrent && "opacity-40")}
                    />
                  </div>
                  <label className="flex items-center gap-2 cursor-pointer pb-2">
                    <input
                      type="checkbox"
                      {...register(`experiences.${i}.isCurrent`)}
                      onChange={(e) => {
                        setValue(`experiences.${i}.isCurrent`, e.target.checked);
                        if (e.target.checked) setValue(`experiences.${i}.endDate`, null);
                      }}
                      className="h-4 w-4 rounded border-border accent-primary"
                    />
                    <span className="text-xs text-muted-foreground">Current role</span>
                  </label>
                </div>

                {/* Description */}
                <div className="space-y-1.5">
                  <Label className="text-sm font-medium">Key Responsibilities &amp; Achievements <span className="text-muted-foreground/60">(optional)</span></Label>
                  <textarea
                    rows={4}
                    placeholder="Describe your main responsibilities, technologies used, and key achievements…"
                    {...register(`experiences.${i}.description`)}
                    className="flex min-h-[96px] w-full resize-y rounded-lg border border-border bg-background px-3 py-2.5 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  />
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>

        <button
          type="button"
          onClick={() => append(newExp())}
          className="flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-border/60 py-3 text-sm text-muted-foreground hover:border-primary/40 hover:text-primary transition-colors"
        >
          <Plus className="h-4 w-4" /> Add Another Position
        </button>

        <div className="flex items-center justify-between pt-2">
          <Button type="button" variant="ghost" className="gap-2" onClick={() => router.push("/onboarding/skills")}>
            <ArrowLeft className="h-4 w-4" /> Back
          </Button>
          <Button type="submit" className="gap-2 glow-blue" disabled={isSubmitting}>
            {isSubmitting ? <><Loader2 className="h-4 w-4 animate-spin" /> Saving…</> : <>Save &amp; Continue <ArrowRight className="h-4 w-4" /></>}
          </Button>
        </div>
      </form>
    </motion.div>
  );
}

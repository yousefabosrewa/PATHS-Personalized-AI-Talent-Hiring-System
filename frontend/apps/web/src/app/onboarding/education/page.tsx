"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowLeft, ArrowRight, Plus, Trash2, Loader2, GraduationCap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useOnboardingStore } from "@/lib/stores/onboarding.store";
import { cn } from "@/lib/utils/cn";

const educationSchema = z.object({
  id:           z.string(),
  institution:  z.string().min(1, "Institution is required"),
  degree:       z.string().min(1, "Degree is required"),
  fieldOfStudy: z.string().min(1, "Field of study is required"),
  startYear:    z.number().min(1950).max(2030).nullable(),
  endYear:      z.number().min(1950).max(2030).nullable(),
  isOngoing:    z.boolean(),
  gpa:          z.string().optional(),
  description:  z.string().optional(),
});

const schema = z.object({
  education: z.array(educationSchema),
});

type FormValues = z.infer<typeof schema>;

const degrees = [
  "High School Diploma", "Associate's Degree", "Bachelor of Science", "Bachelor of Arts",
  "Bachelor of Engineering", "Master of Science", "Master of Arts", "MBA",
  "Doctor of Philosophy (PhD)", "Postdoctoral", "Professional Certificate", "Bootcamp Certificate", "Other",
];

export default function EducationPage() {
  const router = useRouter();
  const { draft, updateDraft, markStepComplete, saveDraft } = useOnboardingStore();

  const { register, control, handleSubmit, watch, setValue, formState: { errors, isSubmitting } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      education: draft.education && draft.education.length > 0
        ? draft.education
        : [{
            id: crypto.randomUUID(),
            institution: "", degree: "", fieldOfStudy: "",
            startYear: null, endYear: null, isOngoing: false,
            gpa: "", description: "",
          }],
    },
  });

  const { fields, append, remove } = useFieldArray({ control, name: "education" });

  const onSubmit = async (data: FormValues) => {
    updateDraft({ education: data.education });
    markStepComplete("education");
    await saveDraft();
    router.push("/onboarding/links");
  };

  const addEntry = () => {
    append({
      id: crypto.randomUUID(),
      institution: "", degree: "", fieldOfStudy: "",
      startYear: null, endYear: null, isOngoing: false,
      gpa: "", description: "",
    });
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="mx-auto max-w-2xl px-6 py-10"
    >
      <div className="mb-8">
        <p className="text-xs font-semibold uppercase tracking-widest text-primary">Step 6 of 9</p>
        <h1 className="mt-1 font-heading text-3xl font-bold text-foreground">Education</h1>
        <p className="mt-2 text-sm text-muted-foreground">Add your academic background. Add multiple entries if needed.</p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        <AnimatePresence>
          {fields.map((field, i) => {
            const isOngoing = watch(`education.${i}.isOngoing`);
            const errs = errors.education?.[i];
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
                    <GraduationCap className="h-4 w-4 text-primary" />
                    <span className="text-sm font-semibold text-foreground">Education {i + 1}</span>
                  </div>
                  {fields.length > 1 && (
                    <button type="button" onClick={() => remove(i)} className="text-muted-foreground/60 hover:text-destructive transition-colors">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>

                {/* Institution */}
                <div className="space-y-1.5">
                  <Label className="text-sm font-medium">Institution</Label>
                  <Input
                    placeholder="Cairo University"
                    {...register(`education.${i}.institution`)}
                    className={cn("h-10", errs?.institution && "border-destructive")}
                  />
                  {errs?.institution && <p className="text-xs text-destructive">{errs.institution.message}</p>}
                </div>

                {/* Degree + Field */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label className="text-sm font-medium">Degree</Label>
                    <select
                      {...register(`education.${i}.degree`)}
                      className={cn(
                        "flex h-10 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                        errs?.degree && "border-destructive"
                      )}
                    >
                      <option value="">Select degree…</option>
                      {degrees.map((d) => <option key={d} value={d}>{d}</option>)}
                    </select>
                    {errs?.degree && <p className="text-xs text-destructive">{errs.degree.message}</p>}
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-sm font-medium">Field of Study</Label>
                    <Input
                      placeholder="Computer Science"
                      {...register(`education.${i}.fieldOfStudy`)}
                      className={cn("h-10", errs?.fieldOfStudy && "border-destructive")}
                    />
                    {errs?.fieldOfStudy && <p className="text-xs text-destructive">{errs.fieldOfStudy.message}</p>}
                  </div>
                </div>

                {/* Years */}
                <div className="grid grid-cols-3 gap-3 items-end">
                  <div className="space-y-1.5">
                    <Label className="text-sm font-medium">Start Year</Label>
                    <Input type="number" min={1950} max={2030} placeholder="2018" {...register(`education.${i}.startYear`, { setValueAs: (v: string) => v === "" ? null : Number(v) })} className="h-10" />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-sm font-medium">End Year</Label>
                    <Input
                      type="number" min={1950} max={2030} placeholder="2022"
                      disabled={isOngoing}
                      {...register(`education.${i}.endYear`, { setValueAs: (v: string) => v === "" ? null : Number(v) })}
                      className={cn("h-10", isOngoing && "opacity-40")}
                    />
                  </div>
                  <label className="flex items-center gap-2 cursor-pointer pb-2">
                    <input
                      type="checkbox"
                      {...register(`education.${i}.isOngoing`)}
                      onChange={(e) => {
                        setValue(`education.${i}.isOngoing`, e.target.checked);
                        if (e.target.checked) setValue(`education.${i}.endYear`, null);
                      }}
                      className="h-4 w-4 rounded border-border accent-primary"
                    />
                    <span className="text-xs text-muted-foreground">Ongoing</span>
                  </label>
                </div>

                {/* GPA (optional) */}
                <div className="space-y-1.5">
                  <Label className="text-sm font-medium">GPA <span className="text-muted-foreground/60">(optional)</span></Label>
                  <Input placeholder="3.8 / 4.0" {...register(`education.${i}.gpa`)} className="h-10 w-48" />
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>

        <button
          type="button"
          onClick={addEntry}
          className="flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-border/60 py-3 text-sm text-muted-foreground hover:border-primary/40 hover:text-primary transition-colors"
        >
          <Plus className="h-4 w-4" /> Add Another Degree
        </button>

        <div className="flex items-center justify-between pt-2">
          <Button type="button" variant="ghost" className="gap-2" onClick={() => router.push("/onboarding/experience")}>
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

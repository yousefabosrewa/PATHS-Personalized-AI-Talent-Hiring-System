"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  ArrowLeft, ArrowRight, Check, Loader2, Shield, Workflow,
  ClipboardCheck, FileSearch, Users, Code2, MessageSquare,
  ArrowUp, ArrowDown, Trash2, Plus, Flag, CheckCircle2, X,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { JobPipelineStage, PipelineStageKind } from "@/lib/api";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import { useCreateJob, useUpdateFairnessRubric } from "@/lib/hooks";

// ── Step schemas ────────────────────────────────────────────────────────────

const step1Schema = z.object({
  title: z.string().min(2, "Title is required"),
  description: z.string().optional(),
  location: z.string().optional(),
  employment_type: z.string().optional(),
  workplace_type: z.string().optional(),
  seniority_level: z.string().optional(),
  // Required skills for this specific job (chip input).
  skills: z.array(z.string()).optional(),
});

const step2Schema = z.object({
  salary_min: z.string().optional(),
  salary_max: z.string().optional(),
  min_years_experience: z.string().optional(),
  max_years_experience: z.string().optional(),
  // Fixes.md §2: company name is inferred from the authenticated recruiter's
  // organization on the backend — recruiters never re-type it here.
});

type Step1Values = z.infer<typeof step1Schema>;
type Step2Values = z.infer<typeof step2Schema>;

interface FairnessConfig {
  enabled: boolean;
  disparate_impact_threshold: number;
  protected_attrs: Record<string, boolean>;
}

const PROTECTED_ATTRS = ["gender", "race_ethnicity", "age", "disability", "veteran_status"];

const STEPS = ["Basic Info", "Requirements", "Pipeline", "Fairness Rubric"];

// ── Hiring pipeline (configurable candidate workflow) ────────────────────────

type PipelineStage = { key: string; kind: PipelineStageKind; label: string };

const STAGE_PALETTE: {
  kind: PipelineStageKind;
  label: string;
  desc: string;
  Icon: typeof Users;
}[] = [
  { kind: "screening", label: "CV Screening", desc: "Automated résumé review & ranking", Icon: FileSearch },
  { kind: "assessment", label: "Skills Assessment", desc: "Online skills / knowledge test", Icon: ClipboardCheck },
  { kind: "hr_interview", label: "HR Interview", desc: "Culture, motivation & logistics", Icon: Users },
  { kind: "technical_interview", label: "Technical Interview", desc: "Hands-on / domain deep-dive", Icon: Code2 },
  { kind: "mixed_interview", label: "Mixed Interview", desc: "Combined technical + behavioural", Icon: MessageSquare },
];

const PALETTE_BY_KIND = Object.fromEntries(STAGE_PALETTE.map((p) => [p.kind, p]));

const DEFAULT_PIPELINE: PipelineStage[] = [
  { key: "screening", kind: "screening", label: "CV Screening" },
  { key: "hr_interview", kind: "hr_interview", label: "HR Interview" },
];

let _stageSeq = 0;
function makeStage(kind: PipelineStageKind): PipelineStage {
  _stageSeq += 1;
  return { key: `${kind}_${Date.now()}_${_stageSeq}`, kind, label: PALETTE_BY_KIND[kind].label };
}

function PipelineStep({
  pipeline,
  onChange,
  onBack,
  onNext,
}: {
  pipeline: PipelineStage[];
  onChange: (p: PipelineStage[]) => void;
  onBack: () => void;
  onNext: () => void;
}) {
  const add = (kind: PipelineStageKind) => onChange([...pipeline, makeStage(kind)]);
  const remove = (key: string) => onChange(pipeline.filter((s) => s.key !== key));
  const rename = (key: string, label: string) =>
    onChange(pipeline.map((s) => (s.key === key ? { ...s, label } : s)));
  const move = (idx: number, dir: -1 | 1) => {
    const next = [...pipeline];
    const target = idx + dir;
    if (target < 0 || target >= next.length) return;
    [next[idx], next[target]] = [next[target], next[idx]];
    onChange(next);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start gap-2">
        <Workflow className="mt-0.5 h-5 w-5 shrink-0 text-blue-500" />
        <div>
          <h2 className="text-base font-semibold">Hiring pipeline</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Choose the exact stages a candidate moves through for this job. Reorder or remove
            them freely — every job can have its own workflow.
          </p>
        </div>
      </div>

      {/* Palette */}
      <div className="space-y-2">
        <Label className="text-xs uppercase tracking-wide text-muted-foreground">Add a stage</Label>
        <div className="grid gap-2 sm:grid-cols-2">
          {STAGE_PALETTE.map(({ kind, label, desc, Icon }) => (
            <button
              key={kind}
              type="button"
              onClick={() => add(kind)}
              className="flex items-center gap-3 rounded-lg border border-border bg-card px-3 py-2.5 text-left transition-colors hover:border-primary/50 hover:bg-primary/5"
            >
              <Icon className="h-4 w-4 shrink-0 text-primary" />
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium">{label}</span>
                <span className="block truncate text-[11px] text-muted-foreground">{desc}</span>
              </span>
              <Plus className="h-4 w-4 shrink-0 text-muted-foreground" />
            </button>
          ))}
        </div>
      </div>

      {/* Configured flow */}
      <div className="space-y-2">
        <Label className="text-xs uppercase tracking-wide text-muted-foreground">
          Candidate workflow ({pipeline.length} {pipeline.length === 1 ? "stage" : "stages"})
        </Label>

        {/* Implicit start */}
        <div className="flex items-center gap-2 rounded-lg border border-dashed border-border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
          <Flag className="h-4 w-4 text-emerald-500" /> Applied
          <span className="ml-auto text-[10px] uppercase tracking-wide">start</span>
        </div>

        {pipeline.length === 0 && (
          <p className="rounded-lg border border-dashed border-border px-3 py-4 text-center text-xs text-muted-foreground">
            No stages yet — add at least one from above, or candidates go straight to a decision.
          </p>
        )}

        {pipeline.map((stage, idx) => {
          const meta = PALETTE_BY_KIND[stage.kind];
          const Icon = meta?.Icon ?? Users;
          return (
            <div
              key={stage.key}
              className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2"
            >
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[11px] font-bold text-primary">
                {idx + 1}
              </span>
              <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
              <Input
                value={stage.label}
                onChange={(e) => rename(stage.key, e.target.value)}
                className="h-8 flex-1 border-transparent bg-transparent px-1 text-sm focus-visible:border-border focus-visible:bg-background"
              />
              <span className="hidden shrink-0 rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground sm:inline">
                {meta?.label ?? stage.kind}
              </span>
              <div className="flex shrink-0 items-center">
                <button type="button" onClick={() => move(idx, -1)} disabled={idx === 0}
                  className="rounded p-1 text-muted-foreground hover:bg-muted disabled:opacity-30" title="Move up">
                  <ArrowUp className="h-3.5 w-3.5" />
                </button>
                <button type="button" onClick={() => move(idx, 1)} disabled={idx === pipeline.length - 1}
                  className="rounded p-1 text-muted-foreground hover:bg-muted disabled:opacity-30" title="Move down">
                  <ArrowDown className="h-3.5 w-3.5" />
                </button>
                <button type="button" onClick={() => remove(stage.key)}
                  className="rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive" title="Remove">
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          );
        })}

        {/* Implicit finish */}
        <div className="flex items-center gap-2 rounded-lg border border-dashed border-border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
          <CheckCircle2 className="h-4 w-4 text-blue-500" /> Offer → Hired
          <span className="ml-auto text-[10px] uppercase tracking-wide">decision</span>
        </div>
      </div>

      <div className="flex justify-between">
        <Button type="button" variant="outline" onClick={onBack} className="gap-2">
          <ArrowLeft className="h-4 w-4" /> Back
        </Button>
        <Button type="button" onClick={onNext} className="gap-2">
          Next <ArrowRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

// ── Sub-forms ────────────────────────────────────────────────────────────────

function Step1Form({
  defaultValues,
  onNext,
}: {
  defaultValues: Partial<Step1Values>;
  onNext: (v: Step1Values) => void;
}) {
  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm<Step1Values>({ resolver: zodResolver(step1Schema), defaultValues });

  // Required-skills chip input: type a skill, press Enter (or +) to add more.
  const [skillDraft, setSkillDraft] = useState("");
  const skills = watch("skills") ?? [];

  function addSkill() {
    const name = skillDraft.trim().replace(/,+$/, "");
    if (!name) return;
    if (skills.some((s) => s.toLowerCase() === name.toLowerCase())) {
      setSkillDraft("");
      return;
    }
    setValue("skills", [...skills, name]);
    setSkillDraft("");
  }

  function removeSkill(name: string) {
    setValue("skills", skills.filter((s) => s !== name));
  }

  return (
    <form onSubmit={handleSubmit(onNext)} className="space-y-5">
      <div className="space-y-1.5">
        <Label htmlFor="title">Job title *</Label>
        <Input id="title" {...register("title")} placeholder="e.g. Senior Software Engineer" />
        {errors.title && <p className="text-xs text-destructive">{errors.title.message}</p>}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="employment_type">Employment type</Label>
          <Select
            value={watch("employment_type") ?? ""}
            onValueChange={(v) => setValue("employment_type", v ?? undefined)}
          >
            <SelectTrigger id="employment_type">
              <SelectValue placeholder="Select…" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="full_time">Full-time</SelectItem>
              <SelectItem value="part_time">Part-time</SelectItem>
              <SelectItem value="contract">Contract</SelectItem>
              <SelectItem value="internship">Internship</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="workplace_type">Work mode</Label>
          <Select
            value={watch("workplace_type") ?? ""}
            onValueChange={(v) => setValue("workplace_type", v ?? undefined)}
          >
            <SelectTrigger id="workplace_type">
              <SelectValue placeholder="Select…" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="remote">Remote</SelectItem>
              <SelectItem value="onsite">On-site</SelectItem>
              <SelectItem value="hybrid">Hybrid</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="location">Location</Label>
          <Input id="location" {...register("location")} placeholder="City, Country" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="seniority_level">Seniority</Label>
          <Select
            value={watch("seniority_level") ?? ""}
            onValueChange={(v) => setValue("seniority_level", v ?? undefined)}
          >
            <SelectTrigger id="seniority_level">
              <SelectValue placeholder="Select…" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="entry">Entry</SelectItem>
              <SelectItem value="mid">Mid</SelectItem>
              <SelectItem value="senior">Senior</SelectItem>
              <SelectItem value="lead">Lead</SelectItem>
              <SelectItem value="principal">Principal</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="description">Description</Label>
        <Textarea
          id="description"
          {...register("description")}
          placeholder="Describe the role, responsibilities, and team…"
          rows={5}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="skill-input">Required skills</Label>
        <div className="flex gap-2">
          <Input
            id="skill-input"
            value={skillDraft}
            onChange={(e) => setSkillDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === ",") {
                e.preventDefault();
                addSkill();
              }
            }}
            placeholder="e.g. Python — press Enter to add"
          />
          <Button
            type="button"
            variant="outline"
            onClick={addSkill}
            disabled={!skillDraft.trim()}
            className="gap-1 shrink-0"
          >
            <Plus className="h-4 w-4" /> Add
          </Button>
        </div>
        {skills.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1.5">
            {skills.map((s) => (
              <span
                key={s}
                className="inline-flex items-center gap-1 rounded-full border border-primary/25 bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary"
              >
                {s}
                <button
                  type="button"
                  onClick={() => removeSkill(s)}
                  className="rounded-full p-0.5 hover:bg-primary/20"
                  aria-label={`Remove ${s}`}
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
        )}
        <p className="text-[11px] text-muted-foreground">
          These count toward candidate match scores for this job.
        </p>
      </div>

      <div className="flex justify-end">
        <Button type="submit" className="gap-2">
          Next <ArrowRight className="h-4 w-4" />
        </Button>
      </div>
    </form>
  );
}

function Step2Form({
  defaultValues,
  onBack,
  onNext,
}: {
  defaultValues: Partial<Step2Values>;
  onBack: () => void;
  onNext: (v: Step2Values) => void;
}) {
  const { register, handleSubmit } = useForm<Step2Values>({
    resolver: zodResolver(step2Schema),
    defaultValues,
  });

  return (
    <form onSubmit={handleSubmit(onNext)} className="space-y-5">
      {/* Fixes.md §2: company name removed — derived from the recruiter's
          organization on the backend.  See create_job() in jobs.py. */}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="salary_min">Salary min (USD)</Label>
          <Input
            id="salary_min"
            type="number"
            min={0}
            {...register("salary_min")}
            placeholder="60000"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="salary_max">Salary max (USD)</Label>
          <Input
            id="salary_max"
            type="number"
            min={0}
            {...register("salary_max")}
            placeholder="90000"
          />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="min_years_experience">Min years experience</Label>
          <Input
            id="min_years_experience"
            type="number"
            min={0}
            {...register("min_years_experience")}
            placeholder="2"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="max_years_experience">Max years experience</Label>
          <Input
            id="max_years_experience"
            type="number"
            min={0}
            {...register("max_years_experience")}
            placeholder="8"
          />
        </div>
      </div>

      <div className="flex justify-between">
        <Button type="button" variant="outline" onClick={onBack} className="gap-2">
          <ArrowLeft className="h-4 w-4" /> Back
        </Button>
        <Button type="submit" className="gap-2">
          Next <ArrowRight className="h-4 w-4" />
        </Button>
      </div>
    </form>
  );
}

function Step3Form({
  config,
  onChange,
  onBack,
  onSubmit,
  isSubmitting,
}: {
  config: FairnessConfig;
  onChange: (c: FairnessConfig) => void;
  onBack: () => void;
  onSubmit: () => void;
  isSubmitting: boolean;
}) {
  function toggleAttr(attr: string) {
    onChange({
      ...config,
      protected_attrs: {
        ...config.protected_attrs,
        [attr]: !config.protected_attrs[attr],
      },
    });
  }

  return (
    <div className="space-y-6">
      {/* Enable toggle */}
      <div className="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-4 py-3">
        <div>
          <p className="text-sm font-medium">Enable fairness monitoring</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Flags candidates if selection rates across protected groups diverge beyond the threshold.
          </p>
        </div>
        <Switch
          checked={config.enabled}
          onCheckedChange={(v) => onChange({ ...config, enabled: v })}
        />
      </div>

      {config.enabled && (
        <>
          {/* Threshold */}
          <div className="space-y-2">
            <Label htmlFor="threshold">
              4/5ths threshold (disparate impact ratio)
              <span className="ml-2 font-normal text-muted-foreground text-xs">
                {(config.disparate_impact_threshold * 100).toFixed(0)}%
              </span>
            </Label>
            <input
              id="threshold"
              type="range"
              min={60}
              max={95}
              step={5}
              value={config.disparate_impact_threshold * 100}
              onChange={(e) =>
                onChange({
                  ...config,
                  disparate_impact_threshold: Number(e.target.value) / 100,
                })
              }
              className="w-full accent-primary"
            />
            <div className="flex justify-between text-[10px] text-muted-foreground">
              <span>60% (lenient)</span>
              <span>80% (standard)</span>
              <span>95% (strict)</span>
            </div>
            <p className="text-xs text-muted-foreground">
              EEOC recommends 80%. Any group&apos;s selection rate must be ≥{" "}
              {(config.disparate_impact_threshold * 100).toFixed(0)}% of the highest-rate group.
            </p>
          </div>

          {/* Protected attributes */}
          <div className="space-y-2">
            <Label>Protected attributes to monitor</Label>
            <div className="grid gap-2 sm:grid-cols-2">
              {PROTECTED_ATTRS.map((attr) => (
                <label
                  key={attr}
                  className={cn(
                    "flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2.5 text-sm transition-colors",
                    config.protected_attrs[attr]
                      ? "border-primary/50 bg-primary/5"
                      : "border-border bg-transparent",
                  )}
                >
                  <input
                    type="checkbox"
                    checked={!!config.protected_attrs[attr]}
                    onChange={() => toggleAttr(attr)}
                    className="rounded border-border accent-primary"
                  />
                  <span className="capitalize">{attr.replace(/_/g, " ")}</span>
                </label>
              ))}
            </div>
          </div>
        </>
      )}

      <div className="flex justify-between">
        <Button type="button" variant="outline" onClick={onBack} className="gap-2">
          <ArrowLeft className="h-4 w-4" /> Back
        </Button>
        <Button onClick={onSubmit} disabled={isSubmitting} className="gap-2">
          {isSubmitting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Check className="h-4 w-4" />
          )}
          Create Job
        </Button>
      </div>
    </div>
  );
}

// ── Main wizard page ─────────────────────────────────────────────────────────

export default function NewJobPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [step1Data, setStep1Data] = useState<Partial<Step1Values>>({});
  const [step2Data, setStep2Data] = useState<Partial<Step2Values>>({});
  const [pipeline, setPipeline] = useState<PipelineStage[]>(DEFAULT_PIPELINE);
  const [fairness, setFairness] = useState<FairnessConfig>({
    enabled: true,
    disparate_impact_threshold: 0.8,
    protected_attrs: Object.fromEntries(PROTECTED_ATTRS.map((a) => [a, true])),
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { mutateAsync: createJob } = useCreateJob();

  async function handleFinalSubmit() {
    setIsSubmitting(true);
    try {
      // Fixes.md §2 + §3:
      //   • No `company_name` — backend reads the recruiter's org from the JWT.
      //   • No `status: "draft"` — backend `create_job()` defaults to "active"
      //     (= "Live" in the recruiter UI), see jobs.py create_job().
      const body = {
        title: step1Data.title!,
        description_text: step1Data.description || undefined,
        skills: step1Data.skills?.length ? step1Data.skills : undefined,
        location_text: step1Data.location || undefined,
        employment_type: step1Data.employment_type || undefined,
        workplace_type: step1Data.workplace_type || undefined,
        seniority_level: step1Data.seniority_level || undefined,
        salary_min: step2Data.salary_min ? Number(step2Data.salary_min) : undefined,
        salary_max: step2Data.salary_max ? Number(step2Data.salary_max) : undefined,
        min_years_experience: step2Data.min_years_experience
          ? Number(step2Data.min_years_experience)
          : undefined,
        max_years_experience: step2Data.max_years_experience
          ? Number(step2Data.max_years_experience)
          : undefined,
        hiring_pipeline: pipeline.map<JobPipelineStage>((s) => ({
          key: s.key,
          kind: s.kind,
          label: s.label,
        })),
      };

      const job = await createJob(body);

      // Apply fairness rubric if enabled
      if (fairness.enabled) {
        try {
          const { putFairnessRubric: applyRubric } = await import("@/lib/api/index");
          await applyRubric(job.id, {
            protected_attrs: fairness.protected_attrs,
            disparate_impact_threshold: fairness.disparate_impact_threshold,
            enabled: true,
          });
        } catch {
          // Non-fatal: rubric can be set later from the job detail page
          toast.warning("Job created but fairness rubric could not be saved. Set it from job settings.");
        }
      }

      toast.success("Job created successfully!");
      router.push(`/jobs/${job.id}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create job.");
      setIsSubmitting(false);
    }
  }

  return (
    <div className="p-6 max-w-2xl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-xl font-bold">Create New Job</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Fill in the details to create a new job posting.
        </p>
      </div>

      {/* Step indicator */}
      <div className="mb-8 flex items-center gap-0">
        {STEPS.map((label, i) => (
          <div key={i} className="flex items-center">
            <div className="flex flex-col items-center">
              <div
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-full border-2 text-xs font-semibold transition-colors",
                  i < step
                    ? "border-primary bg-primary text-primary-foreground"
                    : i === step
                      ? "border-primary bg-background text-primary"
                      : "border-border bg-background text-muted-foreground",
                )}
              >
                {i < step ? <Check className="h-4 w-4" /> : i + 1}
              </div>
              <span
                className={cn(
                  "mt-1 text-[10px] font-medium whitespace-nowrap",
                  i === step ? "text-foreground" : "text-muted-foreground",
                )}
              >
                {label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div
                className={cn(
                  "mb-5 h-px w-16 transition-colors",
                  i < step ? "bg-primary" : "bg-border",
                )}
              />
            )}
          </div>
        ))}
      </div>

      {/* Step content */}
      <div className="rounded-xl border border-border bg-card p-6">
        {step === 0 && (
          <Step1Form
            defaultValues={step1Data}
            onNext={(v) => { setStep1Data(v); setStep(1); }}
          />
        )}
        {step === 1 && (
          <Step2Form
            defaultValues={step2Data}
            onBack={() => setStep(0)}
            onNext={(v) => { setStep2Data(v); setStep(2); }}
          />
        )}
        {step === 2 && (
          <PipelineStep
            pipeline={pipeline}
            onChange={setPipeline}
            onBack={() => setStep(1)}
            onNext={() => setStep(3)}
          />
        )}
        {step === 3 && (
          <>
            <div className="mb-5 flex items-center gap-2">
              <Shield className="h-5 w-5 text-blue-500" />
              <h2 className="text-base font-semibold">Fairness Rubric</h2>
            </div>
            <Step3Form
              config={fairness}
              onChange={setFairness}
              onBack={() => setStep(2)}
              onSubmit={handleFinalSubmit}
              isSubmitting={isSubmitting}
            />
          </>
        )}
      </div>
    </div>
  );
}

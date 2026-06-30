"use client";

/**
 * Edit Job — opens from the job header's "Edit Job" menu item.
 *
 * Loads the raw job, lets the recruiter edit the core fields, and PATCHes
 * via jobsApi.update. (Previously the menu item was inert and nothing opened.)
 */

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, Loader2, Save, Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { jobsApi, type BackendJob, type BackendJobWriteBody } from "@/lib/api";

const STATUS_OPTIONS = ["active", "draft", "closed", "inactive"];
const EMPLOYMENT_OPTIONS = ["full_time", "part_time", "contract", "internship", "temporary"];
const WORKPLACE_OPTIONS = ["remote", "hybrid", "onsite"];
const SENIORITY_OPTIONS = ["intern", "junior", "mid", "senior", "lead", "principal"];

type FormState = {
  title: string;
  status: string;
  location_text: string;
  employment_type: string;
  workplace_type: string;
  seniority_level: string;
  summary: string;
  description_text: string;
  requirements: string;
  salary_min: string;
  salary_max: string;
  skills: string[];
};

function fieldsFrom(job: BackendJob): FormState {
  return {
    title: job.title ?? "",
    status: job.status ?? "active",
    location_text: job.location_text ?? "",
    employment_type: job.employment_type ?? "",
    workplace_type: job.workplace_type ?? "",
    seniority_level: job.seniority_level ?? "",
    summary: job.summary ?? "",
    description_text: job.description_text ?? job.description ?? "",
    requirements: job.requirements ?? "",
    salary_min: job.salary_min != null ? String(job.salary_min) : "",
    salary_max: job.salary_max != null ? String(job.salary_max) : "",
    skills: (job.skills ?? []).map((s) => s.name),
  };
}

const labelCls = "text-[11px] font-semibold uppercase tracking-wide text-muted-foreground";
const inputCls =
  "mt-1 w-full rounded-lg border border-border/40 bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary/40";

export default function EditJobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const qc = useQueryClient();

  const { data: job, isLoading, isError } = useQuery({
    queryKey: ["job-raw", id],
    queryFn: () => jobsApi.get(id),
    enabled: Boolean(id),
  });

  const [form, setForm] = useState<FormState | null>(null);
  useEffect(() => {
    if (job && form === null) setForm(fieldsFrom(job));
  }, [job, form]);

  const update = useMutation({
    mutationFn: (body: BackendJobWriteBody) => jobsApi.update(id, body),
    onSuccess: () => {
      toast.success("Job updated.");
      qc.invalidateQueries({ queryKey: ["job", id] });
      qc.invalidateQueries({ queryKey: ["job-raw", id] });
      qc.invalidateQueries({ queryKey: ["jobs"] });
      router.push(`/jobs/${id}`);
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Could not update the job."),
  });

  const set = (k: keyof FormState, v: string) =>
    setForm((f) => (f ? { ...f, [k]: v } : f));

  // Required-skills chip input (structured → JobSkillRequirement rows).
  const [skillDraft, setSkillDraft] = useState("");
  function addSkill() {
    const name = skillDraft.trim().replace(/,+$/, "");
    if (!name) return;
    setForm((f) => {
      if (!f) return f;
      if (f.skills.some((s) => s.toLowerCase() === name.toLowerCase())) return f;
      return { ...f, skills: [...f.skills, name] };
    });
    setSkillDraft("");
  }
  function removeSkill(name: string) {
    setForm((f) => (f ? { ...f, skills: f.skills.filter((s) => s !== name) } : f));
  }

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form) return;
    if (!form.title.trim()) {
      toast.error("Title is required.");
      return;
    }
    const body: BackendJobWriteBody = {
      title: form.title.trim(),
      status: form.status,
      location_text: form.location_text.trim() || null,
      employment_type: form.employment_type || null,
      workplace_type: form.workplace_type || null,
      seniority_level: form.seniority_level || null,
      summary: form.summary.trim() || null,
      description_text: form.description_text.trim() || null,
      requirements: form.requirements.trim() || null,
      salary_min: form.salary_min ? Number(form.salary_min) : null,
      salary_max: form.salary_max ? Number(form.salary_max) : null,
      skills: form.skills,
    };
    update.mutate(body);
  };

  if (isLoading || (!form && !isError)) {
    return (
      <div className="flex flex-col gap-4 p-6 max-w-3xl">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }
  if (isError || !job || !form) {
    return (
      <div className="p-6">
        <p className="text-sm text-rose-400">Could not load this job.</p>
        <Button asChild variant="ghost" size="sm" className="mt-3">
          <Link href={`/jobs/${id}`}>Back to job</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mx-auto max-w-3xl space-y-5">
        <div className="flex items-center justify-between gap-3">
          <Button asChild variant="ghost" size="sm" className="gap-1.5 -ml-2 text-muted-foreground">
            <Link href={`/jobs/${id}`}>
              <ArrowLeft className="h-3.5 w-3.5" /> Back to job
            </Link>
          </Button>
        </div>
        <h1 className="text-2xl font-bold">Edit job</h1>

        <form onSubmit={onSubmit} className="glass gradient-border rounded-2xl p-6 space-y-4">
          <div>
            <label className={labelCls}>Title</label>
            <input className={inputCls} value={form.title} onChange={(e) => set("title", e.target.value)} required />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className={labelCls}>Status</label>
              <select className={inputCls} value={form.status} onChange={(e) => set("status", e.target.value)}>
                {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className={labelCls}>Location</label>
              <input className={inputCls} value={form.location_text} onChange={(e) => set("location_text", e.target.value)} placeholder="e.g. Cairo / Remote" />
            </div>
            <div>
              <label className={labelCls}>Employment type</label>
              <select className={inputCls} value={form.employment_type} onChange={(e) => set("employment_type", e.target.value)}>
                <option value="">—</option>
                {EMPLOYMENT_OPTIONS.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
              </select>
            </div>
            <div>
              <label className={labelCls}>Workplace</label>
              <select className={inputCls} value={form.workplace_type} onChange={(e) => set("workplace_type", e.target.value)}>
                <option value="">—</option>
                {WORKPLACE_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className={labelCls}>Seniority</label>
              <select className={inputCls} value={form.seniority_level} onChange={(e) => set("seniority_level", e.target.value)}>
                <option value="">—</option>
                {SENIORITY_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className={labelCls}>Salary min</label>
                <input type="number" className={inputCls} value={form.salary_min} onChange={(e) => set("salary_min", e.target.value)} />
              </div>
              <div>
                <label className={labelCls}>Salary max</label>
                <input type="number" className={inputCls} value={form.salary_max} onChange={(e) => set("salary_max", e.target.value)} />
              </div>
            </div>
          </div>

          <div>
            <label className={labelCls}>Summary</label>
            <textarea rows={3} className={inputCls + " resize-y"} value={form.summary} onChange={(e) => set("summary", e.target.value)} />
          </div>
          <div>
            <label className={labelCls}>Description</label>
            <textarea rows={6} className={inputCls + " resize-y"} value={form.description_text} onChange={(e) => set("description_text", e.target.value)} />
          </div>
          <div>
            <label className={labelCls}>Requirements</label>
            <textarea rows={5} className={inputCls + " resize-y"} value={form.requirements} onChange={(e) => set("requirements", e.target.value)} />
          </div>

          <div>
            <label className={labelCls}>Required skills</label>
            <div className="mt-1 flex gap-2">
              <input
                className="w-full rounded-lg border border-border/40 bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary/40"
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
            {form.skills.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-2">
                {form.skills.map((s) => (
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
            <p className="mt-1.5 text-[11px] text-muted-foreground">
              These show on the job card and count toward candidate match scores.
            </p>
          </div>

          <div className="flex items-center justify-end gap-2 pt-1">
            <Button asChild variant="ghost" size="sm">
              <Link href={`/jobs/${id}`}>Cancel</Link>
            </Button>
            <Button type="submit" className="gap-1.5 glow-blue" disabled={update.isPending}>
              {update.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              Save changes
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

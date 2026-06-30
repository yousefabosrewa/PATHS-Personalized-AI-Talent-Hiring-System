"use client";

/**
 * Assessments workspace (fix5.md refactor).
 *
 *  • Assessments are job-level templates — created with **job_id only**.
 *  • Candidate/application selectors removed.
 *  • Six assessment types: technical, HR, IQ, problem-solving (coding +
 *    thinking), quiz.
 *  • Generate → draft → HR review/edit → approve/publish.
 *  • No yellow disclaimer/AI-use warning box anywhere.
 *  • Reuses the OpenRouter abstraction via the backend agent — the
 *    frontend never calls OpenRouter directly.
 */

import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ClipboardCheck, Loader2, Plus, X, CheckCircle2, AlertTriangle, FileText,
  Briefcase, Sparkles, Upload, BadgeCheck, FilePlus2, Edit3, Trash2,
  ListChecks, BookOpen, Brain, Code2, ShieldCheck, AlertCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils/cn";
import {
  useJobs,
  useAssessments,
  useGenerateAssessmentDraft,
  useApproveAssessment,
  useUpdateAssessment,
  useDeleteAssessment,
  useUploadAssessmentSourceFile,
} from "@/lib/hooks";
import {
  ASSESSMENT_TYPE_OPTIONS,
  type AssessmentTypeValue,
  type AssessmentDifficulty,
  type BackendAssessmentOut,
  type BackendAssessmentQuestion,
} from "@/lib/api";

// ── Constants ───────────────────────────────────────────────────────────────

const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  approved: "Approved",
  published: "Published",
  archived: "Archived",
  // legacy
  pending: "Pending",
  in_progress: "In progress",
  submitted: "Submitted",
  reviewed: "Reviewed",
};

const STATUS_STYLES: Record<string, string> = {
  draft: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  approved: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  published: "border-emerald-500/40 bg-emerald-500/15 text-emerald-300",
  archived: "border-zinc-500/30 bg-zinc-500/10 text-zinc-300",
};

const TYPE_ICONS: Record<string, typeof FileText> = {
  technical_assessment: Code2,
  hr_assessment: Briefcase,
  iq_test: Brain,
  problem_solving_coding: Code2,
  problem_solving_thinking: BookOpen,
  quiz: ListChecks,
};

const DIFFICULTY_OPTIONS: AssessmentDifficulty[] = [
  "junior", "intermediate", "senior", "expert",
];

// ── Status / type helpers ───────────────────────────────────────────────────

function statusLabel(s: string) { return STATUS_LABELS[s] ?? s; }
function statusStyle(s: string) {
  return STATUS_STYLES[s] ?? "border-border/40 bg-muted/20 text-muted-foreground";
}
function typeLabel(t: string) {
  return (
    ASSESSMENT_TYPE_OPTIONS.find((o) => o.value === t)?.label ??
    t.replace(/_/g, " ")
  );
}
function TypeIcon({ type, className }: { type: string; className?: string }) {
  const I = TYPE_ICONS[type] ?? FileText;
  return <I className={cn("h-4 w-4", className)} />;
}

// ── Cards ───────────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  return (
    <Badge
      variant="outline"
      className={cn("text-[10px] uppercase tracking-wider gap-1", statusStyle(status))}
    >
      {statusLabel(status)}
    </Badge>
  );
}

function AssessmentCard({
  a,
  jobs,
  onEdit,
  onDelete,
  onApprove,
}: {
  a: BackendAssessmentOut;
  jobs: { id: string; title: string }[];
  onEdit: () => void;
  onDelete: () => void;
  onApprove: () => void;
}) {
  const usedFallback = Boolean(
    a.agent_metadata && (a.agent_metadata as Record<string, unknown>).used_fallback,
  );
  const job = jobs.find((j) => j.id === a.job_id);
  const qCount = a.questions?.length ?? 0;
  const isDraft = a.status === "draft";
  return (
    <article className="glass gradient-border rounded-2xl p-5 space-y-3">
      <header className="flex items-start gap-3 justify-between">
        <div className="flex items-start gap-3 min-w-0">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <TypeIcon type={a.assessment_type} />
          </div>
          <div className="min-w-0">
            <h3 className="font-heading text-sm font-bold text-foreground truncate">
              {a.title || typeLabel(a.assessment_type)}
            </h3>
            <p className="text-[11px] text-muted-foreground">
              {typeLabel(a.assessment_type)}
              {a.difficulty ? ` · ${a.difficulty}` : ""}
              {a.duration_minutes ? ` · ${a.duration_minutes} min` : ""}
              {a.total_score ? ` · ${a.total_score} pts` : ""}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {usedFallback && (
            <Badge
              variant="outline"
              className="border-amber-500/30 bg-amber-500/5 text-[10px] uppercase tracking-wider text-amber-300"
              title="The LLM agent was unavailable; this draft used the deterministic fallback. Regenerate when the agent is back."
            >
              <AlertTriangle className="mr-1 h-2.5 w-2.5" />
              Fallback
            </Badge>
          )}
          <StatusBadge status={a.status} />
        </div>
      </header>

      <p className="text-[12px] text-muted-foreground flex items-center gap-1.5">
        <Briefcase className="h-3 w-3" />
        Job: <span className="text-foreground">{job?.title ?? a.job_id.slice(0, 8)}</span>
      </p>

      {a.description && (
        <p className="text-[12px] text-muted-foreground line-clamp-2">{a.description}</p>
      )}

      <div className="flex items-center justify-between">
        <p className="text-[11px] text-muted-foreground">
          {qCount} question{qCount === 1 ? "" : "s"} ·{" "}
          {a.created_at
            ? `created ${new Date(a.created_at).toLocaleDateString()}`
            : ""}
          {a.approved_at
            ? ` · approved ${new Date(a.approved_at).toLocaleDateString()}`
            : ""}
        </p>
        <div className="flex items-center gap-1">
          <button
            onClick={onEdit}
            className="px-2 py-1 text-[11px] font-medium text-primary hover:bg-primary/10 rounded-md transition-colors inline-flex items-center gap-1"
          >
            <Edit3 className="h-3 w-3" />
            {isDraft ? "Review draft" : "View"}
          </button>
          {isDraft && (
            <button
              onClick={onApprove}
              className="px-2 py-1 text-[11px] font-medium text-emerald-400 hover:bg-emerald-500/10 rounded-md transition-colors inline-flex items-center gap-1"
              title="Publish — make this assessment available to all candidates of this job."
            >
              <CheckCircle2 className="h-3 w-3" /> Approve / Publish
            </button>
          )}
          <button
            onClick={onDelete}
            className="px-2 py-1 text-[11px] font-medium text-rose-400 hover:bg-rose-500/10 rounded-md transition-colors inline-flex items-center gap-1"
          >
            <Trash2 className="h-3 w-3" />
            Delete
          </button>
        </div>
      </div>
    </article>
  );
}

// ── Generate-draft modal ────────────────────────────────────────────────────

function GenerateDraftModal({
  open,
  onClose,
  onCreated,
  jobs,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (assessment: BackendAssessmentOut) => void;
  jobs: { id: string; title: string }[];
}) {
  const generate = useGenerateAssessmentDraft();
  const upload = useUploadAssessmentSourceFile();

  const [jobId, setJobId] = useState("");
  const [type, setType] = useState<AssessmentTypeValue>("technical_assessment");
  const [difficulty, setDifficulty] = useState<AssessmentDifficulty>("intermediate");
  const [questionCount, setQuestionCount] = useState<number>(5);
  const [duration, setDuration] = useState<number>(60);
  const [hrInstructions, setHrInstructions] = useState("");
  const [candidateInstructions, setCandidateInstructions] = useState("");
  const [sourceFileId, setSourceFileId] = useState<string | null>(null);
  const [sourceFileName, setSourceFileName] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // Reset when opened.
  useEffect(() => {
    if (open) {
      setErr(null);
    }
  }, [open]);

  const hrNeedsInput = type === "hr_assessment";

  const onFile = async (f: File | null) => {
    setErr(null);
    if (!f) {
      setSourceFileId(null);
      setSourceFileName(null);
      return;
    }
    try {
      const res = await upload.mutateAsync(f);
      setSourceFileId(res.source_file_id);
      setSourceFileName(res.source_file_name);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "File upload failed.");
    }
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (!jobId) {
      setErr("Pick the job this assessment is for.");
      return;
    }
    if (hrNeedsInput && !hrInstructions.trim() && !sourceFileId) {
      setErr(
        "HR Assessment requires topics, instructions, or an uploaded reference file.",
      );
      return;
    }
    try {
      const draft = await generate.mutateAsync({
        job_id: jobId,
        assessment_type: type,
        difficulty,
        question_count: questionCount,
        duration_minutes: duration,
        hr_instructions: hrInstructions.trim() || null,
        source_file_id: sourceFileId,
        candidate_instructions: candidateInstructions.trim() || null,
      });
      onCreated(draft);
      // Reset
      setJobId("");
      setHrInstructions("");
      setCandidateInstructions("");
      setSourceFileId(null);
      setSourceFileName(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Generation failed.");
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm overflow-y-auto p-4"
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 12 }}
            onClick={(e) => e.stopPropagation()}
            className="glass gradient-border rounded-2xl p-6 w-full max-w-2xl my-8 space-y-5"
          >
            <header className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <FilePlus2 className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="font-heading text-base font-bold text-foreground">
                    New Assessment
                  </h2>
                  <p className="text-[12px] text-muted-foreground">
                    Generates a job-level draft. HR reviews and approves before
                    candidates see it.
                  </p>
                </div>
              </div>
              <button
                onClick={onClose}
                className="text-muted-foreground hover:text-foreground"
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </header>

            <form onSubmit={onSubmit} className="space-y-4">
              {/* Job selector */}
              <div>
                <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  Job *
                </label>
                <select
                  value={jobId}
                  onChange={(e) => setJobId(e.target.value)}
                  required
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                >
                  <option value="">Select a job…</option>
                  {jobs.map((j) => (
                    <option key={j.id} value={j.id}>
                      {j.title}
                    </option>
                  ))}
                </select>
              </div>

              {/* Type selector — six radio cards */}
              <div>
                <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  Assessment type *
                </label>
                <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {ASSESSMENT_TYPE_OPTIONS.map((opt) => {
                    const Icon = TYPE_ICONS[opt.value] ?? FileText;
                    return (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => setType(opt.value)}
                        className={cn(
                          "flex items-center gap-2 rounded-lg border px-3 py-2 text-left text-[12px] transition-all",
                          type === opt.value
                            ? "border-primary/40 bg-primary/15 text-foreground"
                            : "border-border/40 bg-muted/10 text-muted-foreground hover:border-border",
                        )}
                      >
                        <Icon className="h-3.5 w-3.5 shrink-0 text-primary" />
                        <span className="truncate">{opt.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Difficulty + counts */}
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                    Difficulty
                  </label>
                  <select
                    value={difficulty}
                    onChange={(e) => setDifficulty(e.target.value as AssessmentDifficulty)}
                    className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  >
                    {DIFFICULTY_OPTIONS.map((d) => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                    Questions
                  </label>
                  <Input
                    type="number"
                    min={1}
                    max={25}
                    value={questionCount}
                    onChange={(e) => setQuestionCount(Math.max(1, Math.min(25, Number(e.target.value) || 1)))}
                    className="mt-1"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                    Duration (min)
                  </label>
                  <Input
                    type="number"
                    min={5}
                    max={240}
                    value={duration}
                    onChange={(e) => setDuration(Math.max(5, Math.min(240, Number(e.target.value) || 5)))}
                    className="mt-1"
                  />
                </div>
              </div>

              {/* HR instructions (always available; REQUIRED for HR type unless file uploaded) */}
              <div>
                <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  HR / agent instructions {hrNeedsInput && <span className="text-amber-400">(required for HR Assessment unless you upload a file)</span>}
                </label>
                <textarea
                  rows={3}
                  value={hrInstructions}
                  onChange={(e) => setHrInstructions(e.target.value)}
                  placeholder={
                    hrNeedsInput
                      ? "List the HR topics or competencies the agent should cover (e.g. prioritization, ownership, communication, company-specific values)."
                      : "Optional. Steer the agent — e.g. 'focus on FastAPI design and vector search debugging'."
                  }
                  className="mt-1 w-full rounded-lg border border-border/40 bg-background px-3 py-2 text-[13px] focus:outline-none focus:ring-1 focus:ring-primary/40 resize-none"
                />
              </div>

              {/* Candidate-facing instructions */}
              <div>
                <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  Candidate-facing instructions (optional)
                </label>
                <textarea
                  rows={2}
                  value={candidateInstructions}
                  onChange={(e) => setCandidateInstructions(e.target.value)}
                  placeholder="What candidates will see when they open the assessment."
                  className="mt-1 w-full rounded-lg border border-border/40 bg-background px-3 py-2 text-[13px] focus:outline-none focus:ring-1 focus:ring-primary/40 resize-none"
                />
              </div>

              {/* File upload */}
              <div>
                <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  Reference file (optional)
                </label>
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <label className="inline-flex items-center gap-2 rounded-md border border-border/50 px-3 py-1.5 text-[12px] cursor-pointer hover:bg-muted/20">
                    <Upload className="h-3.5 w-3.5" />
                    Upload .txt / .md / .csv / .json / .pdf
                    <input
                      type="file"
                      className="hidden"
                      accept=".txt,.md,.csv,.tsv,.json,.yaml,.yml,.html,.htm,.pdf"
                      onChange={(e) => onFile(e.target.files?.[0] ?? null)}
                    />
                  </label>
                  {sourceFileName && (
                    <Badge
                      variant="outline"
                      className="border-emerald-500/30 bg-emerald-500/5 text-[11px] text-emerald-300"
                    >
                      <BadgeCheck className="mr-1 h-3 w-3" />
                      {sourceFileName}
                    </Badge>
                  )}
                  {upload.isPending && (
                    <span className="flex items-center gap-1 text-[11px] text-muted-foreground">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      Parsing…
                    </span>
                  )}
                </div>
                <p className="mt-1 text-[10px] text-muted-foreground/60">
                  The file is parsed in the backend and used as agent context. Max 5 MB.
                </p>
              </div>

              {err && (
                <div className="flex items-start gap-2 rounded-md border border-rose-500/30 bg-rose-500/5 p-2.5 text-[12px] text-rose-300">
                  <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                  {err}
                </div>
              )}

              <footer className="flex items-center justify-between gap-2 pt-1">
                <p className="text-[11px] text-muted-foreground inline-flex items-center gap-1">
                  <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
                  Drafts stay private to HR. Candidates only see published assessments.
                </p>
                <div className="flex gap-2">
                  <Button type="button" variant="ghost" size="sm" onClick={onClose}>
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    size="sm"
                    className="gap-1 glow-blue"
                    disabled={generate.isPending}
                  >
                    {generate.isPending ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Sparkles className="h-3.5 w-3.5" />
                    )}
                    Generate draft
                  </Button>
                </div>
              </footer>
            </form>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// ── Draft preview / edit / approve modal ────────────────────────────────────

function DraftPreviewModal({
  assessment,
  jobs,
  open,
  onClose,
}: {
  assessment: BackendAssessmentOut;
  jobs: { id: string; title: string }[];
  open: boolean;
  onClose: () => void;
}) {
  const update = useUpdateAssessment();
  const approve = useApproveAssessment();

  // Local editable state — initialised from the assessment.
  const [title, setTitle] = useState(assessment.title);
  const [description, setDescription] = useState(assessment.description ?? "");
  const [duration, setDuration] = useState<number>(assessment.duration_minutes ?? 60);
  const [totalScore, setTotalScore] = useState<number>(assessment.total_score ?? 100);
  const [instructions, setInstructions] = useState(assessment.instructions ?? "");
  const [questions, setQuestions] = useState<BackendAssessmentQuestion[]>(
    () => (assessment.questions ? [...assessment.questions] : []),
  );
  const [savingMsg, setSavingMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setTitle(assessment.title);
      setDescription(assessment.description ?? "");
      setDuration(assessment.duration_minutes ?? 60);
      setTotalScore(assessment.total_score ?? 100);
      setInstructions(assessment.instructions ?? "");
      setQuestions(assessment.questions ? [...assessment.questions] : []);
      setErr(null);
      setSavingMsg(null);
    }
  }, [open, assessment]);

  const job = jobs.find((j) => j.id === assessment.job_id);
  const isDraft = assessment.status === "draft";
  const usedFallback = Boolean(
    assessment.agent_metadata &&
      (assessment.agent_metadata as Record<string, unknown>).used_fallback,
  );

  const setQuestionField = (idx: number, key: keyof BackendAssessmentQuestion, value: unknown) => {
    setQuestions((prev) => {
      const next = [...prev];
      const cur = { ...(next[idx] ?? {}) } as BackendAssessmentQuestion;
      (cur as Record<string, unknown>)[key as string] = value;
      next[idx] = cur;
      return next;
    });
  };

  const removeQuestion = (idx: number) =>
    setQuestions((prev) => prev.filter((_, i) => i !== idx));

  const onSave = async () => {
    setErr(null);
    setSavingMsg(null);
    try {
      await update.mutateAsync({
        id: assessment.id,
        title,
        description: description || null,
        duration_minutes: duration,
        total_score: totalScore,
        instructions: instructions || null,
        questions,
      });
      setSavingMsg("Saved.");
      setTimeout(() => setSavingMsg(null), 1500);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Save failed.");
    }
  };

  const onApprove = async () => {
    setErr(null);
    try {
      // Save first to make sure HR edits are persisted before approval.
      await update.mutateAsync({
        id: assessment.id,
        title,
        description: description || null,
        duration_minutes: duration,
        total_score: totalScore,
        instructions: instructions || null,
        questions,
      });
      await approve.mutateAsync({ id: assessment.id, publish: true });
      onClose();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Approval failed.");
    }
  };

  if (!open) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-start justify-center bg-black/55 backdrop-blur-sm overflow-y-auto p-4"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.97, y: 12 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.97, y: 12 }}
          onClick={(e) => e.stopPropagation()}
          className="glass gradient-border rounded-2xl p-6 w-full max-w-4xl my-6 space-y-5"
        >
          {/* Header */}
          <header className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3 min-w-0">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <TypeIcon type={assessment.assessment_type} />
              </div>
              <div className="min-w-0 space-y-1">
                <h2 className="font-heading text-base font-bold text-foreground">
                  {isDraft ? "Review draft" : "Assessment"}
                </h2>
                <p className="text-[11px] text-muted-foreground">
                  {typeLabel(assessment.assessment_type)}
                  {assessment.difficulty ? ` · ${assessment.difficulty}` : ""}
                  {job ? ` · Job: ${job.title}` : ""}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {usedFallback && (
                <Badge
                  variant="outline"
                  className="border-amber-500/30 bg-amber-500/5 text-[10px] uppercase tracking-wider text-amber-300"
                >
                  <AlertTriangle className="mr-1 h-2.5 w-2.5" />
                  Fallback
                </Badge>
              )}
              <StatusBadge status={assessment.status} />
              <button
                onClick={onClose}
                className="text-muted-foreground hover:text-foreground"
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </header>

          {/* Metadata editor */}
          <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="sm:col-span-2">
              <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Title</label>
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                disabled={!isDraft}
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Total score</label>
              <Input
                type="number"
                value={totalScore}
                onChange={(e) => setTotalScore(Number(e.target.value) || 0)}
                disabled={!isDraft}
                className="mt-1"
              />
            </div>
            <div className="sm:col-span-2">
              <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Description</label>
              <textarea
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={!isDraft}
                className="mt-1 w-full rounded-lg border border-border/40 bg-background px-3 py-2 text-[13px] focus:outline-none focus:ring-1 focus:ring-primary/40 resize-none disabled:opacity-70"
              />
            </div>
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Duration (min)</label>
              <Input
                type="number"
                min={5}
                max={240}
                value={duration}
                onChange={(e) => setDuration(Math.max(5, Math.min(240, Number(e.target.value) || 5)))}
                disabled={!isDraft}
                className="mt-1"
              />
            </div>
            <div className="sm:col-span-3">
              <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Candidate-facing instructions</label>
              <textarea
                rows={2}
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
                disabled={!isDraft}
                className="mt-1 w-full rounded-lg border border-border/40 bg-background px-3 py-2 text-[13px] focus:outline-none focus:ring-1 focus:ring-primary/40 resize-none disabled:opacity-70"
              />
            </div>
          </section>

          {/* Questions */}
          <section className="space-y-3">
            <header className="flex items-center justify-between">
              <h3 className="font-heading text-sm font-bold text-foreground inline-flex items-center gap-1.5">
                <ListChecks className="h-4 w-4 text-primary" />
                Generated questions
              </h3>
              <span className="text-[11px] text-muted-foreground">
                {questions.length} question{questions.length === 1 ? "" : "s"}
              </span>
            </header>

            {questions.length === 0 && (
              <p className="rounded-md border border-dashed border-border/40 p-4 text-[12px] text-muted-foreground">
                No questions in this draft.
              </p>
            )}

            {questions.map((q, i) => (
              <QuestionEditor
                key={q.id ?? `Q${i + 1}`}
                index={i}
                question={q}
                editable={isDraft}
                onChange={(key, value) => setQuestionField(i, key, value)}
                onRemove={() => removeQuestion(i)}
              />
            ))}
          </section>

          {err && (
            <div className="flex items-start gap-2 rounded-md border border-rose-500/30 bg-rose-500/5 p-2.5 text-[12px] text-rose-300">
              <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
              {err}
            </div>
          )}

          <footer className="flex flex-wrap items-center justify-end gap-2 pt-2">
            {savingMsg && <span className="text-[11px] text-emerald-400 mr-auto">{savingMsg}</span>}
            <Button type="button" variant="ghost" size="sm" onClick={onClose}>
              Close
            </Button>
            {isDraft && (
              <>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={onSave}
                  disabled={update.isPending || approve.isPending}
                >
                  {update.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                  Save changes
                </Button>
                <Button
                  type="button"
                  size="sm"
                  className="gap-1 glow-blue"
                  onClick={onApprove}
                  disabled={update.isPending || approve.isPending || questions.length === 0}
                >
                  {approve.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  )}
                  Approve & publish
                </Button>
              </>
            )}
          </footer>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

// ── Per-question editor ─────────────────────────────────────────────────────

function QuestionEditor({
  index,
  question,
  editable,
  onChange,
  onRemove,
}: {
  index: number;
  question: BackendAssessmentQuestion;
  editable: boolean;
  onChange: (key: keyof BackendAssessmentQuestion, value: unknown) => void;
  onRemove: () => void;
}) {
  const opts = Array.isArray(question.options) ? (question.options as string[]) : [];
  const rubric = Array.isArray(question.rubric) ? question.rubric : [];
  const measures = Array.isArray(question.measures) ? question.measures : [];
  const mapped = Array.isArray(question.mapped_job_requirements)
    ? question.mapped_job_requirements
    : [];
  const strongs = Array.isArray(question.strong_answer_indicators) ? question.strong_answer_indicators : [];
  const weaks = Array.isArray(question.weak_answer_indicators) ? question.weak_answer_indicators : [];

  return (
    <div className="rounded-xl border border-border/40 bg-muted/10 p-4 space-y-3">
      <header className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <Badge variant="outline" className="text-[10px] text-muted-foreground">
            Q{index + 1}
          </Badge>
          {question.difficulty && (
            <Badge variant="outline" className="text-[10px] text-muted-foreground">
              {String(question.difficulty)}
            </Badge>
          )}
          {typeof question.score === "number" && (
            <Badge
              variant="outline"
              className="text-[10px] border-emerald-500/30 bg-emerald-500/5 text-emerald-300"
            >
              {question.score} pts
            </Badge>
          )}
          {question.type && (
            <Badge variant="outline" className="text-[10px] text-muted-foreground/80">
              {String(question.type)}
            </Badge>
          )}
        </div>
        {editable && (
          <button
            onClick={onRemove}
            className="text-rose-400 hover:bg-rose-500/10 rounded-md p-1"
            title="Remove this question"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        )}
      </header>

      {/* Question text + scenario */}
      {typeof question.scenario === "string" && question.scenario.length > 0 && (
        <FieldText
          label="Scenario"
          value={question.scenario}
          editable={editable}
          onChange={(v) => onChange("scenario", v)}
        />
      )}
      <FieldText
        label="Question"
        value={String(question.question ?? "")}
        editable={editable}
        onChange={(v) => onChange("question", v)}
        multiline
      />

      {/* Options (MCQ / quiz / IQ) */}
      {(opts.length > 0 || question.correct_answer != null) && (
        <div className="space-y-1.5">
          <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Options
          </label>
          <ul className="space-y-1">
            {opts.map((o, oi) => (
              <li
                key={oi}
                className={cn(
                  "flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-[12px]",
                  String(question.correct_answer) === o
                    ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-300"
                    : "border-border/40 bg-background/50 text-foreground/80",
                )}
              >
                <span
                  className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    String(question.correct_answer) === o ? "bg-emerald-400" : "bg-muted-foreground/40",
                  )}
                />
                {o}
                {String(question.correct_answer) === o && (
                  <CheckCircle2 className="ml-auto h-3 w-3 text-emerald-400" />
                )}
              </li>
            ))}
          </ul>
          {question.correct_answer && opts.length === 0 && (
            <p className="text-[11px] text-emerald-300">Correct: {String(question.correct_answer)}</p>
          )}
        </div>
      )}

      {/* Expected answer */}
      {typeof question.expected_answer === "string" && question.expected_answer.length > 0 && (
        <FieldText
          label="Expected answer"
          value={question.expected_answer}
          editable={editable}
          onChange={(v) => onChange("expected_answer", v)}
          multiline
        />
      )}

      {/* Explanation */}
      {typeof question.explanation === "string" && question.explanation.length > 0 && (
        <FieldText
          label="Explanation"
          value={question.explanation}
          editable={editable}
          onChange={(v) => onChange("explanation", v)}
          multiline
        />
      )}

      {/* Rubric */}
      {rubric.length > 0 && (
        <div>
          <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Rubric
          </label>
          <ul className="mt-1 space-y-1">
            {rubric.map((r, ri) => (
              <li
                key={ri}
                className="flex items-center justify-between rounded-md border border-border/40 bg-background/50 px-2.5 py-1.5 text-[12px]"
              >
                <span className="truncate">{r.criterion}</span>
                <span className="font-mono text-[11px] text-muted-foreground">
                  {r.points} pts
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* HR strong / weak indicators */}
      {strongs.length > 0 && (
        <div>
          <label className="text-[11px] font-semibold uppercase tracking-wide text-emerald-400/80">
            Strong-answer indicators
          </label>
          <ul className="mt-1 space-y-0.5">
            {strongs.map((s, i) => (
              <li key={i} className="text-[12px] text-emerald-200/80">• {String(s)}</li>
            ))}
          </ul>
        </div>
      )}
      {weaks.length > 0 && (
        <div>
          <label className="text-[11px] font-semibold uppercase tracking-wide text-rose-400/80">
            Weak-answer indicators
          </label>
          <ul className="mt-1 space-y-0.5">
            {weaks.map((s, i) => (
              <li key={i} className="text-[12px] text-rose-200/80">• {String(s)}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Agent reason + measures + mapped requirements */}
      {(question.agent_reason || measures.length > 0 || mapped.length > 0) && (
        <div className="rounded-md border border-primary/15 bg-primary/5 p-3 space-y-1.5">
          {question.agent_reason && (
            <p className="text-[12px] text-foreground/80">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-primary/80 mr-1.5">
                Why this question
              </span>
              {String(question.agent_reason)}
            </p>
          )}
          {measures.length > 0 && (
            <p className="text-[11px] text-muted-foreground">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-primary/80 mr-1.5">
                Measures
              </span>
              {measures.join(" · ")}
            </p>
          )}
          {mapped.length > 0 && (
            <p className="text-[11px] text-muted-foreground">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-primary/80 mr-1.5">
                Mapped requirements
              </span>
              {mapped.join(" · ")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function FieldText({
  label,
  value,
  editable,
  onChange,
  multiline,
}: {
  label: string;
  value: string;
  editable: boolean;
  onChange: (v: string) => void;
  multiline?: boolean;
}) {
  return (
    <div>
      <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </label>
      {multiline ? (
        <textarea
          rows={3}
          value={value}
          disabled={!editable}
          onChange={(e) => onChange(e.target.value)}
          className="mt-1 w-full rounded-lg border border-border/40 bg-background px-3 py-2 text-[13px] focus:outline-none focus:ring-1 focus:ring-primary/40 resize-none disabled:opacity-80"
        />
      ) : (
        <Input
          value={value}
          disabled={!editable}
          onChange={(e) => onChange(e.target.value)}
          className="mt-1"
        />
      )}
    </div>
  );
}

// ── Page ────────────────────────────────────────────────────────────────────

export default function OrgAssessmentsPage() {
  const { data: jobs = [] } = useJobs({ limit: 200 });
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [jobFilter, setJobFilter] = useState<string>("");

  const filterParams = useMemo(
    () => ({
      status: statusFilter || undefined,
      assessment_type: typeFilter || undefined,
      job_id: jobFilter || undefined,
      limit: 100,
    }),
    [statusFilter, typeFilter, jobFilter],
  );
  const { data: assessments = [], isLoading } = useAssessments(filterParams);
  const deleteAssessment = useDeleteAssessment();
  const approve = useApproveAssessment();

  const [showGenerate, setShowGenerate] = useState(false);
  const [preview, setPreview] = useState<BackendAssessmentOut | null>(null);
  const [deleting, setDeleting] = useState<BackendAssessmentOut | null>(null);

  const draftCount = assessments.filter((a) => a.status === "draft").length;
  const publishedCount = assessments.filter(
    (a) => a.status === "published" || a.status === "approved",
  ).length;

  const jobOptions = jobs.map((j) => ({ id: String(j.id), title: j.title }));

  const handleDelete = async () => {
    if (!deleting) return;
    await deleteAssessment.mutateAsync(deleting.id);
    setDeleting(null);
  };

  const onCreated = (draft: BackendAssessmentOut) => {
    setShowGenerate(false);
    setPreview(draft);
  };

  const onCardApprove = async (a: BackendAssessmentOut) => {
    try {
      await approve.mutateAsync({ id: a.id, publish: true });
    } catch {
      // Errors surface via the modal flow if HR opens the draft to fix it.
    }
  };

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6 max-w-5xl">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-start justify-between gap-4"
      >
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
            <ClipboardCheck className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h1 className="font-heading text-xl font-bold tracking-tight text-foreground">
              Assessments
            </h1>
            <p className="text-sm text-muted-foreground">
              Job-level assessment templates. Generate a draft, edit it, then
              approve to make it available to every candidate of that job.
            </p>
          </div>
        </div>
        <Button size="sm" onClick={() => setShowGenerate(true)} className="text-xs shrink-0">
          <Plus className="h-3.5 w-3.5 mr-1" />
          New assessment
        </Button>
      </motion.div>

      {/* Stat tiles */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="glass rounded-xl p-4">
          <p className="text-2xl font-bold text-amber-300">{draftCount}</p>
          <p className="text-[12px] text-muted-foreground">Drafts awaiting review</p>
        </div>
        <div className="glass rounded-xl p-4">
          <p className="text-2xl font-bold text-emerald-300">{publishedCount}</p>
          <p className="text-[12px] text-muted-foreground">Published (visible to candidates)</p>
        </div>
        <div className="glass rounded-xl p-4">
          <p className="text-2xl font-bold text-foreground">{assessments.length}</p>
          <p className="text-[12px] text-muted-foreground">Total assessments</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex flex-wrap items-center gap-1">
          {["", "draft", "published", "approved", "archived"].map((s) => (
            <button
              key={s || "all"}
              onClick={() => setStatusFilter(s)}
              className={cn(
                "rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors",
                statusFilter === s
                  ? "bg-primary/15 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/30",
              )}
            >
              {s ? statusLabel(s) : "all"}
            </button>
          ))}
        </div>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="rounded-md border border-border bg-background px-2.5 py-1 text-[12px]"
          aria-label="Type filter"
        >
          <option value="">All types</option>
          {ASSESSMENT_TYPE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <select
          value={jobFilter}
          onChange={(e) => setJobFilter(e.target.value)}
          className="rounded-md border border-border bg-background px-2.5 py-1 text-[12px] min-w-[14rem]"
          aria-label="Job filter"
        >
          <option value="">All jobs</option>
          {jobOptions.map((j) => (
            <option key={j.id} value={j.id}>{j.title}</option>
          ))}
        </select>
      </div>

      {/* List */}
      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading assessments…
        </div>
      )}

      {!isLoading && assessments.length === 0 && (
        <div className="glass rounded-xl p-10 text-center space-y-2">
          <ClipboardCheck className="h-8 w-8 text-muted-foreground/40 mx-auto" />
          <p className="text-sm text-muted-foreground">No assessments yet.</p>
          <p className="text-xs text-muted-foreground/60">
            Click <span className="font-semibold">New assessment</span> to generate the first draft.
          </p>
        </div>
      )}

      {!isLoading && assessments.length > 0 && (
        <div className="space-y-3">
          {assessments.map((a) => (
            <AssessmentCard
              key={a.id}
              a={a}
              jobs={jobOptions}
              onEdit={() => setPreview(a)}
              onApprove={() => onCardApprove(a)}
              onDelete={() => setDeleting(a)}
            />
          ))}
        </div>
      )}

      {/* Modals */}
      <GenerateDraftModal
        open={showGenerate}
        onClose={() => setShowGenerate(false)}
        onCreated={onCreated}
        jobs={jobOptions}
      />
      {preview && (
        <DraftPreviewModal
          assessment={preview}
          jobs={jobOptions}
          open={!!preview}
          onClose={() => setPreview(null)}
        />
      )}
      <AnimatePresence>
        {deleting && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
            onClick={() => setDeleting(null)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.96, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 12 }}
              onClick={(e) => e.stopPropagation()}
              className="glass gradient-border rounded-2xl p-6 w-full max-w-sm space-y-4"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-rose-500/10">
                  <AlertCircle className="h-5 w-5 text-rose-400" />
                </div>
                <div>
                  <h2 className="text-sm font-semibold text-foreground">Delete assessment</h2>
                  <p className="text-xs text-muted-foreground">This action cannot be undone.</p>
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                Delete <span className="font-semibold">{deleting.title}</span>?
              </p>
              <div className="flex justify-end gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setDeleting(null)}
                >
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  disabled={deleteAssessment.isPending}
                  onClick={handleDelete}
                >
                  {deleteAssessment.isPending ? (
                    <Loader2 className="h-3 w-3 animate-spin mr-1" />
                  ) : null}
                  Delete
                </Button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

"use client";

/**
 * PreparationPanel (fix3.md §5).
 *
 * Replaces the old "AI Interview" tile.  Four cards, each calls the
 * backend Preparation Agent with the candidate (anonymized) + job
 * context and renders the structured JSON it returns.
 *
 * Identity is never sent to the agent — the backend strips it before the
 * prompt is built (see services/preparation/service.py).
 */

import { useState, useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Brain, Code2, Users, Loader2, Sparkles, Copy as CopyIcon,
  AlertCircle, RefreshCw,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";
import {
  preparationApi,
  type PreparationOutputType,
  type PreparationGenerateResponse,
  type PreparationSavedDraft,
} from "@/lib/api";

// Assessment is intentionally excluded here — it has a dedicated tab.
type PrepSectionType = Exclude<PreparationOutputType, "assessment">;

const SECTION_META: Record<PrepSectionType, {
  title: string;
  description: string;
  icon: typeof Brain;
  tone: string;
}> = {
  pre_analysis: {
    title: "Candidate pre-analysis",
    description: "Strengths, possible gaps, risk flags, and an interview strategy — derived from the candidate's anonymized evidence.",
    icon: Brain,
    tone: "text-violet-300",
  },
  technical_questions: {
    title: "Technical question drafts",
    description: "Role-specific technical questions with rubric and answer signals.",
    icon: Code2,
    tone: "text-sky-300",
  },
  hr_questions: {
    title: "HR / behavioural question drafts",
    description: "Scenario-based behavioural questions across motivation, teamwork, communication, ownership, problem solving, and culture fit.",
    icon: Users,
    tone: "text-emerald-300",
  },
};


function copyJson(payload: unknown) {
  try {
    navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
    toast.success("Copied to clipboard");
  } catch {
    toast.error("Clipboard unavailable");
  }
}


// ── Per-section renderers ───────────────────────────────────────────────────

function PreAnalysisView({ data }: { data: Record<string, unknown> }) {
  const summary = String(data.summary ?? "");
  const list = (k: string) => (Array.isArray(data[k]) ? (data[k] as string[]) : []);
  const blocks: { label: string; items: string[]; tone: string }[] = [
    { label: "Strengths",                 items: list("strengths"),                tone: "border-emerald-500/20 text-emerald-300" },
    { label: "Possible gaps",             items: list("possible_gaps"),            tone: "border-amber-500/20 text-amber-300" },
    { label: "Risk flags",                items: list("risk_flags"),               tone: "border-rose-500/20 text-rose-300" },
    { label: "Recommended focus areas",   items: list("recommended_focus_areas"),  tone: "border-sky-500/20 text-sky-300" },
    { label: "Interview strategy",        items: list("interview_strategy"),       tone: "border-violet-500/20 text-violet-300" },
  ];
  return (
    <div className="space-y-3 text-[13px]">
      {summary && (
        <p className="text-foreground leading-relaxed">{summary}</p>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {blocks.filter((b) => b.items.length > 0).map((b) => (
          <div key={b.label} className={cn("rounded-lg border p-3", b.tone)}>
            <p className="text-[10px] font-semibold uppercase tracking-widest mb-1.5">
              {b.label}
            </p>
            <ul className="space-y-1 text-foreground/90 text-[12px] list-disc list-inside">
              {b.items.slice(0, 6).map((x, i) => (<li key={i}>{x}</li>))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}


function QuestionListView({
  data, behavioural,
}: { data: Record<string, unknown>; behavioural: boolean }) {
  const qs = Array.isArray(data.questions) ? (data.questions as Record<string, unknown>[]) : [];
  if (qs.length === 0) {
    return (
      <p className="text-[12px] text-muted-foreground italic">
        The agent returned no questions for this run.  Try regenerating —
        sometimes the free model rate-limits us.
      </p>
    );
  }
  return (
    <ol className="space-y-3 list-decimal list-inside text-[13px]">
      {qs.map((q, i) => {
        const question = String(q.question ?? "");
        const why = String(q.why_ask ?? "");
        const strong = Array.isArray(q.strong_answer_signals)
          ? (q.strong_answer_signals as string[]) : [];
        const weakLabel = behavioural ? "Red flags" : "Weak signals";
        const weak = behavioural
          ? (Array.isArray(q.red_flags) ? (q.red_flags as string[]) : [])
          : (Array.isArray(q.weak_answer_signals) ? (q.weak_answer_signals as string[]) : []);
        const rubric = Array.isArray(q.rubric) ? (q.rubric as string[]) : [];
        const competency = behavioural ? String(q.competency ?? "") : "";
        return (
          <li key={i} className="rounded-lg border border-border/40 bg-muted/10 p-3 space-y-1.5">
            <p className="font-semibold text-foreground leading-snug">{question}</p>
            {competency && (
              <span className="inline-block rounded-full bg-primary/10 border border-primary/20 px-2 py-0.5 text-[10px] font-semibold text-primary capitalize">
                {competency.replace(/_/g, " ")}
              </span>
            )}
            {why && <p className="text-[12px] text-muted-foreground"><span className="font-medium text-foreground">Why ask:</span> {why}</p>}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
              {strong.length > 0 && (
                <div className="rounded-md bg-emerald-500/5 border border-emerald-500/15 p-2">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-emerald-300 mb-1">Strong signals</p>
                  <ul className="text-[11px] text-foreground/90 list-disc list-inside space-y-0.5">
                    {strong.slice(0, 4).map((s, j) => (<li key={j}>{s}</li>))}
                  </ul>
                </div>
              )}
              {weak.length > 0 && (
                <div className="rounded-md bg-rose-500/5 border border-rose-500/15 p-2">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-rose-300 mb-1">{weakLabel}</p>
                  <ul className="text-[11px] text-foreground/90 list-disc list-inside space-y-0.5">
                    {weak.slice(0, 4).map((s, j) => (<li key={j}>{s}</li>))}
                  </ul>
                </div>
              )}
              {!behavioural && rubric.length > 0 && (
                <div className="rounded-md bg-sky-500/5 border border-sky-500/15 p-2 sm:col-span-2">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-sky-300 mb-1">Rubric</p>
                  <ul className="text-[11px] text-foreground/90 list-disc list-inside space-y-0.5">
                    {rubric.slice(0, 6).map((s, j) => (<li key={j}>{s}</li>))}
                  </ul>
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}


function PreparationSection({
  type, candidateId, jobId, saved,
}: {
  type: PrepSectionType;
  candidateId: string;
  jobId?: string;
  saved?: PreparationSavedDraft;
}) {
  const meta = SECTION_META[type];
  const Icon = meta.icon;
  const [result, setResult] = useState<PreparationGenerateResponse | null>(null);
  const mutation = useMutation({
    mutationFn: () => preparationApi.generate(candidateId, type, jobId),
    onSuccess: (data) => setResult(data),
    onError: (e) => toast.error(e instanceof Error ? e.message : "Generation failed"),
  });

  // Seed from the persisted draft when it loads — but never clobber a fresh
  // (re)generation the user just made this session.
  useEffect(() => {
    if (saved && result == null) {
      setResult({
        candidate_id: candidateId,
        job_id: jobId ?? null,
        output_type: type,
        content: saved.content,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [saved]);

  const hasResult = result != null;
  const savedAt = saved?.updated_at ?? null;
  const errorNote = (result?.content as Record<string, unknown> | undefined)?.agent_error as
    string | undefined;

  return (
    <div className="glass rounded-xl p-5 space-y-3">
      <div className="flex items-start gap-3">
        <div className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10", meta.tone)}>
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="font-heading text-[14px] font-semibold text-foreground">{meta.title}</h3>
          <p className="mt-1 text-[12px] text-muted-foreground">{meta.description}</p>
          {savedAt && (
            <p className="mt-0.5 text-[10px] text-emerald-400/80">
              Saved · {new Date(savedAt).toLocaleString()} — kept until you regenerate.
            </p>
          )}
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {hasResult && (
            <Button
              size="sm"
              variant="ghost"
              className="h-7 gap-1 text-[11px]"
              onClick={() => copyJson(result?.content)}
            >
              <CopyIcon className="h-3 w-3" /> Copy
            </Button>
          )}
          <Button
            size="sm"
            variant={hasResult ? "outline" : "default"}
            className="h-7 gap-1.5 text-[11px]"
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
          >
            {mutation.isPending
              ? <Loader2 className="h-3 w-3 animate-spin" />
              : hasResult
                ? <RefreshCw className="h-3 w-3" />
                : <Sparkles className="h-3 w-3" />}
            {hasResult ? "Regenerate" : "Generate"}
          </Button>
        </div>
      </div>

      {errorNote && (
        <div className="flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-[11px] text-amber-300">
          <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
          <span>Agent fell back: {errorNote}</span>
        </div>
      )}

      {hasResult && type === "pre_analysis" && (
        <PreAnalysisView data={result!.content} />
      )}
      {hasResult && type === "technical_questions" && (
        <QuestionListView data={result!.content} behavioural={false} />
      )}
      {hasResult && type === "hr_questions" && (
        <QuestionListView data={result!.content} behavioural />
      )}

      {!hasResult && !mutation.isPending && (
        <p className="text-[12px] text-muted-foreground italic">
          Click <strong>Generate</strong> to run the Preparation Agent — it
          will receive only the candidate&apos;s alias plus structured evidence,
          never the real name.
        </p>
      )}
    </div>
  );
}


export function PreparationPanel({
  candidateId,
  jobId,
}: {
  candidateId: string;
  jobId?: string;
}) {
  // Load any persisted drafts so they show on open (saved until regenerated).
  const { data: saved } = useQuery({
    queryKey: ["prep-drafts", candidateId, jobId ?? null],
    queryFn: () => preparationApi.list(candidateId, jobId),
    enabled: Boolean(candidateId),
    staleTime: 30_000,
  });
  const drafts = saved?.drafts ?? {};

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-primary/15 bg-primary/5 px-3 py-2">
        <p className="text-[12px] text-foreground/90 leading-relaxed">
          <strong>Preparation</strong> generates AI-assisted artifacts for the
          upcoming interview.  Drafts are saved and reused until you regenerate
          them. Every prompt uses the candidate&apos;s anonymized alias only —
          identity is never sent to the model.
        </p>
      </div>
      {/* Assessment draft intentionally removed — assessments have their own
          dedicated tab. Preparation keeps pre-analysis + interview questions. */}
      <PreparationSection type="pre_analysis" candidateId={candidateId} jobId={jobId} saved={drafts.pre_analysis} />
      <PreparationSection type="technical_questions" candidateId={candidateId} jobId={jobId} saved={drafts.technical_questions} />
      <PreparationSection type="hr_questions" candidateId={candidateId} jobId={jobId} saved={drafts.hr_questions} />
    </div>
  );
}

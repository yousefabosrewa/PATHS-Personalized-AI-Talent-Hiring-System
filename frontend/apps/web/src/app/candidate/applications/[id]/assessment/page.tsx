"use client";

import { use, useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowLeft, Loader2, ClipboardList, Award, CheckCircle2, AlertTriangle,
  Clock, Send, ThumbsUp, Target,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  useApplicationAssessment,
  useSubmitApplicationAssessment,
} from "@/lib/hooks";
import type { BackendAssessmentReport } from "@/lib/api";
import { cn } from "@/lib/utils/cn";

function scoreColor(pct: number): string {
  return pct >= 70
    ? "text-emerald-400"
    : pct >= 45
      ? "text-amber-400"
      : "text-rose-400";
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center px-6">
      <div className="text-center">{children}</div>
    </div>
  );
}

export default function AssessmentPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data, isLoading, isError } = useApplicationAssessment(id);
  const submit = useSubmitApplicationAssessment(id);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [localReport, setLocalReport] = useState<BackendAssessmentReport | null>(null);

  const questions = data?.assessment?.questions ?? [];
  const answeredCount = useMemo(
    () => questions.filter((q) => (answers[q.id] ?? "").trim().length > 0).length,
    [questions, answers],
  );

  const report = localReport ?? data?.report ?? null;
  const submitted = data?.status === "submitted" || report != null;

  if (isLoading) {
    return (
      <Centered>
        <Loader2 className="mx-auto h-6 w-6 animate-spin text-primary" />
        <p className="mt-2 text-sm text-muted-foreground">Loading assessment…</p>
      </Centered>
    );
  }
  if (isError || !data) {
    return (
      <Centered>
        <p className="text-sm text-rose-400">Could not load this assessment.</p>
        <Button asChild variant="ghost" size="sm" className="mt-3">
          <Link href="/candidate/applications">Back to applications</Link>
        </Button>
      </Centered>
    );
  }

  // Locked until the candidate reaches the assessment stage (backend-enforced).
  if (data.status === "locked") {
    return (
      <Centered>
        <AlertTriangle className="mx-auto h-6 w-6 text-amber-400" />
        <p className="mt-2 text-sm font-semibold text-foreground">Assessment locked</p>
        <p className="mt-1 text-[13px] text-muted-foreground">
          {data.locked_reason ??
            "This assessment unlocks once you reach the assessment stage."}
        </p>
        <Button asChild variant="ghost" size="sm" className="mt-3">
          <Link href="/candidate/applications">Back to applications</Link>
        </Button>
      </Centered>
    );
  }

  const onSubmit = () => {
    submit.mutate(answers, {
      onSuccess: (rep) => setLocalReport(rep),
    });
  };

  return (
    <div className="min-h-screen px-6 py-8">
      <div className="mx-auto max-w-3xl space-y-6">
        <div>
          <Button asChild variant="ghost" size="sm" className="-ml-2 gap-1.5 text-muted-foreground">
            <Link href="/candidate/applications">
              <ArrowLeft className="h-3.5 w-3.5" /> My applications
            </Link>
          </Button>
        </div>

        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass gradient-border rounded-2xl p-6"
        >
          <div className="flex items-center gap-2">
            <ClipboardList className="h-4 w-4 text-primary" />
            <p className="text-[11px] font-semibold uppercase tracking-widest text-primary/80">
              Assessment · {data.job_title ?? "Role"}
            </p>
          </div>
          <h1 className="mt-1 font-heading text-2xl font-bold text-foreground">
            {data.assessment?.title ?? "Skills Assessment"}
          </h1>
          {data.assessment?.description && (
            <p className="mt-1 text-sm text-muted-foreground">{data.assessment.description}</p>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            {data.assessment?.duration_minutes != null && (
              <Badge variant="outline" className="gap-1 text-[11px] text-muted-foreground">
                <Clock className="h-3 w-3" /> {data.assessment.duration_minutes} min
              </Badge>
            )}
            {data.assessment?.total_score != null && (
              <Badge variant="outline" className="text-[11px] text-muted-foreground">
                {data.assessment.total_score} points
              </Badge>
            )}
            {data.assessment?.difficulty && (
              <Badge variant="outline" className="text-[11px] capitalize text-muted-foreground">
                {data.assessment.difficulty}
              </Badge>
            )}
          </div>
          {data.assessment?.instructions && !submitted && (
            <p className="mt-3 rounded-lg border border-border/40 bg-muted/20 px-3 py-2 text-[12px] text-foreground/80">
              {data.assessment.instructions}
            </p>
          )}
        </motion.div>

        {/* Not available */}
        {!data.available && !submitted && (
          <div className="rounded-2xl border border-dashed border-border/40 py-12 text-center">
            <AlertTriangle className="mx-auto mb-3 h-8 w-8 text-muted-foreground/30" />
            <p className="text-sm text-muted-foreground">
              No assessment is available for this application yet.
            </p>
          </div>
        )}

        {/* Submitted → report */}
        {submitted && report && <ReportView report={report} />}

        {/* Take the assessment */}
        {!submitted && data.available && (
          <>
            <div className="space-y-4">
              {questions.map((q, i) => {
                const hasOptions = Array.isArray(q.options) && q.options.length > 0;
                return (
                  <motion.div
                    key={q.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.03 }}
                    className="glass rounded-2xl p-5 space-y-3"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-sm font-semibold text-foreground">
                        <span className="text-primary">Q{i + 1}.</span>{" "}
                        {q.scenario ? <span className="text-muted-foreground">{q.scenario} </span> : null}
                        {q.question}
                      </p>
                      {q.score != null && (
                        <Badge variant="outline" className="shrink-0 text-[10px] text-muted-foreground">
                          {q.score} pts
                        </Badge>
                      )}
                    </div>

                    {hasOptions ? (
                      <div className="space-y-1.5">
                        {q.options!.map((opt, oi) => (
                          <label
                            key={oi}
                            className={cn(
                              "flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-[13px] transition-colors",
                              answers[q.id] === opt
                                ? "border-primary/50 bg-primary/10 text-foreground"
                                : "border-border/40 hover:bg-muted/20 text-foreground/80",
                            )}
                          >
                            <input
                              type="radio"
                              name={q.id}
                              value={opt}
                              checked={answers[q.id] === opt}
                              onChange={() => setAnswers((p) => ({ ...p, [q.id]: opt }))}
                              className="accent-primary"
                            />
                            {opt}
                          </label>
                        ))}
                      </div>
                    ) : (
                      <textarea
                        rows={5}
                        placeholder="Type your answer…"
                        value={answers[q.id] ?? ""}
                        onChange={(e) => setAnswers((p) => ({ ...p, [q.id]: e.target.value }))}
                        className="w-full resize-y rounded-lg border border-border/40 bg-background px-3 py-2 text-[13px] leading-relaxed text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/40"
                      />
                    )}
                  </motion.div>
                );
              })}
            </div>

            <div className="glass gradient-border sticky bottom-4 flex items-center justify-between gap-3 rounded-2xl p-4">
              <p className="text-[12px] text-muted-foreground">
                {answeredCount} / {questions.length} answered
                {answeredCount < questions.length && " — unanswered questions score 0."}
              </p>
              <Button onClick={onSubmit} disabled={submit.isPending || answeredCount === 0} className="gap-2 glow-blue">
                {submit.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" /> Grading…
                  </>
                ) : (
                  <>
                    <Send className="h-4 w-4" /> Submit assessment
                  </>
                )}
              </Button>
            </div>
            {submit.isError && (
              <p className="text-xs text-rose-400">
                {(submit.error as Error)?.message ?? "Submission failed. Please try again."}
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function ReportView({ report }: { report: BackendAssessmentReport }) {
  const pct = Math.round(report.score_percent ?? 0);
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-5"
    >
      {/* Score header */}
      <div className="glass gradient-border rounded-2xl p-6 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
          <Award className="h-6 w-6 text-primary" />
        </div>
        <p className="mt-3 text-[11px] uppercase tracking-widest text-muted-foreground">Your score</p>
        <p className={cn("font-heading text-5xl font-bold", scoreColor(pct))}>{pct}%</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {report.score != null && report.max_score != null
            ? `${Math.round(report.score)} of ${Math.round(report.max_score)} points`
            : ""}
        </p>
        {report.provisional && (
          <Badge variant="outline" className="mt-3 gap-1 border-amber-500/30 bg-amber-500/5 text-[10px] text-amber-300">
            <AlertTriangle className="h-2.5 w-2.5" /> Provisional — pending reviewer confirmation
          </Badge>
        )}
        <div className="mt-3 rounded-md border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-[12px] text-emerald-300">
          <CheckCircle2 className="mr-1 inline h-3 w-3" />
          Submitted — your tutor has been notified with your results.
        </div>
      </div>

      {report.summary && (
        <div className="glass rounded-2xl p-5">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-primary/80">Summary</p>
          <p className="mt-1 text-[13px] leading-relaxed text-foreground/90">{report.summary}</p>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        {report.strengths.length > 0 && (
          <div className="glass rounded-2xl p-5">
            <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-emerald-400/90">
              <ThumbsUp className="h-3 w-3" /> Strengths
            </p>
            <ul className="mt-2 space-y-1">
              {report.strengths.map((s, i) => (
                <li key={i} className="text-[12px] text-emerald-200/80">• {s}</li>
              ))}
            </ul>
          </div>
        )}
        {report.areas_to_improve.length > 0 && (
          <div className="glass rounded-2xl p-5">
            <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-amber-400/90">
              <Target className="h-3 w-3" /> Areas to improve
            </p>
            <ul className="mt-2 space-y-1">
              {report.areas_to_improve.map((s, i) => (
                <li key={i} className="text-[12px] text-amber-200/80">• {s}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Per-question breakdown */}
      {report.per_question.length > 0 && (
        <div className="space-y-3">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
            Question-by-question
          </p>
          {report.per_question.map((pq, i) => {
            const qpct = pq.max > 0 ? (pq.awarded / pq.max) * 100 : 0;
            return (
              <div key={pq.question_id || i} className="glass rounded-2xl p-5 space-y-2">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm font-medium text-foreground">
                    <span className="text-primary">Q{i + 1}.</span> {pq.question}
                  </p>
                  <Badge variant="outline" className={cn("shrink-0 text-[11px] font-mono", scoreColor(qpct))}>
                    {Math.round(pq.awarded)}/{Math.round(pq.max)}
                  </Badge>
                </div>
                <div className="rounded-lg border border-border/40 bg-muted/20 px-3 py-2">
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground/70">Your answer</p>
                  <p className="mt-0.5 whitespace-pre-wrap text-[12px] text-foreground/80">
                    {pq.answer || "(no answer)"}
                  </p>
                </div>
                {pq.feedback && (
                  <p className="text-[12px] text-muted-foreground">
                    <span className="font-semibold text-foreground/80">Feedback:</span> {pq.feedback}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}

      <div className="text-center">
        <Button asChild variant="ghost" size="sm">
          <Link href="/candidate/applications">Back to applications</Link>
        </Button>
      </div>
    </motion.div>
  );
}

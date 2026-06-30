"use client";

import { use, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Loader2,
  Send,
  ChevronRight,
  Sparkles,
  CheckCircle2,
  RefreshCcw,
  Square,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  useFinishInterviewSession,
  useGenerateInterviewFollowUp,
  useGenerateInterviewQuestionsRuntime,
  useEvaluateInterviewSession,
  useInterviewSession,
  useRecordInterviewAnswer,
} from "@/lib/hooks";
import type { BackendInterviewTurn } from "@/lib/api";

type QueueItem = {
  text: string;
  category: string;
  is_followup?: boolean;
  parent_index?: number | null;
};

export default function InterviewRunPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const { data, isLoading, isError, refetch } = useInterviewSession(id);

  const generateQuestions = useGenerateInterviewQuestionsRuntime();
  const recordAnswer = useRecordInterviewAnswer();
  const generateFollowUp = useGenerateInterviewFollowUp();
  const finish = useFinishInterviewSession();
  const evaluate = useEvaluateInterviewSession();

  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState<"idle" | "evaluating">("idle");
  const seeded = useRef(false);

  // Seed queue from server on first load.
  useEffect(() => {
    if (!data) return;
    if (!seeded.current && data.questions.length > 0 && data.turns.length === 0) {
      seeded.current = true;
      setQueue(
        data.questions.map((q) => ({
          text: q.text,
          category: q.category,
        })),
      );
    }
  }, [data]);

  const askedIndexes = useMemo(
    () => new Set(data?.turns.map((t) => t.index) ?? []),
    [data?.turns],
  );

  const askedFollowUps = useMemo(() => {
    const map = new Map<number, number>();
    for (const t of data?.turns ?? []) {
      if (t.is_followup && t.parent_index != null) {
        map.set(t.parent_index, (map.get(t.parent_index) ?? 0) + 1);
      }
    }
    return map;
  }, [data?.turns]);

  const currentQuestion: QueueItem | null = queue[0] ?? null;

  async function ensureQuestionsExist() {
    if (!data) return;
    if (data.questions.length > 0) return;
    setError(null);
    try {
      await generateQuestions.mutateAsync({
        interviewId: data.session.id,
        orgId: data.session.organization_id,
      });
      await refetch();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not generate questions.");
    }
  }

  async function onSubmitAnswer() {
    if (!data || !currentQuestion) return;
    if (!answer.trim()) {
      setError("Please record an answer before continuing.");
      return;
    }
    setError(null);
    try {
      await recordAnswer.mutateAsync({
        sessionId: id,
        question: currentQuestion.text,
        answer: answer.trim(),
        is_followup: !!currentQuestion.is_followup,
        parent_index: currentQuestion.parent_index ?? null,
      });
      setAnswer("");
      setQueue((prev) => prev.slice(1));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save answer.");
    }
  }

  async function onAskFollowUp() {
    if (!data || !data.turns.length) {
      setError("Record at least one answer before asking a follow-up.");
      return;
    }
    const parent = data.turns[data.turns.length - 1];
    setError(null);
    try {
      const r = await generateFollowUp.mutateAsync({
        sessionId: id,
        parentIndex: parent.index,
      });
      setQueue((prev) => [
        {
          text: r.question,
          category: "follow_up",
          is_followup: true,
          parent_index: parent.index,
        },
        ...prev,
      ]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not generate follow-up.");
    }
  }

  async function onSkipQuestion() {
    setQueue((prev) => prev.slice(1));
  }

  async function onFinish() {
    setError(null);
    try {
      const r = await finish.mutateAsync(id);
      if (!r.ok) {
        setError("Could not finish interview.");
        return;
      }
      setRunning("evaluating");
      try {
        await evaluate.mutateAsync(id);
      } catch (e) {
        setError(
          e instanceof Error
            ? `Saved, but evaluation failed: ${e.message}`
            : "Saved, but evaluation failed.",
        );
        setRunning("idle");
        return;
      }
      router.push(`/interviews/${id}/report`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not finish.");
    }
  }

  if (isLoading) {
    return (
      <Centered>
        <Loader2 className="h-5 w-5 animate-spin text-primary" />
        <p className="mt-2 text-sm text-muted-foreground">Loading interview…</p>
      </Centered>
    );
  }
  if (isError || !data) {
    return (
      <Centered>
        <p className="text-sm text-red-400">Interview not found.</p>
      </Centered>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-6 max-w-4xl space-y-5">
      <div className="flex items-center justify-between">
        <Link href={`/candidates/${data.session.candidate_id}`}>
          <Button variant="ghost" size="sm" className="gap-1.5 text-muted-foreground -ml-2">
            <ArrowLeft className="h-3.5 w-3.5" /> Back to candidate
          </Button>
        </Link>
        <Badge variant="outline" className="text-[11px]">
          {data.session.interview_type} · {data.session.status}
        </Badge>
      </div>

      <div className="glass rounded-xl p-4 space-y-1">
        <p className="text-[11px] uppercase tracking-widest text-primary">Preparation</p>
        <h1 className="text-xl font-semibold">
          {data.candidate.full_name ?? "Candidate"}
        </h1>
        <p className="text-[12px] text-muted-foreground">
          {data.job.title ?? "—"}
          {data.job.seniority_level ? ` · ${data.job.seniority_level}` : ""}
        </p>
      </div>

      {data.questions.length === 0 && data.turns.length === 0 && (
        <div className="glass rounded-xl p-4">
          <p className="text-sm">
            No questions generated yet. Click below to draft an interview plan
            using the existing question generator.
          </p>
          <Button
            className="mt-3"
            onClick={() => void ensureQuestionsExist()}
            disabled={generateQuestions.isPending}
          >
            {generateQuestions.isPending ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Sparkles className="h-3 w-3" />
            )}
            Generate questions
          </Button>
        </div>
      )}

      {/* Current question + answer panel */}
      {currentQuestion && (
        <div className="glass rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <Badge variant="outline" className="text-[10px]">
              {currentQuestion.is_followup ? "follow-up" : currentQuestion.category}
            </Badge>
            <span className="text-[11px] text-muted-foreground">
              {data.turns.length} of {data.questions.length + (data.turns.filter((t) => t.is_followup).length)} answered
            </span>
          </div>
          <p className="text-base font-medium leading-relaxed">{currentQuestion.text}</p>
          <Textarea
            rows={6}
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="Type the candidate's answer (text mode). Voice mode coming soon."
          />
          {error && <p className="text-sm text-red-400">{error}</p>}
          <div className="flex flex-wrap gap-2">
            <Button
              onClick={() => void onSubmitAnswer()}
              disabled={recordAnswer.isPending || !answer.trim()}
            >
              {recordAnswer.isPending ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Send className="h-3 w-3" />
              )}
              Save & Next
            </Button>
            <Button
              variant="ghost"
              onClick={() => void onAskFollowUp()}
              disabled={generateFollowUp.isPending || data.turns.length === 0}
              title={
                (askedFollowUps.get(data.turns[data.turns.length - 1]?.index ?? -1) ?? 0) >= 2
                  ? "Two follow-ups already asked for this answer"
                  : undefined
              }
            >
              {generateFollowUp.isPending ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <RefreshCcw className="h-3 w-3" />
              )}
              Generate follow-up
            </Button>
            <Button variant="ghost" onClick={() => void onSkipQuestion()}>
              <ChevronRight className="h-3 w-3" /> Skip
            </Button>
          </div>
        </div>
      )}

      {!currentQuestion && data.questions.length > 0 && data.turns.length > 0 && (
        <div className="glass rounded-xl p-4 space-y-3">
          <p className="text-sm">
            <CheckCircle2 className="inline h-4 w-4 text-emerald-400 mr-1" />
            All questions answered. Generate one final follow-up or finish the interview to run the evaluation.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="ghost"
              onClick={() => void onAskFollowUp()}
              disabled={generateFollowUp.isPending}
            >
              {generateFollowUp.isPending ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <RefreshCcw className="h-3 w-3" />
              )}
              One more follow-up
            </Button>
            <Button
              onClick={() => void onFinish()}
              disabled={finish.isPending || running === "evaluating"}
            >
              {finish.isPending || running === "evaluating" ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Square className="h-3 w-3" />
              )}
              {running === "evaluating" ? "Evaluating…" : "Finish & Evaluate"}
            </Button>
          </div>
        </div>
      )}

      {/* Recorded turns */}
      {data.turns.length > 0 && (
        <div className="space-y-2">
          <p className="text-[11px] uppercase tracking-widest text-muted-foreground">
            Transcript so far
          </p>
          {data.turns.map((t) => (
            <Turn key={t.index} t={t} />
          ))}
        </div>
      )}
    </div>
  );
}

function Turn({ t }: { t: BackendInterviewTurn }) {
  return (
    <div className="rounded-xl border border-border/40 bg-muted/20 p-3 space-y-1">
      <p className="text-[11px] text-muted-foreground">
        Q{t.index}
        {t.is_followup ? ` (follow-up of Q${t.parent_index})` : ""}
      </p>
      <p className="text-sm font-medium">{t.question}</p>
      <p className="text-[13px] text-foreground/90 whitespace-pre-wrap">{t.answer}</p>
    </div>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="text-center">{children}</div>
    </div>
  );
}

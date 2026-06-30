"use client";

import { use, useState } from "react";
import {
  AlertCircle,
  Bot,
  CheckCircle2,
  ChevronRight,
  Loader2,
  MessageSquare,
  RefreshCw,
  Send,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import {
  useInterviewSession,
  useRecordInterviewAnswer,
  useGenerateInterviewFollowUp,
  useFinishInterviewSession,
  useEvaluateInterviewSession,
  useInterviewReport,
} from "@/lib/hooks";

interface Props {
  params: Promise<{ sid: string }>;
}

type Turn = {
  question: string;
  answer: string;
  is_followup?: boolean;
};

export default function CandidateInterviewPage({ params }: Props) {
  const { sid } = use(params);

  const {
    data: session,
    isLoading,
    refetch: refetchSession,
  } = useInterviewSession(sid);

  const { mutateAsync: recordAnswer, isPending: recordingAnswer } = useRecordInterviewAnswer();
  const { mutateAsync: generateFollowUp, isPending: generatingFollowup } = useGenerateInterviewFollowUp();
  const { mutateAsync: finish, isPending: finishing } = useFinishInterviewSession();
  const { mutateAsync: evaluate, isPending: evaluating } = useEvaluateInterviewSession();
  const { data: report } = useInterviewReport(sid, session?.session?.status === "completed");

  const [currentAnswer, setCurrentAnswer] = useState("");
  const [activeQuestionIndex, setActiveQuestionIndex] = useState(0);

  const turns: Turn[] = session?.turns ?? [];
  const questions: string[] = (session?.questions ?? []).map((q) => q.text);
  const currentQuestion =
    questions[activeQuestionIndex] ??
    (turns[activeQuestionIndex]?.question || "");
  const isCompleted = session?.session?.status === "completed" || session?.session?.status === "evaluated";
  const canFinish = turns.length > 0 && !isCompleted;

  async function handleSubmitAnswer() {
    if (!currentAnswer.trim()) return;
    try {
      await recordAnswer({
        sessionId: sid,
        question: currentQuestion,
        answer: currentAnswer.trim(),
      });
      setCurrentAnswer("");
      setActiveQuestionIndex((i) => i + 1);
      await refetchSession();
    } catch {
      toast.error("Failed to save answer — please try again.");
    }
  }

  async function handleGetFollowUp() {
    try {
      await generateFollowUp({
        sessionId: sid,
        parentIndex: activeQuestionIndex - 1,
      });
      await refetchSession();
    } catch {
      toast.error("Failed to generate follow-up question.");
    }
  }

  async function handleFinish() {
    try {
      await finish(sid);
      await evaluate(sid);
      await refetchSession();
      toast.success("Interview submitted! Your results are being processed.");
    } catch {
      toast.error("Failed to submit interview.");
    }
  }

  // ── Loading ────────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex flex-col items-center gap-4 p-6 py-24 text-center">
        <AlertCircle className="h-10 w-10 text-destructive" />
        <p className="font-semibold">Interview session not found</p>
        <Button variant="outline" size="sm" onClick={() => refetchSession()} className="gap-2">
          <RefreshCw className="h-3.5 w-3.5" /> Retry
        </Button>
      </div>
    );
  }

  // ── Completed state ─────────────────────────────────────────────────────────
  if (isCompleted) {
    return (
      <div className="flex flex-col gap-6 p-6 max-w-2xl">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <CheckCircle2 className="h-6 w-6 text-green-500" />
            Interview Complete
          </h1>
          <p className="text-muted-foreground mt-1">
            Thank you for completing your interview. Results are being reviewed.
          </p>
        </div>

        {/* Summary stats */}
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl border border-border bg-card p-4 text-center">
            <p className="text-2xl font-bold text-primary">{turns.length}</p>
            <p className="text-xs text-muted-foreground">Questions Answered</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-4 text-center">
            <p className="text-2xl font-bold text-primary capitalize">
              {session.session.interview_type ?? "Mixed"}
            </p>
            <p className="text-xs text-muted-foreground">Interview Type</p>
          </div>
        </div>

        {/* Transcript review */}
        <div className="rounded-xl border border-border bg-card p-5 space-y-4">
          <h3 className="text-sm font-semibold">Interview Transcript</h3>
          <div className="space-y-4 max-h-96 overflow-y-auto pr-1">
            {turns.map((turn, i) => (
              <div key={i} className="space-y-2">
                <div className="rounded-lg bg-muted/40 p-3">
                  <p className="text-xs font-semibold text-muted-foreground mb-1 flex items-center gap-1.5">
                    <Bot className="h-3 w-3" /> Interviewer
                  </p>
                  <p className="text-sm">{turn.question}</p>
                </div>
                <div className="rounded-lg bg-primary/5 border border-primary/10 p-3 ml-4">
                  <p className="text-xs font-semibold text-primary/70 mb-1">Your Answer</p>
                  <p className="text-sm">{turn.answer}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* AI report if available */}
        {report && (
          <div className="rounded-xl border border-green-300 dark:border-green-800 bg-green-50 dark:bg-green-950/20 p-5 space-y-3">
            <div className="flex items-center gap-2">
              <Bot className="h-4 w-4 text-green-600 dark:text-green-400" />
              <h3 className="text-sm font-semibold text-green-700 dark:text-green-300">
                AI Evaluation Available
              </h3>
            </div>
            <p className="text-sm text-green-700 dark:text-green-300">
              Your interview has been evaluated. The hiring team will review your
              results and get back to you soon.
            </p>
          </div>
        )}
      </div>
    );
  }

  // ── Active interview ─────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-5 p-6 max-w-2xl h-full">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold">Live Interview</h1>
          <p className="text-sm text-muted-foreground capitalize">
            {session.session.interview_type ?? "Mixed"} Interview
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-xs">
            Q {Math.min(activeQuestionIndex + 1, questions.length)} / {questions.length}
          </Badge>
          {canFinish && (
            <Button
              size="sm"
              variant="outline"
              className="gap-1.5 text-xs"
              onClick={handleFinish}
              disabled={finishing || evaluating}
            >
              {finishing || evaluating ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <CheckCircle2 className="h-3.5 w-3.5" />
              )}
              {evaluating ? "Evaluating…" : "Finish Interview"}
            </Button>
          )}
        </div>
      </div>

      {/* Conversation history */}
      <div className="flex-1 overflow-y-auto space-y-4 min-h-0">
        {turns.map((turn, i) => (
          <div key={i} className="space-y-2">
            <div className="rounded-lg bg-muted/40 p-3">
              <p className="text-xs font-semibold text-muted-foreground mb-1 flex items-center gap-1.5">
                <Bot className="h-3 w-3" /> Question {i + 1}
              </p>
              <p className="text-sm">{turn.question}</p>
            </div>
            <div className="rounded-lg bg-primary/5 border border-primary/10 p-3 ml-4">
              <p className="text-xs font-semibold text-primary/70 mb-1">Your Answer</p>
              <p className="text-sm">{turn.answer}</p>
            </div>
          </div>
        ))}

        {/* Current question */}
        {currentQuestion && activeQuestionIndex < questions.length && (
          <div className="rounded-lg border-2 border-primary/30 bg-primary/5 p-4 space-y-3">
            <div className="flex items-start gap-2">
              <Bot className="h-4 w-4 text-primary shrink-0 mt-0.5" />
              <div>
                <p className="text-xs font-semibold text-primary/70 mb-1">
                  Question {activeQuestionIndex + 1}
                </p>
                <p className="text-sm font-medium">{currentQuestion}</p>
              </div>
            </div>

            <Separator />

            <div className="space-y-2">
              <Textarea
                placeholder="Type your answer here…"
                className="resize-none min-h-[120px] text-sm"
                value={currentAnswer}
                onChange={(e) => setCurrentAnswer(e.target.value)}
                disabled={recordingAnswer}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && e.ctrlKey) {
                    handleSubmitAnswer();
                  }
                }}
              />
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs text-muted-foreground">
                  Press Ctrl+Enter to submit
                </p>
                <div className="flex items-center gap-2">
                  {turns.length > 0 && (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="gap-1.5 text-xs"
                      onClick={handleGetFollowUp}
                      disabled={generatingFollowup}
                    >
                      {generatingFollowup ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5" />
                      )}
                      Get follow-up
                    </Button>
                  )}
                  <Button
                    size="sm"
                    className="gap-1.5"
                    onClick={handleSubmitAnswer}
                    disabled={recordingAnswer || !currentAnswer.trim()}
                  >
                    {recordingAnswer ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                    Submit
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeQuestionIndex >= questions.length && questions.length > 0 && (
          <div className="rounded-lg border border-green-300 dark:border-green-800 bg-green-50 dark:bg-green-950/20 p-4 text-center">
            <CheckCircle2 className="h-6 w-6 text-green-500 mx-auto mb-2" />
            <p className="text-sm font-semibold text-green-700 dark:text-green-300">
              All questions answered!
            </p>
            <p className="text-xs text-green-600 dark:text-green-400 mt-1">
              Click &quot;Finish Interview&quot; when you&apos;re ready.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

"use client";

import { use, useEffect, useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft, Brain, Video, XCircle, CheckCircle2,
  Loader2, Sparkles, Mic,
  FileText, User, ThumbsUp, ThumbsDown, AlertCircle,
  RefreshCw, Save,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils/cn";
import { useAuthStore } from "@/lib/stores/auth.store";
import {
  useAnalyzeInterview,
  useInterviewHumanDecision,
  useRecallState,
  useSetRecallMode,
  useStartRecallBot,
  useStopRecallBot,
  useSyncRecallBot,
  useRecallTranscript,
} from "@/lib/hooks";
import { interviewsApi } from "@/lib/api";

// Normalise a model score to a 0–100 integer. The backend now emits 0–100,
// but legacy packets may carry a 0–1 fraction — handle both so the score
// never renders as e.g. 580.
function scoreOutOf100(v: number): number {
  const n = v <= 1 ? v * 100 : v;
  return Math.round(Math.min(100, Math.max(0, n)));
}

// ── Analysis section ──────────────────────────────────────────────────────────

function AnalysisSection({ analysis }: { analysis: {
  summary: { summary_json: Record<string, unknown>; created_at: string } | null;
  hr_evaluation: { score_json: Record<string, unknown> | null; recommendation: string | null; confidence: number | null } | null;
  technical_evaluation: { score_json: Record<string, unknown> | null; recommendation: string | null; confidence: number | null } | null;
  decision_packet: { recommendation: string | null; final_score: number | null; confidence: number | null } | null;
} }) {
  const { summary, hr_evaluation, technical_evaluation, decision_packet } = analysis;

  const recColor = (r: string | null) =>
    r === "proceed" || r === "hire" ? "text-emerald-400"
    : r === "reject" ? "text-rose-400"
    : "text-amber-400";

  return (
    <div className="space-y-4">
      {/* Summary */}
      {summary && (
        <div className="rounded-xl border border-border/40 bg-muted/10 p-4">
          <h4 className="font-heading text-[12px] font-bold text-muted-foreground uppercase tracking-wider mb-2">Interview Summary</h4>
          <div className="text-[13px] text-muted-foreground space-y-1">
            {Object.entries(summary.summary_json).map(([k, v]) => (
              <div key={k}>
                <span className="font-semibold text-foreground">{k.replace(/_/g, " ")}:</span>{" "}
                {Array.isArray(v) ? v.join(", ") : String(v)}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Evaluations */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {hr_evaluation && (
          <div className="rounded-xl border border-border/40 bg-muted/10 p-4">
            <h4 className="font-heading text-[12px] font-bold text-muted-foreground uppercase tracking-wider mb-2">HR Evaluation</h4>
            <p className={cn("text-lg font-bold font-heading capitalize", recColor(hr_evaluation.recommendation))}>
              {hr_evaluation.recommendation ?? "N/A"}
            </p>
            {hr_evaluation.confidence != null && (
              <p className="text-[11px] text-muted-foreground mt-1">
                Confidence: {Math.round(hr_evaluation.confidence * 100)}%
              </p>
            )}
          </div>
        )}
        {technical_evaluation && (
          <div className="rounded-xl border border-border/40 bg-muted/10 p-4">
            <h4 className="font-heading text-[12px] font-bold text-muted-foreground uppercase tracking-wider mb-2">Technical Evaluation</h4>
            <p className={cn("text-lg font-bold font-heading capitalize", recColor(technical_evaluation.recommendation))}>
              {technical_evaluation.recommendation ?? "N/A"}
            </p>
            {technical_evaluation.confidence != null && (
              <p className="text-[11px] text-muted-foreground mt-1">
                Confidence: {Math.round(technical_evaluation.confidence * 100)}%
              </p>
            )}
          </div>
        )}
      </div>

      {/* Decision packet */}
      {decision_packet && (
        <div className={cn(
          "rounded-xl border p-4",
          decision_packet.recommendation === "hire" || decision_packet.recommendation === "proceed"
            ? "border-emerald-500/30 bg-emerald-500/5"
            : decision_packet.recommendation === "reject"
            ? "border-rose-500/30 bg-rose-500/5"
            : "border-amber-500/30 bg-amber-500/5"
        )}>
          <h4 className="font-heading text-[12px] font-bold text-muted-foreground uppercase tracking-wider mb-2">AI Decision Packet</h4>
          <div className="flex items-center gap-4">
            <div>
              <p className="text-[11px] text-muted-foreground">Recommendation</p>
              <p className={cn("font-heading text-base font-bold capitalize", recColor(decision_packet.recommendation))}>
                {decision_packet.recommendation ?? "N/A"}
              </p>
            </div>
            {decision_packet.final_score != null && (
              <div>
                <p className="text-[11px] text-muted-foreground">Score</p>
                <p className="font-heading text-base font-bold text-foreground">
                  {scoreOutOf100(decision_packet.final_score)}/100
                </p>
              </div>
            )}
            {decision_packet.confidence != null && (
              <div>
                <p className="text-[11px] text-muted-foreground">Confidence</p>
                <p className="font-heading text-base font-bold text-foreground">
                  {Math.round(decision_packet.confidence * 100)}%
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Note Taker panel (post-meeting transcript only) ───────────────────────────
//
// INST.md §6/§7 — the visible label is "Note Taker" and only the post-meeting
// transcript mode is offered. The bot records the call; the final transcript
// appears here after the meeting and feeds Run Analysis.

const STATUS_LABEL: Record<string, string> = {
  pending: "Idle",
  joining: "Joining the call",
  in_waiting_room: "Waiting room",
  in_call: "In the call",
  recording: "Recording",
  recording_done: "Recording complete",
  done: "Transcript ready",
  failed: "Failed",
  cancelled: "Stopped",
};

const STATUS_COLOR: Record<string, string> = {
  pending: "border-muted/30 text-muted-foreground",
  joining: "border-sky-500/40 text-sky-400",
  in_waiting_room: "border-amber-500/40 text-amber-400",
  in_call: "border-sky-500/40 text-sky-400",
  recording: "border-rose-500/40 text-rose-400 animate-pulse",
  recording_done: "border-amber-500/40 text-amber-400",
  done: "border-emerald-500/40 text-emerald-400",
  failed: "border-rose-500/40 text-rose-400",
  cancelled: "border-muted/40 text-muted-foreground",
};


function NoteTakerPanel({ interviewId }: { interviewId: string }) {
  const { data: state, isLoading } = useRecallState(interviewId);
  const setMode = useSetRecallMode();
  const start = useStartRecallBot();
  const stop = useStopRecallBot();
  const sync = useSyncRecallBot();

  const status = state?.status ?? "pending";
  const isLive =
    status === "joining"
    || status === "in_call"
    || status === "recording"
    || status === "in_waiting_room";
  const isDone = status === "done" || status === "recording_done";
  const hasBot = Boolean(state?.bot_id);
  const canSync = hasBot && !isLive;

  // INST.md §7 — only the post-meeting transcript mode is supported. Ensure
  // the interview is set to that mode (no real-time option in the UI).
  useEffect(() => {
    if (state && state.recording_mode !== "post_meeting" && !isLive) {
      setMode.mutate({ interviewId, mode: "post_meeting" });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state?.recording_mode, isLive]);

  const { data: tx } = useRecallTranscript(interviewId, isDone);

  if (isLoading) {
    return (
      <div className="glass gradient-border rounded-2xl p-6">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading note taker state…
        </div>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.05 }}
      className="glass gradient-border rounded-2xl p-6"
    >
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <h3 className="font-heading text-sm font-bold text-foreground flex items-center gap-2">
          <Video className="h-4 w-4 text-primary" /> Note Taker
        </h3>
        <Badge
          variant="outline"
          className={cn("text-[10px]", STATUS_COLOR[status] ?? STATUS_COLOR.pending)}
        >
          {STATUS_LABEL[status] ?? status}
        </Badge>
      </div>

      {!state?.configured && (
        <div className="mb-4 rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-[12px] text-amber-300">
          The Note Taker is not configured. Paste your <code>RECALL_API_KEY</code>{" "}
          into <code>backend/.env</code> and restart the backend, then refresh
          this page.
        </div>
      )}

      {/* Post-meeting transcript is the only supported mode. */}
      <div className="mb-4 rounded-lg border border-primary/30 bg-primary/5 px-3 py-2 text-[12px] text-foreground/80">
        <span className="font-semibold text-foreground">Post-meeting transcript.</span>{" "}
        The Note Taker records the call and the final transcript appears here
        after the meeting ends. AI analysis uses this final transcript.
      </div>

      {/* ── Start / Stop ── */}
      <div className="flex items-center gap-2 flex-wrap">
        <Button
          size="sm"
          className="gap-1.5 text-xs glow-blue"
          onClick={() => start.mutate(interviewId)}
          disabled={isLive || start.isPending || !state?.configured}
          title={isLive ? "Note taker already in the call." : undefined}
        >
          {start.isPending
            ? <Loader2 className="h-3 w-3 animate-spin" />
            : <Video className="h-3 w-3" />}
          Start note taker
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="gap-1.5 text-xs"
          onClick={() => stop.mutate(interviewId)}
          disabled={!hasBot || stop.isPending || (!isLive && status !== "recording_done")}
        >
          {stop.isPending
            ? <Loader2 className="h-3 w-3 animate-spin" />
            : <XCircle className="h-3 w-3" />}
          Stop
        </Button>
        {canSync && (
          <Button
            size="sm"
            variant="ghost"
            className="gap-1.5 text-xs"
            onClick={() => sync.mutate(interviewId)}
            disabled={sync.isPending}
            title="Fetch the latest status and final transcript from the note taker"
          >
            {sync.isPending
              ? <Loader2 className="h-3 w-3 animate-spin" />
              : <RefreshCw className="h-3 w-3" />}
            Sync transcript
          </Button>
        )}
        {state?.status_message && (
          <span className="text-[11px] text-muted-foreground">{state.status_message}</span>
        )}
      </div>

      {(start.error || stop.error || setMode.error || sync.error) && (
        <p className="mt-2 text-xs text-rose-400">
          {String(
            (start.error as Error | undefined)?.message
              ?? (stop.error as Error | undefined)?.message
              ?? (setMode.error as Error | undefined)?.message
              ?? (sync.error as Error | undefined)?.message,
          )}
        </p>
      )}

      {/* ── Post-meeting transcript pane ── */}
      {isDone && (
        <div className="mt-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Final transcript
            </p>
            {state?.transcript_path && (
              <span className="text-[10px] text-muted-foreground">
                Saved to: <code>{state.transcript_path}</code>
              </span>
            )}
          </div>
          <div className="rounded-lg border border-border/40 bg-muted/10 p-3 max-h-96 overflow-y-auto whitespace-pre-wrap text-[13px] text-muted-foreground">
            {tx?.transcript_text?.trim() || "Transcript not available yet."}
          </div>
        </div>
      )}
    </motion.div>
  );
}


// ── HR Notes panel (INST.md §8/§9) ─────────────────────────────────────────────

function HrNotesPanel({ interviewId, orgId }: { interviewId: string; orgId: string }) {
  const qc = useQueryClient();
  const [notes, setNotes] = useState("");
  const [loaded, setLoaded] = useState(false);

  const notesQuery = useQuery({
    queryKey: ["interview", interviewId, "hr-notes"],
    queryFn: () => interviewsApi.getHrNotes(interviewId, orgId),
    enabled: Boolean(orgId),
  });

  useEffect(() => {
    if (notesQuery.data && !loaded) {
      setNotes(notesQuery.data.hr_notes ?? "");
      setLoaded(true);
    }
  }, [notesQuery.data, loaded]);

  const save = useMutation({
    mutationFn: () => interviewsApi.saveHrNotes(interviewId, orgId, notes),
    onSuccess: (data) => {
      qc.setQueryData(["interview", interviewId, "hr-notes"], data);
      toast.success("HR Notes saved.");
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Failed to save HR Notes"),
  });

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      className="glass gradient-border rounded-2xl p-6"
    >
      <h3 className="font-heading text-sm font-bold text-foreground flex items-center gap-2 mb-2">
        <Mic className="h-4 w-4 text-primary" /> HR Notes
      </h3>
      <p className="text-[13px] text-muted-foreground mb-3">
        Capture human observations — communication quality, strong/weak answers,
        concerns, clarifications, and any decision notes the Note Taker
        wouldn&apos;t catch. These notes are saved with the interview and used as
        extra evidence when you run AI analysis.
      </p>

      <textarea
        rows={6}
        placeholder="e.g. Communicated clearly. Strong on system design; hesitant on testing strategy. Flag: gap on the required cloud platform…"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        className="w-full rounded-lg border border-border/40 bg-muted/20 px-3 py-2 text-[13px] text-foreground placeholder:text-muted-foreground/30 focus:outline-none focus:ring-1 focus:ring-primary/40 resize-y"
      />

      <div className="flex items-center gap-2 mt-3">
        <Button
          size="sm"
          variant="outline"
          className="gap-1.5 text-xs"
          onClick={() => save.mutate()}
          disabled={save.isPending || notesQuery.isLoading}
        >
          {save.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
          Save Notes
        </Button>
        {save.isSuccess && <span className="text-xs text-emerald-400">Saved.</span>}
      </div>
    </motion.div>
  );
}


// ── Main page ────────────────────────────────────────────────────────────────

export default function InterviewDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: interviewId } = use(params);
  const router = useRouter();
  const { user } = useAuthStore();
  const orgId = user?.orgId ?? "";

  const [decisionNotes, setDecisionNotes] = useState("");
  const [overrideReason, setOverrideReason] = useState("");
  const [analysisResult, setAnalysisResult] = useState<Parameters<typeof AnalysisSection>[0]["analysis"] | null>(null);

  const analyzeInterview = useAnalyzeInterview();
  const humanDecision = useInterviewHumanDecision();

  // PATHS.md §1 — once a proceed/reject decision is taken (or the interview
  // is completed), hide the action buttons and show a read-only status.
  const decisionStateQuery = useQuery({
    queryKey: ["interview", interviewId, "decision-state"],
    queryFn: () => interviewsApi.getDecisionState(interviewId, orgId),
    enabled: Boolean(orgId),
  });
  const decisionTaken =
    (decisionStateQuery.data?.decision_taken ?? false) || humanDecision.isSuccess;
  const finalDecisionValue = decisionStateQuery.data?.final_decision ?? null;

  const handleAnalyze = () => {
    analyzeInterview.mutate(
      { interviewId, orgId },
      {
        onSuccess: (data) => {
          setAnalysisResult({
            summary: data.summary
              ? { summary_json: data.summary.summary_json, created_at: data.summary.created_at }
              : null,
            hr_evaluation: data.hr_evaluation
              ? {
                  score_json: data.hr_evaluation.score_json,
                  recommendation: data.hr_evaluation.recommendation,
                  confidence: data.hr_evaluation.confidence,
                }
              : null,
            technical_evaluation: data.technical_evaluation
              ? {
                  score_json: data.technical_evaluation.score_json,
                  recommendation: data.technical_evaluation.recommendation,
                  confidence: data.technical_evaluation.confidence,
                }
              : null,
            decision_packet: data.decision_packet
              ? {
                  recommendation: data.decision_packet.recommendation,
                  final_score: data.decision_packet.final_score,
                  confidence: data.decision_packet.confidence,
                }
              : null,
          });
        },
      },
    );
  };

  const handleHumanDecision = (decision: "proceed" | "reject") => {
    humanDecision.mutate(
      {
        interviewId,
        orgId,
        finalDecision: decision,
        hrNotes: decisionNotes || undefined,
        overrideReason: overrideReason || undefined,
      },
      {
        onSuccess: (data) => {
          // The interview is now marked "completed" by the backend. On a
          // "proceed" decision, take the recruiter straight to the candidate's
          // decision-support page to continue the hiring decision.
          if (decision === "proceed" && data?.candidate_id) {
            router.push(`/candidates/${data.candidate_id}/decision`);
          }
        },
      },
    );
  };

  return (
    <div className="h-full overflow-y-auto">
      {/* Header */}
      <div className="sticky top-0 z-10 border-b border-border/50 bg-background/80 backdrop-blur-sm px-6 py-3 flex items-center gap-3">
        <Link href="/interviews">
          <Button variant="ghost" size="sm" className="gap-1.5 text-muted-foreground -ml-2">
            <ArrowLeft className="h-3.5 w-3.5" /> Interviews
          </Button>
        </Link>
        <div className="h-4 w-px bg-border/60" />
        <div className="flex items-center gap-2">
          <Brain className="h-4 w-4 text-primary" />
          <span className="font-heading text-sm font-bold text-foreground">Interview #{interviewId.slice(0, 8)}</span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {/* INST.md §12 — AI Runtime button removed. §13 — AI Report kept. */}
          <Link href={`/interviews/${interviewId}/report`}>
            <Button size="sm" variant="outline" className="gap-1.5 text-xs">
              <FileText className="h-3.5 w-3.5" /> AI Report
            </Button>
          </Link>
        </div>
      </div>

      <div className="p-6 max-w-4xl space-y-6">

        {/* ── Note Taker ── */}
        <NoteTakerPanel interviewId={interviewId} />

        {/* ── HR Notes ── */}
        <HrNotesPanel interviewId={interviewId} orgId={orgId} />

        {/* ── AI Analysis ── */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="glass gradient-border rounded-2xl p-6"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-heading text-sm font-bold text-foreground flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" /> AI Analysis
            </h3>
            <Button
              size="sm"
              className="gap-1.5 text-xs glow-blue"
              onClick={handleAnalyze}
              disabled={analyzeInterview.isPending}
            >
              {analyzeInterview.isPending
                ? <Loader2 className="h-3 w-3 animate-spin" />
                : <Brain className="h-3 w-3" />}
              Run Analysis
            </Button>
          </div>

          {analyzeInterview.isPending && (
            <div className="flex items-center gap-2 py-6 justify-center">
              <Loader2 className="h-5 w-5 animate-spin text-primary" />
              <span className="text-sm text-muted-foreground">Analyzing the post-meeting transcript…</span>
            </div>
          )}

          {analyzeInterview.isError && (
            <div className="flex items-start gap-2 text-rose-400 text-sm">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>
                {(analyzeInterview.error as Error)?.message ??
                  "Analysis failed. Make sure the Note Taker transcript is ready, then retry."}
              </span>
            </div>
          )}

          {analysisResult && !analyzeInterview.isPending && (
            <AnalysisSection analysis={analysisResult} />
          )}

          {!analysisResult && !analyzeInterview.isPending && !analyzeInterview.isError && (
            <p className="text-[13px] text-muted-foreground">
              Once the Note Taker&apos;s post-meeting transcript is ready, run AI
              analysis to get an evidence-grounded summary, HR + technical
              evaluations, and a recommendation. Analysis uses the transcript,
              your HR Notes, the job requirements, and the candidate profile.
            </p>
          )}
        </motion.div>

        {/* ── HR Decision ── */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="glass gradient-border rounded-2xl p-6"
        >
          <h3 className="font-heading text-sm font-bold text-foreground flex items-center gap-2 mb-1">
            <User className="h-4 w-4 text-primary" /> HR Decision
          </h3>
          <p className="text-[12px] text-muted-foreground mb-4">
            The AI recommends; HR decides. Record the final decision for this
            interview.
          </p>

          {decisionTaken ? (
            <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300 flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              {finalDecisionValue === "reject"
                ? "Interview completed — candidate was not moved forward."
                : "Interview completed and candidate moved forward to the next stage."}
            </div>
          ) : (
          <div className="space-y-4">
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Decision note (optional)</label>
              <textarea
                rows={3}
                placeholder="Short note explaining this decision…"
                value={decisionNotes}
                onChange={(e) => setDecisionNotes(e.target.value)}
                className="mt-1 w-full rounded-lg border border-border/40 bg-muted/20 px-3 py-2 text-[13px] text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/40 resize-none"
              />
            </div>

            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Override Reason (optional)</label>
              <input
                placeholder="Reason for overriding the AI recommendation…"
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                className="mt-1 w-full rounded-lg border border-border/40 bg-muted/20 px-3 py-2 text-[13px] text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/40"
              />
            </div>

            <div className="flex gap-3">
              <Button
                className="flex-1 gap-2 bg-emerald-600 hover:bg-emerald-500 text-white"
                onClick={() => handleHumanDecision("proceed")}
                disabled={humanDecision.isPending}
              >
                {humanDecision.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ThumbsUp className="h-4 w-4" />}
                Proceed to Next Stage
              </Button>
              <Button
                className="flex-1 gap-2 bg-rose-700 hover:bg-rose-600 text-white"
                onClick={() => handleHumanDecision("reject")}
                disabled={humanDecision.isPending}
              >
                {humanDecision.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ThumbsDown className="h-4 w-4" />}
                Reject Candidate
              </Button>
            </div>

            {humanDecision.isSuccess && (
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-center text-sm font-medium text-emerald-400"
              >
                Decision recorded successfully.
              </motion.p>
            )}
          </div>
          )}
        </motion.div>

      </div>
    </div>
  );
}

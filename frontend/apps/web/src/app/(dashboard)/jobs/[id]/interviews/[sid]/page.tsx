"use client";

import { use, useState } from "react";
import {
  AlertCircle,
  Bot,
  CheckCircle2,
  ChevronDown,
  Loader2,
  MessageSquare,
  RefreshCw,
  Shield,
  Sparkles,
  Star,
  Upload,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  useInterviewDetail,
  useInterviewAnalysis,
  useUploadTranscript,
  useAnalyzeInterview,
  useHumanDecision,
} from "@/lib/hooks";
import { useAuthStore } from "@/lib/stores/auth.store";

interface Props {
  params: Promise<{ id: string; sid: string }>;
}

// ── Sub-components ──────────────────────────────────────────────────────────

function TranscriptPanel({
  interviewId,
  orgId,
  transcript,
  onUploaded,
}: {
  interviewId: string;
  orgId: string;
  transcript: string;
  onUploaded: () => void;
}) {
  const [text, setText] = useState(transcript);
  const [uploading, setUploading] = useState(false);
  const { mutateAsync: upload } = useUploadTranscript();

  async function handleUpload() {
    if (!text.trim()) return;
    setUploading(true);
    try {
      await upload({ interviewId, orgId, transcriptText: text });
      toast.success("Transcript saved");
      onUploaded();
    } catch {
      toast.error("Failed to save transcript");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="flex flex-col gap-3 h-full">
      <div className="flex items-center gap-2">
        <MessageSquare className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold">Transcript</h3>
      </div>
      <Textarea
        className="flex-1 min-h-[400px] resize-none font-mono text-xs leading-relaxed"
        placeholder="Paste or type the interview transcript here…"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <Button
        size="sm"
        className="gap-2 w-full"
        onClick={handleUpload}
        disabled={uploading || !text.trim()}
      >
        {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
        Save Transcript
      </Button>
    </div>
  );
}

function RagSuggestionsPanel({
  ragContext,
}: {
  ragContext: { transcript_snippet?: string; interview_type?: string; quality?: string }[];
}) {
  if (ragContext.length === 0) {
    return (
      <div className="flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-amber-500" />
          <h3 className="text-sm font-semibold">RAG Context</h3>
        </div>
        <p className="text-xs text-muted-foreground rounded-lg border border-dashed border-border p-4 text-center">
          Similar past interviews will appear here after the analysis runs.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-amber-500" />
        <h3 className="text-sm font-semibold">RAG Context ({ragContext.length})</h3>
      </div>
      <p className="text-xs text-muted-foreground">
        Similar past interviews retrieved from vector store to inform the evaluation.
      </p>
      <div className="space-y-2">
        {ragContext.map((hit, i) => (
          <div key={i} className="rounded-lg border border-border bg-muted/20 p-3 space-y-1">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="text-[10px]">
                {hit.interview_type ?? "mixed"}
              </Badge>
              {hit.quality && (
                <span className="text-[10px] text-muted-foreground capitalize">{hit.quality} quality</span>
              )}
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed line-clamp-3">
              {hit.transcript_snippet ?? "No snippet available"}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function ScoreGauge({ label, score }: { label: string; score: number | null | undefined }) {
  if (score == null) return null;
  const pct = Math.min(100, Math.max(0, score));
  const color = pct >= 75 ? "bg-green-500" : pct >= 50 ? "bg-amber-500" : "bg-red-500";
  const textColor = pct >= 75 ? "text-green-600 dark:text-green-400" : pct >= 50 ? "text-amber-600 dark:text-amber-400" : "text-red-600 dark:text-red-400";
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className={cn("font-semibold tabular-nums", textColor)}>{pct.toFixed(0)}</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-muted/50">
        <div className={cn("h-full rounded-full", color)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function EvaluationSidebar({
  interviewId,
  orgId,
  analysis,
  onAnalyze,
  analyzing,
  onDecision,
}: {
  interviewId: string;
  orgId: string;
  analysis: ReturnType<typeof useInterviewAnalysis>["data"];
  onAnalyze: () => void;
  analyzing: boolean;
  onDecision: (decision: string) => void;
}) {
  const [decidingWith, setDecidingWith] = useState<string | null>(null);

  // The AI analysis payload is stored inside the summary's JSON blob.
  const summary = (analysis?.summary_json ?? {}) as Record<string, unknown>;
  const dp = summary.decision_packet as
    | { decision_packet_json?: unknown; recommendation?: string; final_score: number | null }
    | undefined;
  const hr = summary.hr_evaluation as Record<string, unknown> | undefined;
  const tech = summary.technical_evaluation as Record<string, unknown> | undefined;
  const comp = summary.compliance as Record<string, unknown> | undefined;

  const DECISION_OPTIONS = [
    { value: "accept", label: "Accept", color: "bg-green-600 hover:bg-green-700 text-white" },
    { value: "reject", label: "Reject", color: "bg-red-600 hover:bg-red-700 text-white" },
    { value: "hold",   label: "Hold",   color: "bg-amber-600 hover:bg-amber-700 text-white" },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <Bot className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold">AI Evaluation</h3>
      </div>

      {/* Run analysis button */}
      {!analysis ? (
        <Button size="sm" className="w-full gap-2" onClick={onAnalyze} disabled={analyzing}>
          {analyzing ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Sparkles className="h-4 w-4" />
          )}
          {analyzing ? "Analyzing…" : "Run AI Analysis"}
        </Button>
      ) : (
        <Button size="sm" variant="outline" className="w-full gap-2" onClick={onAnalyze} disabled={analyzing}>
          {analyzing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          Re-analyze
        </Button>
      )}

      {/* Decision packet */}
      {dp && (
        <>
          <Separator />
          <div className="space-y-3">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Decision Packet</p>
            <div className="rounded-lg border border-border bg-muted/20 p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">Recommendation</span>
                <span className="text-xs font-semibold">
                  {(dp.decision_packet_json as Record<string, unknown>)?.overall_recommendation as string ?? dp.recommendation ?? "—"}
                </span>
              </div>
              <ScoreGauge label="Final Score" score={dp.final_score} />
              <ScoreGauge
                label="HR Score"
                score={(dp.decision_packet_json as Record<string, unknown>)?.hr_score as number ?? null}
              />
              <ScoreGauge
                label="Technical Score"
                score={(dp.decision_packet_json as Record<string, unknown>)?.technical_score as number ?? null}
              />
            </div>
          </div>
        </>
      )}

      {/* Compliance */}
      {comp && (
        <>
          <Separator />
          <div className="flex items-center gap-2 rounded-lg border border-border p-3">
            <Shield className={cn(
              "h-4 w-4",
              (comp as Record<string, unknown>).compliance_status === "pass" ? "text-green-500" : "text-amber-500"
            )} />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold capitalize">
                Compliance: {(comp as Record<string, unknown>).compliance_status as string ?? "—"}
              </p>
              {((comp as Record<string, unknown>).detected_issues as string[] | undefined)?.length ? (
                <p className="text-[10px] text-muted-foreground">
                  {((comp as Record<string, unknown>).detected_issues as string[]).join(", ")}
                </p>
              ) : null}
            </div>
          </div>
        </>
      )}

      {/* HR Decision buttons */}
      {dp && (
        <>
          <Separator />
          <div className="space-y-2">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Record Decision</p>
            <div className="flex flex-col gap-2">
              {DECISION_OPTIONS.map((opt) => (
                <Button
                  key={opt.value}
                  size="sm"
                  className={cn("w-full", opt.color)}
                  disabled={decidingWith === opt.value}
                  onClick={() => {
                    setDecidingWith(opt.value);
                    onDecision(opt.value);
                  }}
                >
                  {decidingWith === opt.value ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4 mr-1" />
                  )}
                  {opt.label}
                </Button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function InterviewSessionPage({ params }: Props) {
  const { id: jobId, sid: interviewId } = use(params);

  // Source the org from the auth store (the legacy `paths_org` localStorage key
  // was never written, so reading it left orgId empty and the interview-analysis
  // query stayed disabled — the AI analysis panel never loaded).
  const { user } = useAuthStore();
  const orgId = user?.orgId ?? "";

  const {
    data: interviewDetail,
    isLoading: detailLoading,
    refetch: refetchDetail,
  } = useInterviewDetail(interviewId, orgId);

  const {
    data: analysis,
    isLoading: analysisLoading,
    refetch: refetchAnalysis,
  } = useInterviewAnalysis(interviewId, orgId);

  const { mutateAsync: analyze } = useAnalyzeInterview();
  const { mutateAsync: recordDecision } = useHumanDecision();

  const [analyzing, setAnalyzing] = useState(false);

  const existingTranscript =
    (interviewDetail?.turns?.map((t) =>
      `Q: ${t.question}\nA: ${t.answer}`
    ).join("\n\n") ?? "");

  const ragContext: Record<string, unknown>[] =
    (analysis as Record<string, unknown>)?.rag_context as Record<string, unknown>[] ?? [];

  async function handleAnalyze() {
    setAnalyzing(true);
    try {
      await analyze({ interviewId, orgId });
      await refetchAnalysis();
      toast.success("Analysis complete");
    } catch {
      toast.error("Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleDecision(decision: string) {
    try {
      await recordDecision({
        interviewId,
        orgId,
        finalDecision: decision,
      });
      toast.success(`Decision recorded: ${decision}`);
    } catch {
      toast.error("Failed to record decision");
    }
  }

  if (detailLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-[500px] rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-6 h-full">
      {/* Header */}
      <div>
        <h2 className="text-lg font-bold">
          Interview Session
          {interviewDetail?.session?.interview_type && (
            <span className="ml-2 text-sm font-normal text-muted-foreground capitalize">
              · {interviewDetail.session.interview_type}
            </span>
          )}
        </h2>
        <p className="text-sm text-muted-foreground">
          {interviewDetail?.candidate?.full_name ?? "Candidate"} ·{" "}
          {interviewDetail?.job?.title ?? "Job"}
        </p>
      </div>

      {/* 3-col layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1 min-h-0">
        {/* Col 1: Transcript */}
        <div className="rounded-xl border border-border bg-card p-4 overflow-auto">
          <TranscriptPanel
            interviewId={interviewId}
            orgId={orgId}
            transcript={existingTranscript}
            onUploaded={() => refetchDetail()}
          />
        </div>

        {/* Col 2: RAG Suggestions */}
        <div className="rounded-xl border border-border bg-card p-4 overflow-auto">
          <RagSuggestionsPanel ragContext={ragContext} />
        </div>

        {/* Col 3: Evaluation Sidebar */}
        <div className="rounded-xl border border-border bg-card p-4 overflow-auto">
          <EvaluationSidebar
            interviewId={interviewId}
            orgId={orgId}
            analysis={analysis}
            onAnalyze={handleAnalyze}
            analyzing={analyzing}
            onDecision={handleDecision}
          />
        </div>
      </div>
    </div>
  );
}

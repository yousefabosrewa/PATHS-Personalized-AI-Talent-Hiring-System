"use client";

import { use, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Download,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  Video,
  FileText,
  StickyNote,
  Gavel,
  PlayCircle,
  ExternalLink,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useEvaluateInterviewSession, useInterviewReport } from "@/lib/hooks";
import { interviewRuntimeApi } from "@/lib/api";
import type { BackendInterviewRecordingMeta } from "@/lib/api";

export default function InterviewReportPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data, isLoading, isError, refetch } = useInterviewReport(id);
  const evaluate = useEvaluateInterviewSession();
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const [evalDone, setEvalDone] = useState(false);

  const handleDownloadPdf = async () => {
    setPdfError(null);
    setPdfLoading(true);
    try {
      const blob = await interviewRuntimeApi.downloadReportPdf(id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const name = (data?.candidate?.full_name ?? "candidate").replace(/\s+/g, "_");
      a.download = `PATHS-Interview-Report-${name}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setPdfError(e instanceof Error ? e.message : "Could not generate the PDF.");
    } finally {
      setPdfLoading(false);
    }
  };

  if (isLoading) {
    return (
      <Centered>
        <Loader2 className="h-5 w-5 animate-spin text-primary" />
        <p className="mt-2 text-sm text-muted-foreground">Loading report…</p>
      </Centered>
    );
  }
  if (isError || !data) {
    return (
      <Centered>
        <p className="text-sm text-red-400">Could not load report.</p>
      </Centered>
    );
  }

  const dpRec = (data.decision_packet ?? {}) as Record<string, unknown>;
  const score = dpRec.final_score as number | undefined;
  const recommendation = dpRec.recommendation as string | undefined;
  const confidence = dpRec.confidence as number | undefined;
  const humanReview = dpRec.human_review_required as boolean | undefined;
  const hasDecisionDetail =
    asArray(dpRec.main_strengths).length > 0 ||
    asArray(dpRec.main_weaknesses).length > 0 ||
    asArray(dpRec.risk_flags).length > 0;

  return (
    <div className="h-full overflow-y-auto p-6 max-w-4xl space-y-5">
      <div className="flex items-center justify-between">
        <Link href={`/candidates/${data.candidate.id ?? ""}`}>
          <Button variant="ghost" size="sm" className="gap-1.5 text-muted-foreground -ml-2">
            <ArrowLeft className="h-3.5 w-3.5" /> Back to candidate
          </Button>
        </Link>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            onClick={() => {
              setEvalDone(false);
              evaluate.mutate(id, {
                onSuccess: () => {
                  setEvalDone(true);
                  void refetch();
                },
              });
            }}
            disabled={evaluate.isPending}
          >
            {evaluate.isPending ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Sparkles className="h-3 w-3" />
            )}
            {evaluate.isPending ? "Analyzing…" : "Re-evaluate"}
          </Button>
          <Button onClick={handleDownloadPdf} disabled={pdfLoading}>
            {pdfLoading ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Download className="h-3 w-3" />
            )}
            Download PDF
          </Button>
        </div>
      </div>

      {(evaluate.isError || pdfError || evalDone) && (
        <div className="space-y-1">
          {evaluate.isError && (
            <p className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-[12px] text-red-300">
              {(evaluate.error as Error)?.message ?? "Re-evaluation failed."}
            </p>
          )}
          {pdfError && (
            <p className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-[12px] text-red-300">
              {pdfError}
            </p>
          )}
          {evalDone && !evaluate.isError && (
            <p className="text-[12px] text-emerald-300">
              Analysis complete — report refreshed below.
            </p>
          )}
        </div>
      )}

      <div className="glass rounded-xl p-4 space-y-2">
        <div className="flex items-center gap-2">
          <p className="text-[11px] uppercase tracking-widest text-primary">Interview Report</p>
          {data.interview_type && (
            <Badge variant="outline" className="text-[10px] capitalize">
              {data.interview_type} interview
            </Badge>
          )}
        </div>
        <h1 className="text-2xl font-semibold">{data.candidate.full_name ?? "Candidate"}</h1>
        <p className="text-[13px] text-muted-foreground">
          {data.job.title ?? "—"}
          {data.job.seniority_level ? ` · ${data.job.seniority_level}` : ""}
        </p>
        <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Overall" value={score == null ? "—" : `${(score as number).toFixed(0)}/100`} />
          <Stat label="Recommendation" value={recommendation ?? "needs_human_review"} />
          <Stat
            label="Confidence"
            value={confidence == null ? "—" : `${Math.round((Number(confidence) <= 1 ? Number(confidence) * 100 : Number(confidence)))}%`}
          />
          <Stat
            label="Human review"
            value={humanReview ? "Required" : "Optional"}
          />
        </div>
        <div className="rounded-md border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-[12px] text-emerald-300 mt-2">
          <CheckCircle2 className="inline h-3 w-3 mr-1" />
          Decision support only — final hiring decisions are made by humans.
        </div>
      </div>

      {/* Recording (video) */}
      <RecordingSection id={id} meta={data.recording} />

      {/* Summary */}
      {data.summary && Object.keys(data.summary).length > 0 && (
        <Section title="Interview summary">
          <SummaryView summary={data.summary as Record<string, unknown>} />
        </Section>
      )}

      {/* Evaluations */}
      {data.evaluations.length > 0 && (
        <Section title="Evaluation">
          <div className="space-y-3">
            {data.evaluations.map((ev, i) => {
              const e = ev as Record<string, unknown>;
              const isScorecard =
                e.title != null || e.sub_scores != null || e.skill_scores != null;
              return isScorecard ? (
                <ScorecardItem key={i} ev={e} />
              ) : (
                <EvaluationItem key={i} evaluation={e} index={i} />
              );
            })}
          </div>
        </Section>
      )}

      {/* Decision packet detail */}
      {hasDecisionDetail && (
        <Section title="Decision packet">
          <div className="space-y-2 rounded-xl border border-border/40 bg-muted/10 p-4">
            <BulletGroup label="Main strengths" items={dpRec.main_strengths} positive />
            <BulletGroup label="Main weaknesses" items={dpRec.main_weaknesses} />
            <BulletGroup label="Risk flags" items={dpRec.risk_flags} negative />
          </div>
        </Section>
      )}

      {/* HR decision (human) */}
      {data.human_decision?.final_decision && (
        <Section title="HR decision">
          <div className="space-y-2 rounded-xl border border-border/40 bg-muted/10 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <Gavel className="h-4 w-4 text-primary" />
              <DecisionBadge value={data.human_decision.final_decision} />
              {data.human_decision.decided_by && (
                <span className="text-[12px] text-muted-foreground">
                  by {data.human_decision.decided_by}
                </span>
              )}
              {data.human_decision.decided_at && (
                <span className="text-[11px] text-muted-foreground">
                  · {new Date(data.human_decision.decided_at).toLocaleDateString()}
                </span>
              )}
            </div>
            {data.human_decision.hr_notes && (
              <p className="text-[13px] text-foreground/90 whitespace-pre-wrap">
                {data.human_decision.hr_notes}
              </p>
            )}
          </div>
        </Section>
      )}

      {/* HR notes (free text) */}
      {data.hr_notes && (
        <Section title="Interviewer notes">
          <div className="rounded-xl border border-border/40 bg-muted/10 p-4">
            <div className="mb-1 flex items-center gap-1.5 text-[11px] uppercase tracking-widest text-muted-foreground">
              <StickyNote className="h-3 w-3" /> Notes captured during the interview
            </div>
            <p className="text-[13px] text-foreground/90 whitespace-pre-wrap">{data.hr_notes}</p>
          </div>
        </Section>
      )}

      {/* Transcript — runtime Q/A turns, or flat recall/meeting text */}
      {data.turns.length > 0 ? (
        <Section title="Transcript">
          <div className="space-y-2">
            {data.turns.map((t) => (
              <div key={t.index} className="rounded-xl border border-border/40 bg-muted/20 p-3">
                <p className="text-[11px] text-muted-foreground">
                  Q{t.index}
                  {t.is_followup ? ` (follow-up of Q${t.parent_index})` : ""}
                </p>
                <p className="text-sm font-medium">{t.question}</p>
                <p className="text-[13px] text-foreground/90 whitespace-pre-wrap mt-1">
                  {t.answer}
                </p>
              </div>
            ))}
          </div>
        </Section>
      ) : data.transcript_text ? (
        <Section title="Transcript">
          <div className="rounded-xl border border-border/40 bg-muted/20 p-4">
            <div className="mb-2 flex items-center gap-1.5 text-[11px] uppercase tracking-widest text-muted-foreground">
              <FileText className="h-3 w-3" /> Meeting transcript
            </div>
            <p className="text-[13px] leading-relaxed text-foreground/90 whitespace-pre-wrap">
              {data.transcript_text}
            </p>
          </div>
        </Section>
      ) : null}

      {!data.completed && (
        <div className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[12px] text-amber-200">
          <AlertTriangle className="inline h-3 w-3 mr-1" />
          The interview is not finalized. Run the interview to completion or click <strong>Re-evaluate</strong> above.
        </div>
      )}
    </div>
  );
}

/* ── helpers ─────────────────────────────────────────────────────────── */

function str(v: unknown): string {
  return typeof v === "string" ? v : "";
}
function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}
function asArray(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}
function humanize(k: string): string {
  return k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <p className="text-[11px] uppercase tracking-widest text-muted-foreground">
        {title}
      </p>
      {children}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border/40 bg-muted/20 p-3">
      <p className="text-[10px] uppercase tracking-widest text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-semibold">{value}</p>
    </div>
  );
}

function SummaryView({ summary }: { summary: Record<string, unknown> }) {
  const short = str(summary.short_summary);
  const detailed = str(summary.detailed_summary);
  const legacy =
    str(summary.summary) ||
    str(summary.candidate_summary) ||
    str(summary.interview_summary);
  const lead = short || legacy || detailed;
  const keyAnswers = isRecord(summary.key_answers) ? summary.key_answers : null;
  const jra = summary.job_requirement_alignment;

  return (
    <div className="space-y-3 rounded-xl border border-border/40 bg-muted/10 p-4">
      {lead && <p className="text-[13px] leading-relaxed">{lead}</p>}
      {detailed && detailed !== lead && (
        <p className="text-[12px] leading-relaxed text-foreground/80">{detailed}</p>
      )}

      {keyAnswers && Object.keys(keyAnswers).length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-widest text-primary">Key answers</p>
          <div className="mt-1 space-y-1">
            {Object.entries(keyAnswers).map(([k, v]) =>
              v ? (
                <p key={k} className="text-[12px] text-foreground/90">
                  <span className="font-medium">{humanize(k)}:</span> {String(v)}
                </p>
              ) : null,
            )}
          </div>
        </div>
      )}

      <BulletGroup
        label="Strengths"
        items={summary.strengths_observed ?? summary.strengths}
        positive
      />
      <BulletGroup
        label="Weaknesses"
        items={summary.weaknesses_observed ?? summary.weaknesses}
      />
      <BulletGroup label="Risks" items={summary.risks} negative />
      <BulletGroup label="Missing skills" items={summary.missing_skills} />
      <BulletGroup label="Unclear / missing points" items={summary.unclear_or_missing_points} />
      <BulletGroup label="CV claims verified" items={summary.candidate_cv_claims_verified} positive />
      <BulletGroup label="CV claims not verified" items={summary.candidate_cv_claims_not_verified} negative />
      <BulletGroup label="Notable quotes / evidence" items={summary.important_quotes_or_answer_evidence} />
      <BulletGroup label="Development plan" items={summary.development_plan} positive />

      {typeof jra === "string" && jra.trim() && (
        <div>
          <p className="text-[10px] uppercase tracking-widest text-amber-200">
            Job requirement alignment
          </p>
          <p className="text-[12px] text-foreground/90">{jra}</p>
        </div>
      )}
      {isRecord(jra) && Object.keys(jra).length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-widest text-amber-200">
            Job requirement alignment
          </p>
          <div className="mt-1 space-y-1">
            {Object.entries(jra).map(([k, v]) => (
              <p key={k} className="text-[12px] text-foreground/90">
                <span className="font-medium">{humanize(k)}:</span> {String(v)}
              </p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function BulletGroup({
  label,
  items,
  positive,
  negative,
}: {
  label: string;
  items: unknown;
  positive?: boolean;
  negative?: boolean;
}) {
  if (!Array.isArray(items) || items.length === 0) return null;
  const color = positive
    ? "text-emerald-300"
    : negative
      ? "text-red-300"
      : "text-amber-200";
  return (
    <div>
      <p className={`text-[10px] uppercase tracking-widest ${color}`}>{label}</p>
      <ul className="ml-4 list-disc text-[12px] text-foreground/90">
        {items.map((s, i) => (
          <li key={i}>{String(s)}</li>
        ))}
      </ul>
    </div>
  );
}

function ScoreGrid({ scores }: { scores: Record<string, number> }) {
  return (
    <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
      {Object.entries(scores).map(([k, v]) => {
        const pct = Math.max(0, Math.min(100, (Number(v) / 10) * 100));
        return (
          <div key={k} className="flex items-center gap-2">
            <span className="w-40 shrink-0 text-[11px] text-foreground/80">{humanize(k)}</span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted/40">
              <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
            </div>
            <span className="w-10 text-right text-[11px] tabular-nums text-muted-foreground">
              {Number(v).toFixed(0)}/10
            </span>
          </div>
        );
      })}
    </div>
  );
}

function ScorecardItem({ ev }: { ev: Record<string, unknown> }) {
  const title = String(ev.title ?? ev.evaluation_type ?? "Evaluation");
  const score = ev.score as number | null | undefined;
  const scale = (ev.score_scale as number | undefined) ?? 10;
  const subScores = isRecord(ev.sub_scores) ? (ev.sub_scores as Record<string, number>) : {};
  const skillScores = isRecord(ev.skill_scores) ? (ev.skill_scores as Record<string, number>) : {};
  const strengths = asArray(ev.strengths);
  const weaknesses = asArray(ev.weaknesses);
  const risks = asArray(ev.risks);
  const devNeeds = asArray(ev.development_needs);
  const recommendation = typeof ev.recommendation === "string" ? ev.recommendation : "";
  const confidence = ev.confidence as number | undefined;
  const evidence = ev.evidence;

  const hasData =
    score != null ||
    Object.keys(subScores).length > 0 ||
    Object.keys(skillScores).length > 0 ||
    strengths.length > 0 ||
    weaknesses.length > 0;

  return (
    <div className="rounded-xl border border-border/40 bg-muted/10 p-4 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold">{title}</p>
        <div className="flex items-center gap-2">
          {confidence != null && (
            <span className="text-[10px] text-muted-foreground">
              Confidence{" "}
              {Math.round(Number(confidence) <= 1 ? Number(confidence) * 100 : Number(confidence))}%
            </span>
          )}
          {score != null ? (
            <Badge variant="outline" className="text-[10px]">
              {Number(score).toFixed(1)}/{scale}
            </Badge>
          ) : (
            <Badge variant="outline" className="text-[10px] text-muted-foreground">
              Not assessed
            </Badge>
          )}
        </div>
      </div>

      {!hasData && (
        <p className="text-[12px] text-muted-foreground">
          This evaluation was not assessed in this interview.
        </p>
      )}

      {Object.keys(subScores).length > 0 && <ScoreGrid scores={subScores} />}
      {Object.keys(skillScores).length > 0 && (
        <div className="space-y-1">
          <p className="text-[10px] uppercase tracking-widest text-primary">Skill scores</p>
          <ScoreGrid scores={skillScores} />
        </div>
      )}

      <BulletGroup label="Strengths" items={strengths} positive />
      <BulletGroup label="Weaknesses" items={weaknesses} />
      <BulletGroup label="Risks" items={risks} negative />
      <BulletGroup label="Development needs" items={devNeeds} />

      {Array.isArray(evidence) && evidence.length > 0 && (
        <BulletGroup label="Evidence" items={evidence} />
      )}
      {typeof evidence === "string" && evidence.trim() && (
        <div>
          <p className="text-[10px] uppercase tracking-widest text-muted-foreground">Evidence</p>
          <p className="text-[12px] text-foreground/80">{evidence}</p>
        </div>
      )}

      {recommendation && (
        <div className="rounded-md border border-primary/20 bg-primary/5 px-3 py-2">
          <p className="text-[10px] uppercase tracking-widest text-primary">Recommendation</p>
          <p className="text-[12px] text-foreground/90">{recommendation}</p>
        </div>
      )}
    </div>
  );
}

function EvaluationItem({
  evaluation,
  index,
}: {
  evaluation: Record<string, unknown>;
  index: number;
}) {
  const q = (evaluation.question as string) ?? `Question ${index + 1}`;
  const a = (evaluation.answer as string) ?? null;
  const score = evaluation.score as number | undefined;
  const reasoning = evaluation.reasoning as string | undefined;
  const evidence = evaluation.evidence as string | undefined;
  const skills = evaluation.skills_tested as unknown[] | undefined;
  const strengths = evaluation.strengths as unknown[] | undefined;
  const weaknesses = evaluation.weaknesses as unknown[] | undefined;
  return (
    <div className="rounded-xl border border-border/40 bg-muted/10 p-3 space-y-1">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-sm font-medium">{q}</p>
        {score != null && (
          <Badge variant="outline" className="text-[10px]">
            {Number(score).toFixed(1)}/10
          </Badge>
        )}
      </div>
      {a && <p className="text-[12px] text-foreground/80 whitespace-pre-wrap">{a}</p>}
      {reasoning && <p className="text-[12px] text-muted-foreground"><strong>Reasoning:</strong> {reasoning}</p>}
      {evidence && <p className="text-[12px] text-muted-foreground"><strong>Evidence:</strong> {evidence}</p>}
      {Array.isArray(skills) && skills.length > 0 && (
        <p className="text-[11px] text-primary">Skills tested · {skills.map(String).join(", ")}</p>
      )}
      {Array.isArray(strengths) && strengths.length > 0 && (
        <p className="text-[11px] text-emerald-400/90">+ {strengths.map(String).join(" · ")}</p>
      )}
      {Array.isArray(weaknesses) && weaknesses.length > 0 && (
        <p className="text-[11px] text-amber-400/90">– {weaknesses.map(String).join(" · ")}</p>
      )}
    </div>
  );
}

function DecisionBadge({ value }: { value: string }) {
  const v = value.toLowerCase();
  const cls =
    v === "accepted"
      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
      : v === "rejected"
        ? "border-red-500/30 bg-red-500/10 text-red-300"
        : v === "hold"
          ? "border-amber-500/30 bg-amber-500/10 text-amber-200"
          : "border-primary/30 bg-primary/10 text-primary";
  return (
    <span
      className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium capitalize ${cls}`}
    >
      {value.replace(/_/g, " ")}
    </span>
  );
}

function RecordingSection({
  id,
  meta,
}: {
  id: string;
  meta: BackendInterviewRecordingMeta | null;
}) {
  const [state, setState] = useState<"idle" | "loading" | "loaded" | "error">("idle");
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  // Purely-runtime AI interviews have no recall recording or meeting — skip.
  if (!meta || (!meta.has_recording && !meta.meeting_url)) return null;

  const load = async () => {
    setState("loading");
    setStatusMsg(null);
    try {
      const res = await interviewRuntimeApi.getRecording(id);
      setVideoUrl(res.video_url);
      setStatusMsg(res.status_message ?? res.status ?? null);
      setState(res.video_url ? "loaded" : "error");
    } catch (e) {
      setStatusMsg(e instanceof Error ? e.message : "Could not load the recording.");
      setState("error");
    }
  };

  return (
    <Section title="Recording">
      <div className="space-y-3 rounded-xl border border-border/40 bg-muted/10 p-4">
        {state === "loaded" && videoUrl ? (
          // eslint-disable-next-line jsx-a11y/media-has-caption
          <video
            src={videoUrl}
            controls
            className="w-full rounded-lg border border-border/40 bg-black"
          />
        ) : (
          <div className="flex flex-col items-start gap-2">
            <div className="flex items-center gap-2 text-[12px] text-muted-foreground">
              <Video className="h-4 w-4 text-primary" />
              {meta.has_recording
                ? "A meeting recording was captured for this interview."
                : "No recording was captured for this interview."}
            </div>
            {meta.has_recording && (
              <Button
                size="sm"
                variant="secondary"
                onClick={load}
                disabled={state === "loading"}
              >
                {state === "loading" ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <PlayCircle className="h-3 w-3" />
                )}
                {state === "loading" ? "Loading video…" : "Load video"}
              </Button>
            )}
            {state === "error" && (
              <p className="text-[12px] text-amber-300">
                {statusMsg
                  ? `Recording not ready yet (${statusMsg}). It may still be processing — try again shortly.`
                  : "The recording isn’t ready yet. It may still be processing — try again shortly."}
              </p>
            )}
            {meta.meeting_url && (
              <a
                href={meta.meeting_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-[12px] text-primary hover:underline"
              >
                <ExternalLink className="h-3 w-3" /> Open meeting link
              </a>
            )}
          </div>
        )}
      </div>
    </Section>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="text-center">{children}</div>
    </div>
  );
}

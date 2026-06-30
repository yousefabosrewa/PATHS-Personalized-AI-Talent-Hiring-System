"use client";

/**
 * IDSS 9-stage rubric — READ-ONLY report.
 *
 * The hiring decision and the development plan are owned by the single
 * "Hiring Manager Final Decision" + "Development Plan" sections on the
 * Decision Support page. This panel only *explains* the score (rubric,
 * bias flags, summary) and offers a PDF export — it no longer carries its
 * own decision buttons or dev-plan card (those were duplicates).
 */

import { useMemo, useState } from "react";
import { Loader2, ShieldAlert } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useDecisionReport } from "@/lib/hooks";
import { dssApi, type BackendIdssV2, type BackendPerStageBreakdown } from "@/lib/api";

const STAGE_LABELS: Record<string, string> = {
  cv_profile_fit: "CV / Profile Fit",
  job_requirement_match: "Job Requirement Match",
  vector_similarity: "Vector Similarity",
  graph_similarity: "Graph Similarity",
  technical_interview: "Technical Interview",
  hr_interview: "HR / Behavioural Interview",
  assessment: "Assessment / Practical",
  human_feedback: "Human Feedback",
};

const STAGE_MISSING_COPY: Record<string, Record<string, string>> = {
  cv_profile_fit: {
    missing_candidate_input: "Missing because the candidate has not uploaded enough profile or CV information.",
    missing_recruiter_input: "Missing because the recruiter has not run the scoring step yet.",
  },
  job_requirement_match: {
    missing_job_requirements: "Missing because the job requirements were not fully defined by the recruiter / hiring team.",
    missing_recruiter_input: "Missing because the recruiter has not specified required skills for this job.",
  },
  vector_similarity: {
    missing_candidate_input: "Missing because the candidate's profile lacks the text needed to embed a comparable vector.",
    missing_recruiter_input: "Missing because the job description has not been embedded yet.",
  },
  graph_similarity: {
    missing_candidate_input: "Missing because the candidate's tagged skills/experience graph is too sparse to compare.",
  },
  outreach_engagement: {
    missing_outreach_activity: "No outreach engagement evidence is available yet because the candidate has not interacted with outreach messages.",
  },
  technical_interview: {
    missing_recruiter_input: "Missing because no technical interview has been scheduled or evaluated by the hiring team yet.",
  },
  hr_interview: {
    missing_recruiter_input: "Missing because no HR / behavioural interview has been recorded by the hiring team yet.",
  },
  assessment: {
    missing_recruiter_input: "Missing because no assessment has been assigned or graded by the hiring team yet.",
  },
  human_feedback: {
    missing_recruiter_input: "Missing because the hiring team has not recorded any human review notes yet.",
  },
};

const GENERIC_MISSING_COPY: Record<string, string> = {
  missing_candidate_input: "Missing because the candidate did not complete or upload this profile information.",
  missing_recruiter_input: "Missing because the recruiter or hiring team did not record this evidence yet.",
  missing_job_requirements: "Missing because the job requirements were not fully defined by the recruiter / hiring team.",
  missing_outreach_activity: "No outreach engagement evidence is available yet because the candidate has not interacted with outreach messages.",
  not_applicable: "Not applicable for this role.",
};

function missingExplanation(stage: string, reason: string | undefined): string {
  if (!reason || reason === "available") return "";
  return (
    STAGE_MISSING_COPY[stage]?.[reason]
    ?? GENERIC_MISSING_COPY[reason]
    ?? "Missing evidence — provide more information to score this stage."
  );
}

export function IdssPanel({ packetId, orgId }: { packetId: string; orgId: string }) {
  const { data, isLoading, isError } = useDecisionReport(packetId, orgId);
  const idss = data?.idss_v2 ?? null;

  if (isLoading) {
    return (
      <div className="glass rounded-xl p-4 flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading IDSS report…
      </div>
    );
  }
  if (isError || !data) {
    return (
      <div className="glass rounded-xl p-4 text-sm text-red-400">
        Could not load IDSS report.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <Header data={data} />
      </div>

      {idss && <RubricTable idss={idss} />}

      {idss && (
        <HumanFeedbackInput
          packetId={packetId}
          orgId={orgId}
          current={idss.score_breakdown?.human_feedback}
        />
      )}

      {data.per_stage_breakdown?.length ? (
        <PerStageBreakdown stages={data.per_stage_breakdown} />
      ) : null}

      {idss?.bias_guardrail_notes?.length ? (
        <BiasFlag notes={idss.bias_guardrail_notes} />
      ) : null}
    </div>
  );
}

function Header({ data }: { data: NonNullable<ReturnType<typeof useDecisionReport>["data"]> }) {
  const score = data.idss_v2?.final_score ?? data.final_score;
  const rec = data.idss_v2?.recommendation ?? data.recommendation;
  // "Next action" tracks the HR Manager's decision, not the AI's suggestion:
  // it waits for the manager, then shows Accepted / Rejected once they decide.
  const decision = (data.hr_decision?.final_hr_decision ?? "").toLowerCase();
  const nextAction =
    ["accepted", "accept", "hire", "hired"].includes(decision)
      ? "Accepted"
      : ["rejected", "reject"].includes(decision)
        ? "Rejected"
        : "Waiting for HR Manager decision";
  return (
    <div className="glass rounded-xl p-4 grid w-full grid-cols-1 gap-3 sm:grid-cols-3">
      <Stat label="Final score" value={score == null ? "—" : `${Number(score).toFixed(1)} / 100`} />
      <Stat label="Recommendation" value={rec ?? "—"} />
      <Stat label="Next action" value={nextAction} />
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

function RubricTable({ idss }: { idss: BackendIdssV2 }) {
  const stages = useMemo(
    () =>
      Object.keys(STAGE_LABELS)
        .map((key) => ({ key, ...(idss.score_breakdown[key] ?? null) }))
        .filter((s) => s),
    [idss],
  );
  return (
    <div className="glass rounded-xl p-4 space-y-2">
      <p className="text-[11px] uppercase tracking-widest text-primary">
        9-Stage Weighted Rubric
      </p>
      {idss.overrides_applied?.length ? (
        <p className="text-[11px] text-amber-300">
          Override(s) applied: {idss.overrides_applied.join(", ")}
        </p>
      ) : null}
      <div className="space-y-1.5">
        {stages.map((s) => {
          const explanation = missingExplanation(
            s.key,
            (s as { missing_reason?: string }).missing_reason,
          );
          return (
            <div key={s.key} className="rounded-md border border-border/40 bg-muted/10 px-3 py-2">
              <div className="grid grid-cols-12 items-center gap-2">
                <span className="col-span-4 text-[12px] font-medium">{STAGE_LABELS[s.key]}</span>
                <span className="col-span-1 text-[11px] text-muted-foreground">{s.weight}%</span>
                <div className="col-span-5 h-2 overflow-hidden rounded-full bg-muted/30">
                  <div
                    className={
                      "h-full " +
                      (s.missing
                        ? "bg-amber-400/40"
                        : (s.score ?? 0) >= 75
                          ? "bg-emerald-400"
                          : (s.score ?? 0) >= 50
                            ? "bg-primary"
                            : "bg-red-400/80")
                    }
                    style={{
                      width: s.missing ? "100%" : `${Math.max(0, Math.min(100, s.score ?? 0))}%`,
                    }}
                  />
                </div>
                <span
                  className={
                    "col-span-2 text-right text-[11px] " +
                    (s.missing ? "text-amber-300" : "text-foreground")
                  }
                >
                  {s.missing ? "missing" : `${(s.score ?? 0).toFixed(0)} / 100`}
                </span>
              </div>
              {s.missing && explanation && (
                <p className="mt-1.5 text-[11px] leading-snug text-amber-200/80">{explanation}</p>
              )}
            </div>
          );
        })}
      </div>
      {idss.summary_for_hiring_manager && (
        <p className="text-[12px] text-foreground/90">{idss.summary_for_hiring_manager}</p>
      )}
      {idss.final_reasoning && (
        <p className="text-[11px] text-muted-foreground">{idss.final_reasoning}</p>
      )}
      {idss.missing_evidence?.length ? (
        <p className="text-[11px] text-amber-300">
          Missing evidence: {idss.missing_evidence.join(", ")}
        </p>
      ) : null}
    </div>
  );
}

function HumanFeedbackInput({
  packetId,
  orgId,
  current,
}: {
  packetId: string;
  orgId: string;
  current?: { score?: number | null; missing?: boolean; weight?: number };
}) {
  const qc = useQueryClient();
  const existing =
    current && !current.missing && current.score != null
      ? String(Math.round(current.score))
      : "";
  const [score, setScore] = useState<string>(existing);
  const [notes, setNotes] = useState("");
  const mutation = useMutation({
    mutationFn: () =>
      dssApi.setHumanFeedback(packetId, orgId, {
        score: Number(score),
        notes: notes.trim() || undefined,
      }),
    onSuccess: () => {
      toast.success("Human feedback saved — final score updated.");
      qc.invalidateQueries({ queryKey: ["decision-report", packetId] });
      qc.invalidateQueries({ queryKey: ["dss-packet"] });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Could not save"),
  });
  const n = Number(score);
  const valid = score !== "" && Number.isFinite(n) && n >= 0 && n <= 100;

  return (
    <div className="glass rounded-xl p-4 space-y-2">
      <p className="text-[11px] uppercase tracking-widest text-primary">
        Human feedback — your HR score
      </p>
      <p className="text-[11px] text-muted-foreground">
        Score this candidate 0–100. It feeds the weighted rubric ({current?.weight ?? 10}%) and
        recomputes the final score.
        {existing && <span className="text-emerald-400/80"> Current: {existing}/100.</span>}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="number"
          min={0}
          max={100}
          value={score}
          onChange={(e) => setScore(e.target.value)}
          placeholder="0–100"
          className="w-24 rounded-md border border-border/40 bg-background px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary/40"
        />
        <input
          type="text"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Optional note (rationale)"
          className="min-w-[180px] flex-1 rounded-md border border-border/40 bg-background px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary/40"
        />
        <Button size="sm" onClick={() => mutation.mutate()} disabled={!valid || mutation.isPending}>
          {mutation.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : "Save score"}
        </Button>
      </div>
    </div>
  );
}

function PerStageBreakdown({ stages }: { stages: BackendPerStageBreakdown[] }) {
  return (
    <div className="glass rounded-xl p-4 space-y-2">
      <p className="text-[11px] uppercase tracking-widest text-primary">
        Per-Stage Breakdown — this job&apos;s pipeline
      </p>
      <p className="text-[11px] text-muted-foreground">
        Each stage the candidate went through: their score, the AI explanation, and the hiring team&apos;s notes.
      </p>
      <div className="space-y-2">
        {stages.map((st) => {
          const score = st.score;
          const tone =
            score == null ? "text-muted-foreground"
            : score >= 75 ? "text-emerald-400"
            : score >= 50 ? "text-amber-400"
            : "text-red-400";
          return (
            <div key={st.key} className="rounded-md border border-border/40 bg-muted/10 p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[12px] font-semibold">{st.label}</span>
                <span className={"text-[12px] font-bold tabular-nums " + tone}>
                  {score == null ? "Not scored yet" : `${score.toFixed(0)} / 100`}
                </span>
              </div>
              {st.ai_explanation && (
                <p className="mt-1 text-[11px] leading-snug text-foreground/85">
                  <span className="font-semibold text-primary/80">AI: </span>
                  {st.ai_explanation}
                </p>
              )}
              {st.hr_notes && (
                <p className="mt-1 text-[11px] leading-snug text-foreground/85">
                  <span className="font-semibold text-amber-300/90">HR notes: </span>
                  {st.hr_notes}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function BiasFlag({ notes }: { notes: string[] }) {
  return (
    <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-[12px] text-amber-200 space-y-1">
      <p className="flex items-center gap-2 font-semibold">
        <ShieldAlert className="h-3 w-3" /> Bias guardrail flags detected
      </p>
      <ul className="ml-4 list-disc">
        {notes.map((n, i) => (
          <li key={i} className="text-amber-100/90">{n}</li>
        ))}
      </ul>
      <p className="text-amber-100/80">
        Human review is required before any decision is finalised.
      </p>
    </div>
  );
}

"use client";

/**
 * Rich development plan section for the Decision Support page.
 *
 * Detailed 18-month plan split into six 3-month phases, each with skills,
 * tasks/projects, learning resources, KPIs, manager check-ins and evidence.
 * Tailored to the hiring decision:
 *   • accepted → internal-growth plan (level up & excel in this role)
 *   • rejected → reapplication-readiness plan (close the gaps for this job)
 *
 * Self-contained: it fetches the plan (decision report), auto-generates it
 * once a decision has been recorded, and offers approve / send / revise.
 */

import { useEffect, useRef, useState } from "react";
import { Loader2, Sparkles, CheckCircle2, RefreshCcw, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  useDecisionReport,
  useGenerateDevelopmentPlan,
  useApprovePlan,
  useRevisePlan,
  useSendPlanFeedback,
  useUpdateCandidateFeedback,
} from "@/lib/hooks";

const PHASE_ORDER = [
  "month_1_3",
  "month_4_6",
  "month_7_9",
  "month_10_12",
  "month_13_15",
  "month_16_18",
];

const PHASE_DEFAULT_LABELS: Record<string, string> = {
  month_1_3: "Month 1-3 — Onboarding & Foundation Gaps",
  month_4_6: "Month 4-6 — Role-Specific Technical Growth",
  month_7_9: "Month 7-9 — Applied Projects & Performance Goals",
  month_10_12: "Month 10-12 — Advanced Ownership & Cross-Functional Collaboration",
  month_13_15: "Month 13-15 — Leadership / Mentoring / Specialisation Path",
  month_16_18: "Month 16-18 — Promotion Readiness & Long-Term Retention",
};

type PhaseFields = {
  label?: string;
  skills_to_improve?: string[];
  tasks_or_projects?: string[];
  learning_resources?: string[];
  measurable_outcomes_or_kpis?: string[];
  manager_check_in_points?: string[];
  evidence_to_collect?: string[];
};

function renderPlanItem(it: unknown): string {
  if (it == null) return "";
  if (typeof it === "string" || typeof it === "number") return String(it);
  if (typeof it === "object") {
    const o = it as Record<string, unknown>;
    const title = (o.title ?? o.name ?? o.resource ?? "") as string;
    const type = (o.type ?? "") as string;
    const reason = (o.reason ?? o.description ?? "") as string;
    const parts = [title, type ? `(${type})` : "", reason ? `— ${reason}` : ""].filter(Boolean);
    if (parts.length) return parts.join(" ");
    try { return JSON.stringify(it); } catch { return String(it); }
  }
  return String(it);
}

function PhaseCard({ phaseKey, phase }: { phaseKey: string; phase: PhaseFields }) {
  const [open, setOpen] = useState(false);
  const label = phase.label || PHASE_DEFAULT_LABELS[phaseKey] || phaseKey;
  const sections: Array<{ heading: string; items?: string[] }> = [
    { heading: "Skills to improve", items: phase.skills_to_improve },
    { heading: "Tasks / projects", items: phase.tasks_or_projects },
    { heading: "Learning resources", items: phase.learning_resources },
    { heading: "Measurable outcomes / KPIs", items: phase.measurable_outcomes_or_kpis },
    { heading: "Manager check-ins", items: phase.manager_check_in_points },
    { heading: "Evidence to collect", items: phase.evidence_to_collect },
  ];
  const firstSkill = (phase.skills_to_improve ?? []).slice(0, 2).join(" · ");
  return (
    <div className="rounded-md border border-border/40 bg-muted/10">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full px-3 py-2 text-left flex items-start gap-2 hover:bg-muted/20 transition-colors"
      >
        <span className="text-[11px] uppercase tracking-widest text-primary shrink-0 mt-0.5">
          {open ? "▾" : "▸"}
        </span>
        <span className="flex-1">
          <span className="block text-[11px] uppercase tracking-widest text-primary">{label}</span>
          {!open && firstSkill && (
            <span className="block text-[11px] text-foreground/80 mt-0.5">{firstSkill}</span>
          )}
        </span>
      </button>
      {open && (
        <div className="px-3 pb-3 space-y-2">
          {sections.map((s) =>
            s.items && s.items.length ? (
              <div key={s.heading}>
                <p className="text-[10px] uppercase tracking-widest text-muted-foreground">{s.heading}</p>
                <ul className="ml-3 list-disc text-[11px] text-foreground/90 space-y-0.5 mt-0.5">
                  {s.items.map((it, i) => <li key={i}>{renderPlanItem(it)}</li>)}
                </ul>
              </div>
            ) : null,
          )}
        </div>
      )}
    </div>
  );
}

function PlanWindows({ body }: { body: Record<string, unknown> }) {
  const phasesRaw = body.phases as Record<string, PhaseFields> | undefined;
  if (phasesRaw && typeof phasesRaw === "object" && !Array.isArray(phasesRaw)) {
    const order = [
      ...PHASE_ORDER.filter((k) => phasesRaw[k]),
      ...Object.keys(phasesRaw).filter((k) => !PHASE_ORDER.includes(k)),
    ];
    if (order.length) {
      return (
        <div className="space-y-2">
          <p className="text-[10px] uppercase tracking-widest text-muted-foreground">
            {order.length * 3}-month plan · {order.length} phase{order.length === 1 ? "" : "s"}
          </p>
          {order.map((k) => <PhaseCard key={k} phaseKey={k} phase={phasesRaw[k] ?? {}} />)}
        </div>
      );
    }
  }
  // Legacy 30/60/90 fallback.
  const legacy = ["first_30_days", "first_60_days", "first_90_days"];
  const items = legacy
    .map((key) => ({ key, value: body[key] as Record<string, unknown> | undefined }))
    .filter((w) => w.value && Object.keys(w.value).length);
  if (!items.length) return null;
  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
      {items.map((w) => (
        <div key={w.key} className="rounded-md border border-border/40 bg-muted/10 p-2">
          <p className="text-[10px] uppercase tracking-widest text-primary">{w.key.replace(/_/g, " ")}</p>
          <p className="text-[11px] text-foreground/90 mt-1">
            {(((w.value?.focus as string[] | undefined) ?? []).slice(0, 3)).join(" · ") || "—"}
          </p>
        </div>
      ))}
    </div>
  );
}

export function DevelopmentPlanSection({
  packetId,
  orgId,
  candidateId,
  jobId,
  canGenerate,
}: {
  packetId: string;
  orgId: string;
  candidateId: string;
  jobId: string;
  canGenerate: boolean;
}) {
  const { data, refetch } = useDecisionReport(packetId, orgId);
  const generatePlan = useGenerateDevelopmentPlan();
  const approvePlan = useApprovePlan();
  const revisePlan = useRevisePlan();
  const sendFeedback = useSendPlanFeedback();
  const updateMessage = useUpdateCandidateFeedback();

  const plan = data?.development_plan ?? null;
  const [editing, setEditing] = useState(false);
  const [draftMessage, setDraftMessage] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const triedRef = useRef(false);

  const canRun = canGenerate && Boolean(jobId);

  // Auto-generate once the decision is recorded and no plan exists yet.
  useEffect(() => {
    if (canRun && !plan && !generatePlan.isPending && !triedRef.current) {
      triedRef.current = true;
      generatePlan.mutate(
        { orgId, candidateId, jobId, decisionId: packetId },
        { onError: (e) => setActionError(e instanceof Error ? e.message : "Could not generate the development plan.") },
      );
    }
  }, [canRun, plan, generatePlan, orgId, candidateId, jobId, packetId]);

  const onGenerate = () => {
    setActionError(null);
    triedRef.current = true;
    generatePlan.mutate(
      { orgId, candidateId, jobId, decisionId: packetId },
      {
        onSuccess: () => void refetch(),
        onError: (e) => setActionError(e instanceof Error ? e.message : "Could not generate the development plan."),
      },
    );
  };

  const body = (plan?.plan_json ?? {}) as Record<string, unknown>;
  const status = (body.status as string) ?? "draft_generated";
  const planType = String((body.plan_type as string) ?? plan?.plan_type ?? "");
  const isAccepted = /accept|growth/i.test(planType);
  const isRejected = /reject|improvement/i.test(planType);
  const summary = (body.executive_summary as string) || (body.summary as string) || plan?.summary || "";
  const candidateMessage =
    (body.candidate_facing_message as string | undefined) ??
    (body.candidate_facing_feedback_message as string | undefined) ?? "";
  const isWorking =
    approvePlan.isPending || revisePlan.isPending || sendFeedback.isPending || updateMessage.isPending;

  if (!plan) {
    return (
      <div className="space-y-2">
        {generatePlan.isPending ? (
          <p className="flex items-center gap-2 text-[13px] text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Building the detailed development plan…
          </p>
        ) : (
          <>
            <p className="text-[13px] text-muted-foreground">
              {canRun
                ? "No development plan yet."
                : "Confirm the hiring decision below first — a detailed, decision-appropriate plan is then generated automatically (internal-growth if hired, reapplication-readiness if rejected)."}
            </p>
            <Button
              size="sm"
              variant="outline"
              className="gap-1.5 text-xs"
              onClick={onGenerate}
              disabled={!canRun || generatePlan.isPending}
              title={!canRun ? "Confirm the hiring decision below first" : undefined}
            >
              <Sparkles className="h-3 w-3" /> Generate Plan
            </Button>
          </>
        )}
        {actionError && <p className="text-xs text-rose-400">{actionError}</p>}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge
          variant="outline"
          className={
            "text-[10px] " +
            (isAccepted
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
              : isRejected
                ? "border-amber-500/30 bg-amber-500/10 text-amber-400"
                : "border-muted/30 text-muted-foreground")
          }
        >
          {isAccepted
            ? "Internal growth plan · level up & excel in this role"
            : isRejected
              ? "12-month plan · get the role you were rejected from"
              : planType.replace(/_/g, " ") || "Development plan"}
        </Badge>
        <Badge variant="outline" className="text-[10px] text-muted-foreground">{status.replace(/_/g, " ")}</Badge>
      </div>

      {summary && <p className="text-[13px] text-foreground/90 leading-relaxed">{summary}</p>}

      <PlanWindows body={body} />

      {/* Candidate-facing message */}
      <div className="rounded-md border border-border/40 bg-muted/10 p-3 space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-[11px] uppercase tracking-widest text-muted-foreground">Candidate-facing message</p>
          {!editing ? (
            <Button variant="ghost" size="sm" className="text-xs" onClick={() => { setDraftMessage(candidateMessage); setEditing(true); }}>
              Edit
            </Button>
          ) : (
            <div className="flex gap-2">
              <Button variant="ghost" size="sm" className="text-xs" onClick={() => setEditing(false)}>Cancel</Button>
              <Button
                size="sm"
                className="text-xs"
                disabled={isWorking}
                onClick={() =>
                  updateMessage
                    .mutateAsync({ planId: plan.id, orgId, candidateFacingMessage: draftMessage })
                    .then(() => { setEditing(false); void refetch(); })
                    .catch((e) => setActionError(e instanceof Error ? e.message : "Could not save message."))
                }
              >
                {isWorking ? <Loader2 className="h-3 w-3 animate-spin" /> : null} Save
              </Button>
            </div>
          )}
        </div>
        {editing ? (
          <Textarea rows={6} value={draftMessage} onChange={(e) => setDraftMessage(e.target.value)} />
        ) : (
          <p className="text-[12px] whitespace-pre-wrap text-foreground/90">{candidateMessage || "—"}</p>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          className="gap-1.5 text-xs"
          disabled={isWorking || status === "approved" || status === "sent"}
          onClick={() =>
            approvePlan
              .mutateAsync({ planId: plan.id, orgId })
              .then(() => sendFeedback.mutateAsync({ planId: plan.id, orgId }))
              .then(() => refetch())
              .catch((e) => setActionError(e instanceof Error ? e.message : "Could not approve / send."))
          }
        >
          <CheckCircle2 className="h-3 w-3" /> Approve & send to candidate
        </Button>
        <Button
          size="sm"
          variant="ghost"
          className="gap-1.5 text-xs"
          disabled={isWorking}
          onClick={() =>
            revisePlan
              .mutateAsync({ planId: plan.id, orgId })
              .then(() => refetch())
              .catch((e) => setActionError(e instanceof Error ? e.message : "Could not request revision."))
          }
        >
          <RefreshCcw className="h-3 w-3" /> Request revision
        </Button>
        {(status === "approved" || status === "sent") && (
          <Button
            size="sm"
            variant="ghost"
            className="gap-1.5 text-xs"
            disabled={isWorking}
            onClick={() =>
              sendFeedback
                .mutateAsync({ planId: plan.id, orgId })
                .then(() => refetch())
                .catch((e) => setActionError(e instanceof Error ? e.message : "Could not resend."))
            }
          >
            <Send className="h-3 w-3" /> Resend
          </Button>
        )}
      </div>
      {status === "sent" && (
        <p className="text-[11px] text-emerald-300">
          <CheckCircle2 className="inline h-3 w-3 mr-1" /> Development plan sent to candidate.
        </p>
      )}
      {actionError && <p className="text-xs text-rose-400">{actionError}</p>}
    </div>
  );
}

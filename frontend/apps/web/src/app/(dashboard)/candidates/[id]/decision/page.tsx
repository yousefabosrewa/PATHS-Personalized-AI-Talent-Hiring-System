"use client";

import { use, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import Link from "next/link";
import {
  ArrowLeft, Brain, CheckCircle2, XCircle, AlertCircle,
  ChevronDown, ChevronUp, Sparkles, Mail, Send,
  ThumbsUp, ThumbsDown, FileText, Loader2, RefreshCw,
  TrendingUp, Shield, User, Download,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils/cn";
import { useAuthStore } from "@/lib/stores/auth.store";
import {
  useDSSLatestPacket,
  useGenerateDSSPacket,
  useHrDecision,
  useGenerateDSSEmail,
  useDSSEmail,
  useApproveDSSEmail,
  useSendDSSEmail,
  useApplications,
  useDecisionReport,
} from "@/lib/hooks";
import { dssApi } from "@/lib/api";
import { IdssPanel } from "@/components/idss/idss-panel";
import { DevelopmentPlanSection } from "@/components/decision/development-plan-section";

// PATHS.md §4 — render confidence reliably from any backend shape.
// 0.82 → "82%", 82 → "82%", null/undefined → "Not available".
function formatConfidence(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "Not available";
  const pct = v <= 1 ? v * 100 : v;
  return `${Math.round(Math.min(100, Math.max(0, pct)))}%`;
}

// Strengths/gaps are usually strings but the agent can return objects
// ({point, evidence} or {title,...}). Coerce to text so React never gets a
// raw object child.
function textOf(it: unknown): string {
  if (it == null) return "";
  if (typeof it === "string" || typeof it === "number") return String(it);
  if (typeof it === "object") {
    const o = it as Record<string, unknown>;
    const main = (o.point ?? o.title ?? o.text ?? o.name ?? o.reason ?? "") as string;
    if (main) return main;
    try { return JSON.stringify(it); } catch { return String(it); }
  }
  return String(it);
}

// The email + development plan can only be generated AFTER a hiring decision
// is recorded (backend returns 400 "HR decision required" otherwise). Turn
// that into a clear instruction instead of a silent failure.
function friendlyDssError(e: unknown, fallback: string): string {
  const msg = e instanceof Error ? e.message : "";
  if (/hr decision required/i.test(msg)) {
    return "Record the hiring decision first — click Confirm Hire or Confirm Reject below.";
  }
  return msg || fallback;
}

// ── Helpers ─────────────────────────────────────────────────────────────────

const RECOMMENDATION_CONFIG = {
  hire: {
    label: "Recommend Hire",
    color: "text-emerald-400",
    border: "border-emerald-500/30 bg-emerald-500/10",
    icon: CheckCircle2,
    glow: "shadow-emerald-500/20",
  },
  reject: {
    label: "Recommend Reject",
    color: "text-rose-400",
    border: "border-rose-500/30 bg-rose-500/10",
    icon: XCircle,
    glow: "shadow-rose-500/20",
  },
  consider: {
    label: "Consider (Manual Review)",
    color: "text-amber-400",
    border: "border-amber-500/30 bg-amber-500/10",
    icon: AlertCircle,
    glow: "shadow-amber-500/20",
  },
} as const;

/**
 * Score ring that always renders the value as ``X / 100``.
 *
 * The backend sometimes hands us a 0..1 ratio (legacy ``final_journey_score``)
 * and sometimes a 0..100 absolute (``idss_v2.final_score``). We detect the
 * scale at render time: anything ``<= 1`` is treated as a ratio and scaled
 * up; anything ``> 1`` is treated as already on the 0..100 scale. This
 * matches the brief's "Final Score: 82 / 100" requirement and rules out the
 * "Final Score: 4100 / 5000" mistake.
 */
function ScoreRing({ score }: { score: number }) {
  const numeric = Number.isFinite(score) ? score : 0;
  const pct = Math.max(
    0,
    Math.min(100, Math.round(numeric > 1 ? numeric : numeric * 100)),
  );
  const color = pct >= 75 ? "#34d399" : pct >= 50 ? "#fbbf24" : "#f87171";
  const r = 44;
  const circ = 2 * Math.PI * r;
  const dash = circ * (pct / 100);

  return (
    <div className="relative flex h-28 w-28 items-center justify-center">
      <svg className="absolute inset-0 -rotate-90" width="112" height="112">
        <circle cx="56" cy="56" r={r} fill="none" stroke="currentColor" className="text-muted/30" strokeWidth="8" />
        <circle
          cx="56" cy="56" r={r} fill="none" stroke={color} strokeWidth="8"
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
          style={{ transition: "stroke-dasharray 1s ease" }}
        />
      </svg>
      <div className="text-center">
        <p className="font-heading text-2xl font-bold text-foreground">{pct}</p>
        <p className="text-[9px] text-muted-foreground uppercase tracking-wide">/ 100</p>
        <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Score</p>
      </div>
    </div>
  );
}

function CriteriaBreakdown({ criteria }: { criteria: Record<string, unknown> }) {
  const entries = Object.entries(criteria).filter(([, v]) => typeof v === "number" || (v && typeof (v as Record<string, unknown>).score === "number"));

  if (entries.length === 0) {
    return <p className="text-xs text-muted-foreground">No criteria data available.</p>;
  }

  return (
    <div className="space-y-3">
      {entries.map(([key, val]) => {
        const score = typeof val === "number" ? val : (val as Record<string, unknown>).score as number;
        const pct = Math.round(score * 100);
        const barColor = pct >= 75 ? "bg-emerald-500" : pct >= 50 ? "bg-amber-500" : "bg-rose-500";
        const label = key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
        return (
          <div key={key} className="space-y-1">
            <div className="flex justify-between text-[12px]">
              <span className="font-medium text-muted-foreground">{label}</span>
              <span className="font-mono font-bold text-foreground">{pct}%</span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-muted/40 overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${pct}%` }}
                transition={{ duration: 0.7, ease: "easeOut" }}
                className={cn("h-full rounded-full", barColor)}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function DecisionSupportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: candidateId } = use(params);
  const { user } = useAuthStore();
  const orgId = user?.orgId ?? "";
  const qc = useQueryClient();
  const [sending, setSending] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);

  const [hrNotes, setHrNotes] = useState("");
  const [overrideReason, setOverrideReason] = useState("");
  const [showOverride, setShowOverride] = useState(false);
  const [emailBody, setEmailBody] = useState("");
  const [emailSubject, setEmailSubject] = useState("");
  const [emailEditing, setEmailEditing] = useState(false);

  // Get candidate's application
  const { data: allApps = [] } = useApplications();
  const candidateApp = allApps.find((a) => a.candidateId === candidateId);
  const applicationId = candidateApp?.id ?? "";
  const jobId = candidateApp?.jobId ?? "";

  // DSS queries
  const { data: packet, isLoading: packetLoading, error: packetError } =
    useDSSLatestPacket(applicationId, orgId);

  const packetId = (packet?.id ?? packet?.packet_id) ?? "";

  const { data: dssEmail, isLoading: emailLoading } = useDSSEmail(packetId, orgId, !!packetId);
  const { data: decisionReport } = useDecisionReport(packetId, orgId, !!packetId);

  // The page becomes a STATIC, read-only record once the decision email has
  // been sent (user's choice: "lock after email + plan sent"). Only the
  // development-plan progress stays interactive after that. The recorded HR
  // decision + notes come back from the report so a reload still shows them.
  const recordedDecision = decisionReport?.hr_decision ?? null;
  // The decision itself is fixed the moment it is confirmed; the whole page
  // locks (read-only) only after the email has been sent.
  const decisionFixed = !!recordedDecision?.final_hr_decision;
  const locked = dssEmail?.status === "sent";

  // Mutations
  const generatePacket = useGenerateDSSPacket();
  const hrDecision = useHrDecision();
  const generateEmail = useGenerateDSSEmail();
  const approveEmail = useApproveDSSEmail();
  const sendEmail = useSendDSSEmail();

  // Recommendation config
  const recKey = (packet?.recommendation ?? "consider") as keyof typeof RECOMMENDATION_CONFIG;
  const rec = RECOMMENDATION_CONFIG[recKey] ?? RECOMMENDATION_CONFIG.consider;
  const RecIcon = rec.icon;

  const handleGenerate = () => {
    if (!applicationId || !orgId) return;
    generatePacket.mutate({
      orgId,
      applicationId,
      candidateId,
      jobId,
    });
  };

  const handleHireDecision = (decision: "hire" | "reject") => {
    if (!packetId || !orgId) return;
    hrDecision.mutate(
      {
        packetId,
        orgId,
        finalDecision: decision,
        hrNotes: hrNotes || undefined,
        overrideReason: showOverride ? overrideReason : undefined,
      },
      {
        // Recording the decision unlocks the email + development plan on the
        // backend, so we chain BOTH automatically — the manager clicks once
        // and the matching mail and the dev plan both appear.
        onSuccess: (data) => {
          const emailType = decision === "hire" ? "acceptance" : "rejection";
          generateEmail.mutate(
            { packetId, orgId, emailType },
            { onError: (e) => toast.error(friendlyDssError(e, "Could not generate the email.")) },
          );
          // The development plan auto-generates inside DevelopmentPlanSection
          // once the decision is recorded (decisionMade flips true).
          // PATHS.md §8 — final decision updates the candidate pipeline.
          qc.invalidateQueries({ queryKey: ["applications"] });
          qc.invalidateQueries({ queryKey: ["candidates"] });
          qc.invalidateQueries({ queryKey: ["candidate", candidateId] });
          const label =
            (data as { pipeline_status_label?: string } | undefined)?.pipeline_status_label
            ?? (decision === "hire" ? "Accepted Candidate" : "Rejected Candidate");
          toast.success(`Candidate marked as ${label}. Drafting the email and development plan…`);
        },
        onError: (e) => toast.error(friendlyDssError(e, "Could not record the decision.")),
      },
    );
  };

  const handleGenerateEmail = (type: "acceptance" | "rejection") => {
    if (!packetId || !orgId) return;
    generateEmail.mutate(
      { packetId, orgId, emailType: type },
      { onError: (e) => toast.error(friendlyDssError(e, "Could not generate the email.")) },
    );
  };

  const handleApproveEmail = () => {
    if (!packetId || !orgId) return;
    approveEmail.mutate({ packetId, orgId });
  };

  // Download the decision report PDF. Must fetch as an authenticated blob —
  // a plain link 404s (hits the frontend origin) and sends no auth token.
  const handleDownloadReport = async () => {
    if (!packetId || !orgId) return;
    setPdfLoading(true);
    try {
      const blob = await dssApi.downloadReportPdf(packetId, orgId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const name = (decisionReport?.candidate?.full_name ?? "candidate").replace(/\s+/g, "_");
      a.download = `PATHS-Decision-Report-${name}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not download the report PDF.");
    } finally {
      setPdfLoading(false);
    }
  };

  // PATHS.md §5 — Send must persist the exact (possibly edited) email shown
  // in the UI, ensure it's approved, then actually send it via the backend.
  const handleSendEmail = async () => {
    if (!packetId || !orgId) return;
    setSending(true);
    try {
      // 1. Save the current subject/body so the sent email matches the UI.
      await dssApi.patchEmail(packetId, orgId, {
        subject: emailSubject,
        body: emailBody,
      });
      // 2. Approve if not already approved (send requires approved status).
      if (dssEmail?.status !== "approved") {
        await dssApi.approveEmail(packetId, orgId);
      }
      // 3. Send to the candidate email linked to the application.
      await sendEmail.mutateAsync({ packetId, orgId });
      toast.success("Email sent successfully.");
    } catch (e) {
      toast.error(
        e instanceof Error
          ? e.message
          : "Failed to send email. Please check the candidate email and mail provider configuration.",
      );
    } finally {
      setSending(false);
    }
  };

  // Sync email body from query data
  if (dssEmail && !emailEditing) {
    if (dssEmail.subject !== emailSubject) setEmailSubject(dssEmail.subject);
    if (dssEmail.body !== emailBody) setEmailBody(dssEmail.body);
  }

  const packetJson = packet?.packet_json ?? {};
  const criteria = (packetJson as Record<string, unknown>).criteria_breakdown as Record<string, unknown> | undefined;
  const strengths = (packetJson as Record<string, unknown>).strengths as string[] | undefined;
  const gaps = (packetJson as Record<string, unknown>).gaps as string[] | undefined;

  // The email + development plan can only be generated AFTER a hiring decision
  // is recorded. Treat the decision as made once we've confirmed one this
  // session, or once a decision email already exists (so reloads behave too).
  const decisionMade = hrDecision.isSuccess || !!dssEmail;

  return (
    <div className="h-full overflow-y-auto">
      {/* Header */}
      <div className="sticky top-0 z-10 border-b border-border/50 bg-background/80 backdrop-blur-sm px-6 py-3 flex items-center gap-3">
        <Link href={`/candidates/${candidateId}`}>
          <Button variant="ghost" size="sm" className="gap-1.5 text-muted-foreground -ml-2">
            <ArrowLeft className="h-3.5 w-3.5" /> Back to Profile
          </Button>
        </Link>
        <div className="h-4 w-px bg-border/60" />
        <div className="flex items-center gap-2">
          <Brain className="h-4 w-4 text-primary" />
          <h1 className="font-heading text-sm font-bold text-foreground">Decision Support</h1>
        </div>
        <Badge variant="outline" className="ml-auto border-primary/30 bg-primary/10 text-primary text-[10px]">
          AI-Assisted · Hiring Manager Final Say
        </Badge>
      </div>

      {/* PATHS.md §3 — flex + gap + order so the Hiring Manager Decision
          renders above Mail Feedback without moving large JSX blocks. */}
      <div className="p-6 max-w-4xl flex flex-col gap-6">

        {/* Generate button (no packet yet) */}
        {!packetLoading && !packet && !packetError && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass gradient-border rounded-2xl p-8 text-center"
          >
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 ring-1 ring-primary/20">
              <Sparkles className="h-6 w-6 text-primary" />
            </div>
            <h2 className="font-heading text-lg font-bold text-foreground mb-2">Generate AI Decision Packet</h2>
            <p className="text-sm text-muted-foreground mb-6 max-w-md mx-auto">
              PATHS will analyze the full candidate journey — CV, scoring, interview, compliance — and generate an explainable recommendation packet.
            </p>
            <Button
              className="glow-blue gap-2"
              onClick={handleGenerate}
              disabled={generatePacket.isPending || !applicationId}
            >
              {generatePacket.isPending
                ? <><Loader2 className="h-4 w-4 animate-spin" /> Generating…</>
                : <><Sparkles className="h-4 w-4" /> Generate Packet</>}
            </Button>
            {!applicationId && (
              <p className="mt-3 text-xs text-rose-400">No application found for this candidate.</p>
            )}
          </motion.div>
        )}

        {/* Loading state */}
        {packetLoading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
          </div>
        )}

        {/* Error (no packet, 404 after app load) */}
        {packetError && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="glass gradient-border rounded-2xl p-8 text-center"
          >
            <AlertCircle className="mx-auto mb-3 h-10 w-10 text-amber-400" />
            <p className="text-sm text-muted-foreground mb-4">No decision packet found for this application yet.</p>
            <Button className="glow-blue gap-2" onClick={handleGenerate} disabled={generatePacket.isPending || !applicationId}>
              {generatePacket.isPending
                ? <><Loader2 className="h-4 w-4 animate-spin" /> Generating…</>
                : <><Sparkles className="h-4 w-4" /> Generate Packet</>}
            </Button>
          </motion.div>
        )}

        {/* Packet loaded */}
        {packet && (
          <>
            {locked && (
              <div className="order-none flex items-center gap-2 rounded-xl border border-primary/30 bg-primary/10 px-4 py-3 text-[12px] text-primary">
                <CheckCircle2 className="h-4 w-4 shrink-0" />
                This decision is finalized and the email has been sent — the page is now a
                read-only record. Only the candidate&apos;s development-plan progress remains editable.
              </div>
            )}
            {/* ── Mail Feedback (brief §4) ────────────────────────────
                Per VM.md the decision email block must appear BEFORE
                the scoring/rubric area and be labelled "Mail Feedback".
                The HR Hire/Reject buttons further down auto-generate
                the matching mail into this section. */}
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 }}
              className="order-6 glass gradient-border rounded-2xl p-6"
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-heading text-sm font-bold text-foreground flex items-center gap-2">
                  <Mail className="h-4 w-4 text-primary" /> Decision Email
                </h3>
                {generateEmail.isPending && (
                  <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                    <Loader2 className="h-3 w-3 animate-spin" /> Drafting…
                  </span>
                )}
              </div>

              {dssEmail ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <Badge
                      variant="outline"
                      className={cn("text-[10px]",
                        dssEmail.status === "approved"
                          ? "border-emerald-500/30 text-emerald-400"
                          : dssEmail.status === "sent"
                          ? "border-primary/30 text-primary"
                          : "border-amber-500/30 text-amber-400"
                      )}
                    >
                      {dssEmail.status}
                    </Badge>
                    {dssEmail.email_type && (
                      <Badge variant="outline" className="text-[10px] border-muted/30 text-muted-foreground">
                        {dssEmail.email_type}
                      </Badge>
                    )}
                  </div>

                  {/* Subject */}
                  <div>
                    <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Subject</label>
                    <input
                      className="mt-1 w-full rounded-lg border border-border/40 bg-muted/20 px-3 py-2 text-[13px] text-foreground focus:outline-none focus:ring-1 focus:ring-primary/40 disabled:opacity-70"
                      value={emailSubject}
                      disabled={locked}
                      onChange={(e) => { setEmailSubject(e.target.value); setEmailEditing(true); }}
                    />
                  </div>

                  {/* Body */}
                  <div>
                    <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Body</label>
                    <textarea
                      rows={8}
                      className="mt-1 w-full rounded-lg border border-border/40 bg-muted/20 px-3 py-2 text-[13px] text-foreground focus:outline-none focus:ring-1 focus:ring-primary/40 resize-y disabled:opacity-70"
                      value={emailBody}
                      disabled={locked}
                      onChange={(e) => { setEmailBody(e.target.value); setEmailEditing(true); }}
                    />
                  </div>

                  {/* Recipient — the email is sent to the candidate address
                      linked to this application; this field is informational. */}
                  <div>
                    <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Recipient</label>
                    <p className="mt-1 text-[12px] text-muted-foreground">
                      Sends to the candidate&apos;s registered email on this application.
                    </p>
                  </div>

                  <div className="flex items-center gap-2 pt-1">
                    <Button
                      size="sm"
                      variant="outline"
                      className="gap-1.5 text-xs"
                      onClick={handleApproveEmail}
                      disabled={approveEmail.isPending || dssEmail.status === "approved" || locked}
                    >
                      {approveEmail.isPending
                        ? <Loader2 className="h-3 w-3 animate-spin" />
                        : <CheckCircle2 className="h-3 w-3 text-emerald-400" />}
                      Approve
                    </Button>
                    <Button
                      size="sm"
                      className="gap-1.5 text-xs glow-blue"
                      onClick={handleSendEmail}
                      disabled={sending || dssEmail.status === "sent"}
                    >
                      {sending
                        ? <Loader2 className="h-3 w-3 animate-spin" />
                        : <Send className="h-3 w-3" />}
                      {dssEmail.status === "sent" ? "Sent" : "Send"}
                    </Button>
                    {dssEmail.status === "sent" && (
                      <span className="text-[11px] text-emerald-400">Email sent to candidate.</span>
                    )}
                  </div>
                </div>
              ) : (
                <p className="text-[13px] text-muted-foreground">
                  Click <strong>Confirm Hire</strong> or <strong>Confirm Reject</strong> in
                  “Hiring Manager Final Decision” below — the matching email <em>and</em> the
                  development plan are drafted automatically. (The Acceptance / Rejection
                  buttons above re-draft the email after a decision; the draft is fully
                  editable before sending.)
                </p>
              )}
            </motion.div>

            {/* IDSS v2 panel (rubric + full explanation + per-stage breakdown + PDF) */}
            {packetId && (
              <div className="order-2">
                <IdssPanel packetId={packetId} orgId={orgId} />
              </div>
            )}
            {/* Recommendation card (evaluation summary — first per §3) */}
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              className={cn("order-1 glass rounded-2xl p-6 border", rec.border)}
            >
              <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
                <ScoreRing score={packet.final_journey_score ?? 0} />
                <div className="flex-1 space-y-2">
                  <div className="flex items-center gap-2">
                    <RecIcon className={cn("h-5 w-5", rec.color)} />
                    <h2 className={cn("font-heading text-xl font-bold", rec.color)}>{rec.label}</h2>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="outline" className="border-muted/30 text-muted-foreground text-[10px]">
                      Confidence: {formatConfidence(packet.confidence)}
                    </Badge>
                    {packet.compliance_status && (
                      <Badge
                        variant="outline"
                        className={cn("text-[10px]",
                          packet.compliance_status === "pass"
                            ? "border-emerald-500/30 text-emerald-400"
                            : "border-rose-500/30 text-rose-400"
                        )}
                      >
                        <Shield className="h-3 w-3 mr-1" />
                        Compliance: {packet.compliance_status}
                      </Badge>
                    )}
                    {packet.human_review_required && (
                      <Badge variant="outline" className="border-amber-500/30 text-amber-400 text-[10px]">
                        Human Review Required
                      </Badge>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="gap-1.5 text-xs text-muted-foreground"
                    onClick={handleGenerate}
                    disabled={generatePacket.isPending}
                  >
                    <RefreshCw className={cn("h-3 w-3", generatePacket.isPending && "animate-spin")} />
                    Regenerate
                  </Button>
                </div>
              </div>
            </motion.div>

            {/* Criteria breakdown */}
            {criteria && (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                className="order-3 glass gradient-border rounded-2xl p-6"
              >
                <h3 className="font-heading text-sm font-bold text-foreground mb-4 flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-primary" /> Criteria Breakdown
                </h3>
                <CriteriaBreakdown criteria={criteria} />
              </motion.div>
            )}

            {/* Strengths & Gaps */}
            {(strengths?.length || gaps?.length) && (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.15 }}
                className="order-4 grid grid-cols-1 gap-4 sm:grid-cols-2"
              >
                {strengths?.length ? (
                  <div className="glass gradient-border rounded-2xl p-5">
                    <h4 className="font-heading text-xs font-bold text-emerald-400 uppercase tracking-wider mb-3">Strengths</h4>
                    <ul className="space-y-2">
                      {strengths.map((s, i) => (
                        <li key={i} className="flex items-start gap-2 text-[13px] text-muted-foreground">
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 mt-0.5 shrink-0" />
                          {textOf(s)}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {gaps?.length ? (
                  <div className="glass gradient-border rounded-2xl p-5">
                    <h4 className="font-heading text-xs font-bold text-rose-400 uppercase tracking-wider mb-3">Gaps</h4>
                    <ul className="space-y-2">
                      {gaps.map((g, i) => (
                        <li key={i} className="flex items-start gap-2 text-[13px] text-muted-foreground">
                          <XCircle className="h-3.5 w-3.5 text-rose-400 mt-0.5 shrink-0" />
                          {textOf(g)}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </motion.div>
            )}

            {/* Development Plan */}
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="order-7 glass gradient-border rounded-2xl p-6"
            >
              <h3 className="font-heading text-sm font-bold text-foreground flex items-center gap-2 mb-4">
                <FileText className="h-4 w-4 text-primary" /> Development Plan
              </h3>
              <DevelopmentPlanSection
                packetId={packetId}
                orgId={orgId}
                candidateId={candidateId}
                jobId={candidateApp?.jobId ?? ""}
                canGenerate={decisionMade}
              />
            </motion.div>

            {/* Hiring Manager Final Decision (renders before Mail Feedback — §3) */}
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="order-5 glass gradient-border rounded-2xl p-6"
            >
              <h3 className="font-heading text-sm font-bold text-foreground flex items-center gap-2 mb-4">
                <User className="h-4 w-4 text-primary" /> Hiring Manager Final Decision
              </h3>

              {decisionFixed ? (
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge
                      variant="outline"
                      className={cn(
                        "text-[11px]",
                        recordedDecision?.final_hr_decision === "accepted"
                          ? "border-emerald-500/40 text-emerald-400"
                          : "border-rose-500/40 text-rose-400",
                      )}
                    >
                      {recordedDecision?.final_hr_decision === "accepted" ? "Hired" : "Rejected"}
                    </Badge>
                    <span className="text-[11px] text-muted-foreground">
                      Decision recorded
                      {recordedDecision?.decided_at
                        ? ` · ${new Date(recordedDecision.decided_at).toLocaleDateString()}`
                        : ""}
                    </span>
                  </div>
                  {(recordedDecision?.hr_notes || hrNotes) && (
                    <div className="rounded-lg border border-border/40 bg-muted/20 px-3 py-2">
                      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Notes</p>
                      <p className="mt-0.5 whitespace-pre-wrap text-[13px] text-foreground/90">
                        {recordedDecision?.hr_notes || hrNotes}
                      </p>
                    </div>
                  )}
                  <p className="text-[12px] text-muted-foreground">
                    {locked
                      ? "This decision is finalized and the email has been sent — the page is now a read-only record. Only the candidate's development-plan progress stays interactive."
                      : "Decision is fixed. The matching email and development plan are below; the page locks once you send the email."}
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  <div>
                    <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Notes (saved with your decision)</label>
                    <textarea
                      rows={3}
                      placeholder="Add your review notes here…"
                      value={hrNotes}
                      onChange={(e) => setHrNotes(e.target.value)}
                      className="mt-1 w-full rounded-lg border border-border/40 bg-muted/20 px-3 py-2 text-[13px] text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/40 resize-none"
                    />
                  </div>

                  <button
                    onClick={() => setShowOverride(!showOverride)}
                    className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {showOverride ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                    Override AI recommendation
                  </button>

                  <AnimatePresence>
                    {showOverride && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                      >
                        <textarea
                          rows={2}
                          placeholder="Reason for overriding AI recommendation…"
                          value={overrideReason}
                          onChange={(e) => setOverrideReason(e.target.value)}
                          className="w-full rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-[13px] text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-amber-400/40 resize-none"
                        />
                      </motion.div>
                    )}
                  </AnimatePresence>

                  <div className="flex items-center gap-3">
                    <Button
                      className="flex-1 gap-2 bg-emerald-600 hover:bg-emerald-500 text-white"
                      onClick={() => handleHireDecision("hire")}
                      disabled={hrDecision.isPending}
                    >
                      {hrDecision.isPending
                        ? <Loader2 className="h-4 w-4 animate-spin" />
                        : <ThumbsUp className="h-4 w-4" />}
                      Confirm Hire
                    </Button>
                    <Button
                      className="flex-1 gap-2 bg-rose-700 hover:bg-rose-600 text-white"
                      onClick={() => handleHireDecision("reject")}
                      disabled={hrDecision.isPending}
                    >
                      {hrDecision.isPending
                        ? <Loader2 className="h-4 w-4 animate-spin" />
                        : <ThumbsDown className="h-4 w-4" />}
                      Confirm Reject
                    </Button>
                  </div>
                  <p className="text-center text-[11px] text-muted-foreground">
                    Confirming records your decision and instantly drafts the matching email and a
                    development plan below (accept → 18 months · reject → 12 months).
                  </p>
                </div>
              )}
            </motion.div>

            {/* Download report — bottom of the page, after the development plan.
                Fetches an authenticated PDF blob (a plain link 404s). */}
            <div className="order-8 flex flex-col items-center gap-1 pt-2">
              <Button
                onClick={handleDownloadReport}
                disabled={pdfLoading}
                className="gap-2 glow-blue"
              >
                {pdfLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Download className="h-4 w-4" />
                )}
                Download report (PDF)
              </Button>
              <p className="text-[11px] text-muted-foreground">
                Full report — score, rubric, per-stage breakdown, decision, notes &amp; development plan.
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

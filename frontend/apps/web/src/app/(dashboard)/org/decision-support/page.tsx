"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  FileText, Loader2, Scale, CheckCircle2, XCircle,
  Mail, BookOpen, FileBarChart, Send,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils/cn";
import { useAuthStore } from "@/lib/stores/auth.store";
import {
  useGenerateDSSPacket, useDSSPacket, useDSSLatestPacket,
  useDSSDevPlan, useDSSEmail, useDecisionReport,
  useHrDecision, useGenerateDevPlan, useGenerateDSSEmail,
  useApproveDSSEmail, useSendDSSEmail,
} from "@/lib/hooks";

const decisionColors: Record<string, string> = {
  accept: "text-emerald-400",
  reject: "text-red-400",
  strong_accept: "text-emerald-300",
  weak_accept: "text-yellow-400",
  weak_reject: "text-orange-400",
  hold: "text-blue-400",
};

function PacketOverview({
  packet,
  packetId,
  orgId,
}: {
  packet: { recommendation: string | null; final_journey_score: number | null; confidence?: number | null; compliance_status?: string | null; human_review_required?: boolean };
  packetId: string;
  orgId: string;
}) {
  const hrDecision = useHrDecision();
  const [hrDecisionValue, setHrDecisionValue] = useState("");
  const [hrNotes, setHrNotes] = useState("");

  const { data: devPlan } = useDSSDevPlan(packetId, orgId);
  const generateDevPlan = useGenerateDevPlan();
  const { data: emailData } = useDSSEmail(packetId, orgId);
  const generateEmail = useGenerateDSSEmail();
  const approveEmail = useApproveDSSEmail();
  const sendEmail = useSendDSSEmail();
  const { data: report } = useDecisionReport(packetId, orgId, false);
  const reportPdfUrl = `/api/v1/decision-support/${packetId}/report/pdf?org_id=${orgId}`;

  const handleHrDecision = () => {
    if (!hrDecisionValue) return;
    hrDecision.mutate({
      packetId, orgId,
      finalDecision: hrDecisionValue,
      hrNotes: hrNotes || undefined,
    });
  };

  const complianceColor: Record<string, string> = {
    pass: "text-emerald-400",
    warning: "text-amber-400",
    fail: "text-red-400",
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="glass rounded-xl p-4 space-y-1">
          <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Recommendation</p>
          <p className={cn("text-lg font-bold", decisionColors[packet.recommendation?.toLowerCase() ?? ""] ?? "text-foreground")}>
            {packet.recommendation ?? "n/a"}
          </p>
        </div>
        <div className="glass rounded-xl p-4 space-y-1">
          <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Journey Score</p>
          <p className="text-lg font-bold text-foreground">{packet.final_journey_score ?? "n/a"}</p>
        </div>
        <div className="glass rounded-xl p-4 space-y-1">
          <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Compliance</p>
          <p className={cn("text-lg font-bold", complianceColor[packet.compliance_status?.toLowerCase() ?? ""] ?? "text-muted-foreground")}>
            {packet.compliance_status ?? "n/a"}
          </p>
        </div>
      </div>

      {packet.human_review_required && (
        <div className="glass rounded-xl p-4 border border-amber-500/30 bg-amber-500/5">
          <p className="flex items-center gap-2 text-sm text-amber-400">
            <CheckCircle2 className="h-4 w-4" /> Human review required
          </p>
        </div>
      )}

      {/* HR Decision */}
      <div className="glass gradient-border rounded-2xl p-5 space-y-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">HR Decision</h3>
        <div className="flex flex-wrap gap-2">
          {["accept", "reject", "hold", "strong_accept", "weak_accept", "weak_reject"].map((d) => (
            <button
              key={d}
              onClick={() => setHrDecisionValue(d)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-[12px] font-medium transition-colors border",
                hrDecisionValue === d
                  ? "border-primary/40 bg-primary/15 text-primary"
                  : "border-border/60 text-muted-foreground hover:border-primary/30 hover:text-foreground",
              )}
            >
              {d.replace(/_/g, " ")}
            </button>
          ))}
        </div>
        <textarea
          placeholder="HR notes (optional)"
          value={hrNotes}
          onChange={(e) => setHrNotes(e.target.value)}
          rows={2}
          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
        <Button size="sm" onClick={handleHrDecision} disabled={!hrDecisionValue || hrDecision.isPending}>
          {hrDecision.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <CheckCircle2 className="h-3 w-3" />}
          Submit HR Decision
        </Button>
      </div>

      {/* Email */}
      <div className="glass gradient-border rounded-2xl p-5 space-y-3">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Mail className="h-4 w-4" />
          <h3 className="text-xs font-semibold uppercase tracking-wider">Email</h3>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={() => generateEmail.mutate({ packetId, orgId, emailType: "acceptance" })} disabled={generateEmail.isPending}>
            {generateEmail.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
            Generate Acceptance
          </Button>
          <Button size="sm" variant="outline" onClick={() => generateEmail.mutate({ packetId, orgId, emailType: "rejection" })} disabled={generateEmail.isPending}>
            Generate Rejection
          </Button>
        </div>
        {emailData && (
          <div className="glass rounded-xl p-3 space-y-2">
            <div className="flex items-center justify-between">
              <Badge variant="outline" className="text-[10px]">{emailData.status}</Badge>
              <div className="flex gap-2">
                {emailData.status !== "approved" && (
                  <Button size="sm" variant="ghost" onClick={() => approveEmail.mutate({ packetId, orgId })} disabled={approveEmail.isPending}>
                    <CheckCircle2 className="h-3 w-3" /> Approve
                  </Button>
                )}
                {emailData.status === "approved" && (
                  <Button size="sm" onClick={() => sendEmail.mutate({ packetId, orgId })} disabled={sendEmail.isPending}>
                    <Send className="h-3 w-3" /> Send
                  </Button>
                )}
              </div>
            </div>
            <p className="text-sm font-medium text-foreground">{emailData.subject}</p>
            <p className="text-xs text-muted-foreground whitespace-pre-wrap max-h-32 overflow-y-auto">{emailData.body}</p>
          </div>
        )}
      </div>

      {/* Development Plan */}
      <div className="glass gradient-border rounded-2xl p-5 space-y-3">
        <div className="flex items-center gap-2 text-muted-foreground">
          <BookOpen className="h-4 w-4" />
          <h3 className="text-xs font-semibold uppercase tracking-wider">Development Plan</h3>
        </div>
        <Button size="sm" variant="outline" onClick={() => generateDevPlan.mutate({ packetId, orgId })} disabled={generateDevPlan.isPending}>
          {generateDevPlan.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
          Generate Plan
        </Button>
        {devPlan && (
          <div className="glass rounded-xl p-3 space-y-2">
            {devPlan.summary && <p className="text-sm text-foreground">{devPlan.summary}</p>}
            {devPlan.plan_json && (
              <pre className="text-[10px] text-muted-foreground/70 overflow-x-auto max-h-40">
                {JSON.stringify(devPlan.plan_json, null, 1)}
              </pre>
            )}
          </div>
        )}
      </div>

      {/* Decision Report */}
      {report && (
        <div className="glass rounded-xl p-4 space-y-2">
          <div className="flex items-center gap-2 text-muted-foreground">
            <FileBarChart className="h-4 w-4" />
            <h3 className="text-xs font-semibold uppercase tracking-wider">Decision Report</h3>
          </div>
          <a
            href={reportPdfUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 text-sm text-primary hover:underline"
          >
            <FileText className="h-4 w-4" /> Download PDF
          </a>
        </div>
      )}
    </div>
  );
}

export default function OrgDecisionSupportPage() {
  const { user } = useAuthStore();
  const orgId = user?.orgId ?? "";
  const generateMutation = useGenerateDSSPacket();

  const [applicationId, setApplicationId] = useState("");
  const [candidateId, setCandidateId] = useState("");
  const [jobId, setJobId] = useState("");
  const [latestAppId, setLatestAppId] = useState("");
  const [activePacketId, setActivePacketId] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const { data: latestPacket } = useDSSLatestPacket(latestAppId, orgId);
  const { data: packet, isLoading: packetLoading } = useDSSPacket(activePacketId ?? "", orgId);

  const validGenerateInput = useMemo(
    () => [applicationId, candidateId, jobId].every((x) => /^[0-9a-fA-F-]{36}$/.test(x.trim())),
    [applicationId, candidateId, jobId],
  );

  const resultPacket = packet ?? latestPacket;

  function handleGenerate() {
    if (!orgId) return;
    if (!validGenerateInput) {
      setErr("Fill valid application, candidate, and job UUIDs.");
      return;
    }
    setErr(null);
    setActivePacketId(null);
    generateMutation.mutate(
      {
        orgId,
        applicationId: applicationId.trim(),
        candidateId: candidateId.trim(),
        jobId: jobId.trim(),
      },
      {
        onSuccess: (data) => {
          setActivePacketId(data.packet_id);
        },
        onError: (e) => {
          setErr(e instanceof Error ? e.message : "Request failed");
        },
      },
    );
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mx-auto max-w-3xl space-y-8">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-3"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
            <Scale className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h1 className="font-heading text-xl font-bold tracking-tight text-foreground">
              Decision Support
            </h1>
            <p className="text-sm text-muted-foreground">
              Generate, review, and manage decision packets through the full workflow.
            </p>
          </div>
        </motion.div>

        {err && <p className="text-sm text-red-400">{err}</p>}

        {/* Generate / Lookup */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            className="glass gradient-border rounded-2xl p-6 space-y-4"
          >
            <div className="flex items-center gap-2 text-primary">
              <FileText className="h-4 w-4" />
              <h2 className="text-sm font-semibold uppercase tracking-wider">Generate Packet</h2>
            </div>
            <p className="text-xs text-muted-foreground">IDs must be valid UUIDs belonging to the same application context.</p>
            <div className="space-y-3">
              <div className="space-y-2">
                <label className="text-[13px] font-medium text-foreground">Application UUID</label>
                <Input value={applicationId} onChange={(e) => setApplicationId(e.target.value)} />
              </div>
              <div className="space-y-2">
                <label className="text-[13px] font-medium text-foreground">Candidate UUID</label>
                <Input value={candidateId} onChange={(e) => setCandidateId(e.target.value)} />
              </div>
              <div className="space-y-2">
                <label className="text-[13px] font-medium text-foreground">Job UUID</label>
                <Input value={jobId} onChange={(e) => setJobId(e.target.value)} />
              </div>
            </div>
            {!validGenerateInput && (applicationId || candidateId || jobId) && (
              <p className="text-xs text-amber-400">Enter valid UUID values before generating.</p>
            )}
            <Button onClick={handleGenerate} disabled={generateMutation.isPending || !validGenerateInput}>
              {generateMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Generate
            </Button>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08 }}
            className="glass rounded-xl p-6 space-y-4"
          >
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Lookup Packet</h2>
            <p className="text-xs text-muted-foreground">Enter an application UUID to load its latest decision packet.</p>
            <div className="space-y-2">
              <label className="text-[13px] font-medium text-foreground">Application UUID</label>
              <Input value={latestAppId} onChange={(e) => setLatestAppId(e.target.value)} />
            </div>
            {latestPacket && (
              <Button size="sm" variant="outline" onClick={() => setActivePacketId(latestPacket.packet_id ?? latestPacket.id ?? "")}>
                <Scale className="h-3 w-3" /> View Packet
              </Button>
            )}
          </motion.div>
        </div>

        {/* Active Packet Detail */}
        {activePacketId && packetLoading && (
          <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground py-12">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading packet…
          </div>
        )}

        {resultPacket && (
          <motion.div
            key={activePacketId}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-6"
          >
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-heading text-base font-bold text-foreground">Packet Detail</h2>
                <p className="font-mono text-[11px] text-muted-foreground">
                  {activePacketId ?? resultPacket.packet_id ?? resultPacket.id}
                </p>
              </div>
              <Badge variant="outline" className="text-[10px]">
                {resultPacket.human_review_required ? "Needs Review" : "Auto-approved"}
              </Badge>
            </div>

            <PacketOverview
              packet={resultPacket}
              packetId={activePacketId ?? resultPacket.packet_id ?? resultPacket.id ?? ""}
              orgId={orgId}
            />
          </motion.div>
        )}
      </div>
    </div>
  );
}

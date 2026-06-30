"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  CheckCircle2, XCircle, Clock, AlertTriangle, Star,
  Users, Layers, ShieldOff, GitMerge, MessageSquare,
  ChevronRight, Filter, CheckSquare, Loader2, Bot,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { useApprovals, useDecideApproval } from "@/lib/hooks";
import { useAuthStore } from "@/lib/stores/auth.store";
import { cn } from "@/lib/utils/cn";
import { relativeTime, shortDateTime } from "@/lib/utils/format";
import type { HITLApproval, HITLActionType } from "@/types";

const decisionSchema = z.object({ reason: z.string().optional() });
type DecisionForm = z.infer<typeof decisionSchema>;

const actionTypeConfig: Record<HITLActionType, { icon: typeof Star; label: string; color: string }> = {
  shortlist_approve:  { icon: Layers,       label: "Shortlist Approval",  color: "text-primary bg-primary/10 border-primary/20" },
  outreach_approve:   { icon: MessageSquare,label: "Outreach Review",     color: "text-teal-400 bg-teal-500/10 border-teal-500/20" },
  assessment_decision:{ icon: CheckSquare,  label: "Assessment Decision", color: "text-violet-400 bg-violet-500/10 border-violet-500/20" },
  interview_finalize: { icon: Users,        label: "Interview Finalize",  color: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20" },
  decision_finalize:  { icon: Star,         label: "Final Decision",      color: "text-amber-400 bg-amber-500/10 border-amber-500/20" },
  deanonymize:        { icon: ShieldOff,    label: "De-anonymize",        color: "text-orange-400 bg-orange-500/10 border-orange-500/20" },
  merge_candidates:   { icon: GitMerge,     label: "Merge Candidates",    color: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20" },
};

const priorityConfig = {
  critical: { label: "Critical", color: "bg-destructive/20 text-red-400 border-destructive/30", dot: "bg-destructive" },
  high:     { label: "High",     color: "bg-amber-500/20 text-amber-400 border-amber-500/30", dot: "bg-amber-400" },
  medium:   { label: "Medium",   color: "bg-primary/10 text-primary border-primary/20", dot: "bg-primary" },
  low:      { label: "Low",      color: "bg-muted/40 text-muted-foreground border-border/40", dot: "bg-muted-foreground/40" },
};

const statusConfig = {
  pending:  { label: "Pending",  color: "text-amber-400" },
  approved: { label: "Approved", color: "text-emerald-400" },
  rejected: { label: "Rejected", color: "text-red-400" },
  expired:  { label: "Expired",  color: "text-muted-foreground/60" },
};

function ApprovalCard({
  approval, onDecide,
}: {
  approval: HITLApproval;
  onDecide: (a: HITLApproval, decision: "approved" | "rejected") => void;
}) {
  const typeConf = actionTypeConfig[approval.actionType];
  const priConf = priorityConfig[approval.priority];
  const statConf = statusConfig[approval.status];
  const Icon = typeConf.icon;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4, scale: 0.97 }}
      className={cn(
        "glass rounded-xl overflow-hidden transition-all",
        approval.status === "pending" && "ring-1 ring-border/60 hover:ring-primary/20",
        approval.status !== "pending" && "opacity-60"
      )}
    >
      <div className="p-4">
        <div className="flex items-start gap-3">
          {/* Type icon */}
          <div className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border", typeConf.color)}>
            <Icon className="h-4 w-4" />
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2 flex-wrap">
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={cn("rounded-full border px-2 py-0.5 text-[10px] font-semibold", typeConf.color)}>
                    {typeConf.label}
                  </span>
                  <span className={cn("rounded-full border px-2 py-0.5 text-[10px] font-semibold flex items-center gap-1", priConf.color)}>
                    <span className={cn("h-1.5 w-1.5 rounded-full", priConf.dot)} />
                    {priConf.label}
                  </span>
                  {approval.status !== "pending" && (
                    <span className={cn("text-[11px] font-semibold", statConf.color)}>
                      {statConf.label}
                    </span>
                  )}
                </div>
                <p className="mt-1.5 text-[14px] font-semibold text-foreground leading-snug">{approval.targetLabel}</p>
                {approval.jobTitle && (
                  <p className="mt-0.5 text-[12px] text-muted-foreground">
                    {approval.jobTitle}{approval.candidateAlias ? ` · ${approval.candidateAlias}` : ""}
                  </p>
                )}
              </div>
              <div className="text-right shrink-0">
                <p className="text-[11px] text-muted-foreground">{relativeTime(approval.requestedAt)}</p>
                <p className="text-[10px] text-muted-foreground/60 mt-0.5">by {approval.requestedByName}</p>
              </div>
            </div>

            {/* Meta */}
            {approval.meta && (
              <div className="mt-2 flex flex-wrap gap-3">
                {Object.entries(approval.meta).map(([k, v]) => (
                  <span key={k} className="text-[11px] text-muted-foreground">
                    <span className="font-semibold capitalize">{k.replace(/_/g, " ")}:</span>{" "}
                    {typeof v === "number" && k.includes("onfidence") ? `${Math.round((v as number) * 100)}%` : String(v)}
                  </span>
                ))}
              </div>
            )}

            {/* Decided */}
            {approval.status !== "pending" && approval.decidedBy && (
              <div className={cn(
                "mt-3 rounded-lg border p-2.5 text-[12px]",
                approval.status === "approved"
                  ? "border-emerald-500/20 bg-emerald-500/5 text-emerald-400"
                  : "border-destructive/20 bg-destructive/5 text-red-400"
              )}>
                <span className="font-semibold">{approval.status === "approved" ? "Approved" : "Rejected"}</span>
                {" by "}{approval.decidedByName} · {shortDateTime(approval.decidedAt!)}
                {approval.reason && <p className="mt-1 text-foreground/70">{approval.reason}</p>}
              </div>
            )}
          </div>
        </div>

        {/* Actions */}
        {approval.status === "pending" && (
          <div className="mt-4 flex items-center gap-2 pl-12">
            <Button
              size="sm"
              className="h-8 gap-1.5 text-xs bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25 border border-emerald-500/20"
              onClick={() => onDecide(approval, "approved")}
            >
              <CheckCircle2 className="h-3.5 w-3.5" /> Approve
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 gap-1.5 text-xs text-destructive hover:bg-destructive/10"
              onClick={() => onDecide(approval, "rejected")}
            >
              <XCircle className="h-3.5 w-3.5" /> Reject
            </Button>
            <span className="text-[10px] text-muted-foreground/50 ml-auto">
              Action required — this is a non-bypassable HITL gate
            </span>
          </div>
        )}
      </div>
    </motion.div>
  );
}

function EmptyState({ filter }: { filter: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/8 ring-1 ring-primary/15 mb-4">
        <CheckCircle2 className="h-8 w-8 text-primary/60" />
      </div>
      <p className="font-heading text-base font-semibold text-foreground">
        {filter === "pending" ? "All caught up!" : "Nothing here"}
      </p>
      <p className="text-sm text-muted-foreground mt-1">
        {filter === "pending"
          ? "No pending approvals. AI agents are working in the background."
          : `No ${filter} approvals found.`}
      </p>
    </div>
  );
}

// Approvals is a manager-level queue — HR Managers / Hiring Managers (and
// admins) only. Regular HR / recruiters are not authorised, matching the
// sidebar gate so deep links don't bypass it.
const APPROVALS_ROLES = new Set([
  "hr_manager",
  "hiring_manager",
  "manager",
  "org_admin",
  "admin",
]);

export default function ApprovalsPage() {
  const { user: authUser } = useAuthStore();
  const role = String(authUser?.role ?? authUser?.accountType ?? "").toLowerCase();
  const canAccess = APPROVALS_ROLES.has(role);

  const { data: approvals = [], refetch } = useApprovals();
  const { mutateAsync: decide, isPending } = useDecideApproval();
  const [filter, setFilter] = useState<"all" | "pending" | "approved" | "rejected">("pending");
  const [deciding, setDeciding] = useState<{ approval: HITLApproval; decision: "approved" | "rejected" } | null>(null);

  const { register, handleSubmit, reset } = useForm<DecisionForm>({
    resolver: zodResolver(decisionSchema),
  });

  // Manager-only gate — declared after all hooks to satisfy the Rules of Hooks.
  if (!canAccess) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <div className="glass gradient-border rounded-2xl p-8 text-center max-w-md">
          <ShieldOff className="mx-auto mb-3 h-8 w-8 text-amber-400" />
          <p className="text-sm font-semibold text-foreground">Approvals are manager-only</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Only HR Managers and Hiring Managers can review approvals. Ask a
            manager on your team to action these requests.
          </p>
        </div>
      </div>
    );
  }

  const filtered = approvals.filter((a) => filter === "all" || a.status === filter);
  const pending = approvals.filter((a) => a.status === "pending");

  const handleDecide = (approval: HITLApproval, decision: "approved" | "rejected") => {
    setDeciding({ approval, decision });
  };

  const onSubmitDecision = async (data: DecisionForm) => {
    if (!deciding) return;
    await decide({ id: deciding.approval.id, decision: deciding.decision, reason: data.reason });
    setDeciding(null);
    reset();
    refetch();
  };

  const tabs = [
    { key: "pending",  label: "Pending",  count: pending.length },
    { key: "approved", label: "Approved", count: approvals.filter((a) => a.status === "approved").length },
    { key: "rejected", label: "Rejected", count: approvals.filter((a) => a.status === "rejected").length },
    { key: "all",      label: "All",      count: approvals.length },
  ] as const;

  return (
    <div className="h-full overflow-y-auto">
      {/* Header */}
      <div className="border-b border-border/50 bg-background/60 backdrop-blur-sm px-6 py-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="font-heading text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              <Bot className="h-5 w-5 text-primary" />
              HITL Approval Inbox
            </h1>
            <p className="text-sm text-muted-foreground">
              Human-in-the-loop gates · Every decision is non-bypassable and audit-logged
            </p>
          </div>
          {pending.length > 0 && (
            <motion.div
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="flex items-center gap-2 rounded-lg bg-amber-500/10 px-4 py-2 ring-1 ring-amber-500/20"
            >
              <AlertTriangle className="h-4 w-4 text-amber-400" />
              <span className="text-sm font-semibold text-amber-400">
                {pending.length} pending action{pending.length > 1 ? "s" : ""}
              </span>
            </motion.div>
          )}
        </div>

        {/* Filter tabs */}
        <div className="mt-4 flex items-center gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setFilter(tab.key as typeof filter)}
              className={cn(
                "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] font-medium transition-all",
                filter === tab.key
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/40"
              )}
            >
              {tab.label}
              {tab.count > 0 && (
                <span className={cn(
                  "rounded-full px-1.5 py-0.5 text-[10px] font-bold",
                  filter === tab.key ? "bg-primary/20 text-primary" : "bg-muted/40 text-muted-foreground"
                )}>
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* List */}
      <div className="p-6 space-y-3 max-w-3xl">
        <AnimatePresence mode="popLayout">
          {filtered.length === 0 ? (
            <EmptyState filter={filter} />
          ) : (
            filtered.map((approval) => (
              <ApprovalCard
                key={approval.id}
                approval={approval}
                onDecide={handleDecide}
              />
            ))
          )}
        </AnimatePresence>
      </div>

      {/* Decision dialog */}
      <Dialog open={!!deciding} onOpenChange={() => { setDeciding(null); reset(); }}>
        <DialogContent className="glass border-border/60 max-w-md">
          <DialogHeader>
            <DialogTitle className="font-heading text-base flex items-center gap-2">
              {deciding?.decision === "approved"
                ? <><CheckCircle2 className="h-4 w-4 text-emerald-400" /> Confirm Approval</>
                : <><XCircle className="h-4 w-4 text-destructive" /> Confirm Rejection</>}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmitDecision)}>
            <div className="py-3 space-y-3">
              <p className="text-sm text-muted-foreground">
                {deciding?.approval.targetLabel}
              </p>
              <div className="space-y-1.5">
                <Label className="text-sm">Reason <span className="text-muted-foreground/60">(optional)</span></Label>
                <Textarea
                  {...register("reason")}
                  placeholder="Add a note for the audit log…"
                  rows={3}
                  className="resize-none text-sm bg-muted/30 border-border/50"
                />
              </div>
              <div className="rounded-lg bg-muted/20 border border-border/40 p-2.5 text-[11px] text-muted-foreground">
                This decision will be recorded in the immutable audit log with your identity and timestamp.
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="ghost" size="sm" onClick={() => { setDeciding(null); reset(); }}>
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={isPending}
                className={cn(
                  deciding?.decision === "approved"
                    ? "bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 border border-emerald-500/20"
                    : "bg-destructive/20 text-red-400 hover:bg-destructive/30 border border-destructive/20"
                )}
              >
                {isPending ? (
                  <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Recording…</>
                ) : deciding?.decision === "approved" ? (
                  <><CheckCircle2 className="h-3.5 w-3.5" /> Confirm Approval</>
                ) : (
                  <><XCircle className="h-3.5 w-3.5" /> Confirm Rejection</>
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

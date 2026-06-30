"use client";

import { motion } from "framer-motion";
import {
  Activity, Bot, Loader2, CheckCircle2, AlertCircle, Circle,
  Clock, Cpu, RefreshCw, Sparkles,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils/cn";
import { useAgentStatus } from "@/lib/hooks";
import type { AgentStatus } from "@/types";

const agentIcons: Record<string, typeof Bot> = {
  agent_screening: Sparkles,
  agent_sourcing: RefreshCw,
  agent_assessment: Cpu,
  agent_compliance: Activity,
};

const statusConfig: Record<string, { icon: typeof Loader2; color: string; bg: string }> = {
  running:   { icon: Loader2,   color: "text-blue-400",  bg: "bg-blue-500/10 border-blue-500/25" },
  completed: { icon: CheckCircle2, color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/25" },
  failed:    { icon: AlertCircle,  color: "text-red-400",    bg: "bg-red-500/10 border-red-500/25" },
  idle:      { icon: Circle,    color: "text-muted-foreground", bg: "bg-muted/20 border-border/40" },
};

function AgentCard({ agent }: { agent: AgentStatus }) {
  const Icon = agentIcons[agent.id] ?? Bot;
  const cfg = statusConfig[agent.status] ?? statusConfig.idle;
  const StatusIcon = cfg.icon;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("glass rounded-2xl p-5 space-y-4", cfg.bg)}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className={cn("flex h-10 w-10 items-center justify-center rounded-xl", cfg.bg.replace("border", "border-0").replace("/25", "/20"))}>
            <Icon className={cn("h-5 w-5", cfg.color)} />
          </div>
          <div>
            <p className="font-heading text-sm font-bold text-foreground">{agent.name}</p>
            <p className="font-mono text-[10px] text-muted-foreground">{agent.id}</p>
          </div>
        </div>
        <Badge variant="outline" className={cn("gap-1.5 text-[10px]", cfg.bg, cfg.color)}>
          <StatusIcon className={cn("h-3 w-3", agent.status === "running" && "animate-spin")} />
          {agent.status}
        </Badge>
      </div>

      {/* Progress */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-muted-foreground">
            {agent.currentTask ?? (agent.status === "idle" ? "Waiting for tasks" : "Processing")}
          </span>
          <span className={cn("font-mono font-semibold", cfg.color)}>
            {agent.progress ?? 0}%
          </span>
        </div>
        <div className="h-2 w-full rounded-full bg-muted/30 overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${agent.progress ?? 0}%` }}
            transition={{ duration: 0.8, ease: "easeOut" }}
            className={cn(
              "h-full rounded-full",
              agent.status === "running" ? "bg-blue-400" :
              agent.status === "completed" ? "bg-emerald-400" :
              agent.status === "failed" ? "bg-red-400" : "bg-muted-foreground/30",
            )}
          />
        </div>
      </div>

      {/* Metadata */}
      <div className="flex items-center gap-4 text-[11px] text-muted-foreground">
        {agent.lastRun && (
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" /> Last: {new Date(agent.lastRun).toLocaleString()}
          </span>
        )}
      </div>
    </motion.div>
  );
}

export default function OrgAgentsPage() {
  const { data: agents = [], isLoading, isError } = useAgentStatus();

  const runningCount = agents.filter((a) => a.status === "running").length;
  const failedCount = agents.filter((a) => a.status === "failed").length;

  return (
    <div className="h-full overflow-y-auto p-6 space-y-8 max-w-5xl">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-3"
      >
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
          <Bot className="h-5 w-5 text-primary" />
        </div>
        <div>
          <h1 className="font-heading text-xl font-bold tracking-tight text-foreground">
            Agent Monitoring
          </h1>
          <p className="text-sm text-muted-foreground">
            Live status of all AI agents in the hiring pipeline.
          </p>
        </div>
      </motion.div>

      {/* Summary bar */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.03 }}
          className="glass rounded-xl p-4 space-y-1"
        >
          <p className="text-2xl font-bold text-foreground">{agents.length}</p>
          <p className="text-xs text-muted-foreground">Total agents</p>
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.06 }}
          className="glass rounded-xl p-4 space-y-1"
        >
          <p className="text-2xl font-bold text-blue-400">{runningCount}</p>
          <p className="text-xs text-muted-foreground">Active</p>
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.09 }}
          className="glass rounded-xl p-4 space-y-1"
        >
          <p className="text-2xl font-bold text-emerald-400">{agents.filter((a) => a.status === "completed" || a.status === "idle").length}</p>
          <p className="text-xs text-muted-foreground">Healthy</p>
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.12 }}
          className="glass rounded-xl p-4 space-y-1"
        >
          <p className={cn("text-2xl font-bold", failedCount > 0 ? "text-red-400" : "text-muted-foreground")}>
            {failedCount}
          </p>
          <p className="text-xs text-muted-foreground">Failed</p>
        </motion.div>
      </div>

      {/* Agent cards */}
      {isLoading && (
        <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading agent status…
        </div>
      )}

      {isError && (
        <div className="glass rounded-xl p-6 text-sm text-red-400 text-center">
          Could not load agent status. The dashboard API may be unavailable.
        </div>
      )}

      {!isLoading && !isError && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {agents.map((agent) => (
            <AgentCard key={agent.id} agent={agent} />
          ))}
        </div>
      )}
    </div>
  );
}

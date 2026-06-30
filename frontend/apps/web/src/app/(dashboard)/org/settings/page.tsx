"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Settings, Building2, Copy, Check, Globe,
  Users, Shield, AlertTriangle, Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useAuthStore } from "@/lib/stores/auth.store";
import { useOrganization } from "@/lib/hooks";

const tabs = ["General", "Members", "API", "Danger Zone"] as const;
type Tab = (typeof tabs)[number];

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
    >
      {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
      {copied ? "Copied!" : "Copy"}
    </button>
  );
}

export default function OrgSettingsPage() {
  const { user, _hasHydrated } = useAuthStore();
  const { data: org } = useOrganization();
  const [activeTab, setActiveTab] = useState<Tab>("General");
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

  if (!_hasHydrated) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading settings…
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6 max-w-4xl">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-3"
      >
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
          <Settings className="h-5 w-5 text-primary" />
        </div>
        <div>
          <h1 className="font-heading text-xl font-bold tracking-tight text-foreground">
            Workspace Settings
          </h1>
          <p className="text-sm text-muted-foreground">
            Manage your organization workspace and preferences.
          </p>
        </div>
      </motion.div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border/60 pb-1">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              "px-3 py-2 text-[13px] font-medium rounded-t-md transition-colors",
              activeTab === tab
                ? "text-foreground border-b-2 border-primary"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {tab}
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {activeTab === "General" && (
          <motion.div
            key="general"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="space-y-4"
          >
            <div className="glass gradient-border rounded-2xl p-6 space-y-4">
              <div className="flex items-center gap-2">
                <Building2 className="h-4 w-4 text-primary" />
                <h2 className="text-sm font-semibold tracking-wider text-foreground">
                  Organization
                </h2>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="glass rounded-xl p-4 space-y-1">
                  <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Name</p>
                  <p className="text-sm text-foreground font-medium">{user?.orgName ?? "—"}</p>
                </div>
                <div className="glass rounded-xl p-4 space-y-1">
                  <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Organization ID</p>
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-mono text-foreground truncate">{user?.orgId ?? "—"}</p>
                    {user?.orgId && <CopyButton text={user.orgId} />}
                  </div>
                </div>
                <div className="glass rounded-xl p-4 space-y-1">
                  <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Your Role</p>
                  <div className="flex items-center gap-2">
                    <Shield className="h-3.5 w-3.5 text-primary/70" />
                    <p className="text-sm text-foreground font-medium capitalize">{user?.role ?? "—"}</p>
                  </div>
                </div>
                <div className="glass rounded-xl p-4 space-y-1">
                  <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Industry</p>
                  <p className="text-sm text-foreground">{org?.industry ?? "—"}</p>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {activeTab === "Members" && (
          <motion.div
            key="members"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="space-y-4"
          >
            <div className="glass gradient-border rounded-2xl p-6 space-y-4">
              <div className="flex items-center gap-2">
                <Users className="h-4 w-4 text-primary" />
                <h2 className="text-sm font-semibold tracking-wider text-foreground">
                  Team Members
                </h2>
              </div>
              <p className="text-sm text-muted-foreground">
                Manage your team members and their roles. Visit the{" "}
                <a href="/settings/members" className="text-primary hover:underline">
                  Members page
                </a>{" "}
                for full member management.
              </p>
              <div className="glass rounded-xl p-4 flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
                  <Users className="h-4 w-4 text-primary" />
                </div>
                <div className="flex-1">
                  <p className="text-sm text-foreground font-medium">{user?.name ?? user?.email ?? "You"}</p>
                  <p className="text-xs text-muted-foreground">{user?.email ?? ""}</p>
                </div>
                <span className="text-[11px] font-medium text-primary bg-primary/10 px-2 py-0.5 rounded-md capitalize">
                  {user?.role ?? "member"}
                </span>
              </div>
            </div>
          </motion.div>
        )}

        {activeTab === "API" && (
          <motion.div
            key="api"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="space-y-4"
          >
            <div className="glass gradient-border rounded-2xl p-6 space-y-4">
              <div className="flex items-center gap-2">
                <Globe className="h-4 w-4 text-primary" />
                <h2 className="text-sm font-semibold tracking-wider text-foreground">
                  API Configuration
                </h2>
              </div>
              <div className="space-y-3">
                <div className="glass rounded-xl p-4 space-y-1">
                  <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Frontend API Base URL</p>
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-mono text-primary">{apiBase}</p>
                    <CopyButton text={apiBase} />
                  </div>
                </div>
                <div className="glass rounded-xl p-4 space-y-1">
                  <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Backend Status</p>
                  <p className="text-sm text-muted-foreground">
                    Configure <code className="text-[11px] font-mono bg-muted/50 px-1 rounded">NEXT_PUBLIC_API_BASE_URL</code> in your environment.
                    Ensure Uvicorn is running and <code className="text-[11px] font-mono bg-muted/50 px-1 rounded">CORS_ORIGINS</code> includes your UI origin.
                  </p>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {activeTab === "Danger Zone" && (
          <motion.div
            key="danger"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="space-y-4"
          >
            <div className="glass rounded-xl p-6 space-y-4 border border-red-500/20">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-red-400" />
                <h2 className="text-sm font-semibold tracking-wider text-foreground text-red-400">
                  Danger Zone
                </h2>
              </div>
              <p className="text-sm text-muted-foreground">
                Destructive actions for workspace administration. These cannot be undone.
              </p>
              <div className="glass rounded-xl p-4 border border-red-500/10 space-y-2">
                <p className="text-sm font-medium text-foreground">Leave Organization</p>
                <p className="text-xs text-muted-foreground">
                  Remove yourself from this organization. You will lose access to all associated data.
                </p>
                <button className="px-3 py-1.5 text-xs font-medium rounded-md border border-red-500/30 text-red-400 hover:bg-red-500/10 transition-colors">
                  Leave workspace
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

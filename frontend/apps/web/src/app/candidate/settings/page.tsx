"use client";

import { useState } from "react";
import {
  AlertTriangle,
  Bell,
  CheckCircle2,
  Download,
  Eye,
  Loader2,
  Lock,
  Shield,
  Trash2,
  User,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useCandidateProfile } from "@/lib/hooks";

// ── Section wrapper ───────────────────────────────────────────────────────────

function Section({
  icon,
  title,
  description,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 space-y-4">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary shrink-0">
          {icon}
        </div>
        <div>
          <h3 className="font-semibold text-sm">{title}</h3>
          <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
        </div>
      </div>
      {children}
    </div>
  );
}

// ── Toggle row ────────────────────────────────────────────────────────────────

function ToggleRow({
  label,
  description,
  enabled,
  onChange,
}: {
  label: string;
  description: string;
  enabled: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <div>
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      <button
        onClick={() => onChange(!enabled)}
        className={cn(
          "relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors",
          enabled ? "bg-primary" : "bg-muted",
        )}
        role="switch"
        aria-checked={enabled}
      >
        <span
          className={cn(
            "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform",
            enabled ? "translate-x-4" : "translate-x-0",
          )}
        />
      </button>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const { data: profile } = useCandidateProfile();

  // Notification prefs
  const [notifApplicationUpdate, setNotifApplicationUpdate] = useState(true);
  const [notifInterviewReminder, setNotifInterviewReminder] = useState(true);
  const [notifNewJob,            setNotifNewJob]            = useState(false);
  const [notifGrowthPlan,        setNotifGrowthPlan]        = useState(true);

  // Privacy prefs
  const [profileVisible, setProfileVisible] = useState(true);
  const [allowAnonymous,  setAllowAnonymous] = useState(true);

  // GDPR actions
  const [downloading, setDownloading] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);

  async function handleDownloadData() {
    setDownloading(true);
    // Simulate download delay
    await new Promise((r) => setTimeout(r, 1500));
    toast.success("Your data export has been prepared. Check your email.");
    setDownloading(false);
  }

  function handleSaveNotifications() {
    toast.success("Notification preferences saved.");
  }

  function handleSavePrivacy() {
    toast.success("Privacy settings updated.");
  }

  return (
    <div className="flex flex-col gap-5 p-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <User className="h-6 w-6 text-primary" />
          Account Settings
        </h1>
        <p className="text-muted-foreground mt-1">
          Manage your preferences, privacy, and GDPR rights.
        </p>
      </div>

      {/* Account summary */}
      <Section
        icon={<User className="h-4 w-4" />}
        title="Account"
        description="Your current account details."
      >
        <div className="flex items-center gap-3 rounded-lg bg-muted/30 px-4 py-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-sm">
            {profile?.fullName?.charAt(0) ?? "C"}
          </div>
          <div>
            <p className="text-sm font-semibold">{profile?.fullName ?? "Candidate"}</p>
            <p className="text-xs text-muted-foreground">{profile?.email ?? "—"}</p>
          </div>
          <Badge variant="outline" className="ml-auto text-xs">Candidate</Badge>
        </div>
      </Section>

      {/* Notifications */}
      <Section
        icon={<Bell className="h-4 w-4" />}
        title="Notifications"
        description="Choose which emails and alerts you receive."
      >
        <div className="space-y-0.5">
          <ToggleRow
            label="Application updates"
            description="Status changes on your applications."
            enabled={notifApplicationUpdate}
            onChange={setNotifApplicationUpdate}
          />
          <Separator />
          <ToggleRow
            label="Interview reminders"
            description="Reminders 24h and 1h before scheduled interviews."
            enabled={notifInterviewReminder}
            onChange={setNotifInterviewReminder}
          />
          <Separator />
          <ToggleRow
            label="New matching jobs"
            description="Weekly digest of new jobs matching your profile."
            enabled={notifNewJob}
            onChange={setNotifNewJob}
          />
          <Separator />
          <ToggleRow
            label="Growth plan updates"
            description="When milestones are added to your growth plan."
            enabled={notifGrowthPlan}
            onChange={setNotifGrowthPlan}
          />
        </div>
        <Button size="sm" onClick={handleSaveNotifications} className="gap-1.5">
          <CheckCircle2 className="h-3.5 w-3.5" />
          Save Notifications
        </Button>
      </Section>

      {/* Privacy */}
      <Section
        icon={<Eye className="h-4 w-4" />}
        title="Privacy"
        description="Control how your profile is visible to employers."
      >
        <div className="space-y-0.5">
          <ToggleRow
            label="Profile visible to employers"
            description="Allow organisations to discover you in sourcing runs."
            enabled={profileVisible}
            onChange={setProfileVisible}
          />
          <Separator />
          <ToggleRow
            label="Allow anonymised scoring"
            description="Permit AI to score your CV without revealing your name."
            enabled={allowAnonymous}
            onChange={setAllowAnonymous}
          />
        </div>
        <Button size="sm" onClick={handleSavePrivacy} className="gap-1.5">
          <CheckCircle2 className="h-3.5 w-3.5" />
          Save Privacy Settings
        </Button>
      </Section>

      {/* GDPR Rights */}
      <Section
        icon={<Shield className="h-4 w-4" />}
        title="Your Data Rights (GDPR)"
        description="Under GDPR you have the right to access, download, and erase your personal data."
      >
        <div className="space-y-3">
          {/* Right to access */}
          <div className="flex items-center justify-between gap-3 rounded-lg border border-border px-4 py-3">
            <div>
              <p className="text-sm font-medium">Download My Data</p>
              <p className="text-xs text-muted-foreground">
                Export all personal data we hold about you (JSON format).
              </p>
            </div>
            <Button
              size="sm"
              variant="outline"
              className="gap-1.5 shrink-0"
              onClick={handleDownloadData}
              disabled={downloading}
            >
              {downloading ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Download className="h-3.5 w-3.5" />
              )}
              {downloading ? "Preparing…" : "Export"}
            </Button>
          </div>

          {/* Right to erasure */}
          <div
            className={cn(
              "rounded-lg border px-4 py-3 space-y-3",
              deleteConfirm
                ? "border-destructive/50 bg-destructive/5"
                : "border-border",
            )}
          >
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-destructive">
                  Request Account Deletion
                </p>
                <p className="text-xs text-muted-foreground">
                  Permanently delete all your personal data. This cannot be undone.
                </p>
              </div>
              <Button
                size="sm"
                variant="destructive"
                className="gap-1.5 shrink-0"
                onClick={() => setDeleteConfirm(true)}
              >
                <Trash2 className="h-3.5 w-3.5" />
                Delete
              </Button>
            </div>

            {deleteConfirm && (
              <div className="flex items-start gap-3 rounded-lg bg-destructive/10 p-3">
                <AlertTriangle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
                <div className="flex-1 space-y-2">
                  <p className="text-xs font-medium text-destructive">
                    Are you absolutely sure? This will permanently erase all your
                    applications, CV data, interview history, and growth plans.
                  </p>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="destructive"
                      className="text-xs"
                      onClick={() => {
                        toast.success(
                          "Deletion request submitted. We'll process it within 30 days.",
                        );
                        setDeleteConfirm(false);
                      }}
                    >
                      Yes, delete everything
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-xs"
                      onClick={() => setDeleteConfirm(false)}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </Section>

      {/* Security */}
      <Section
        icon={<Lock className="h-4 w-4" />}
        title="Security"
        description="Manage your password and active sessions."
      >
        <Button size="sm" variant="outline" className="gap-1.5">
          <Lock className="h-3.5 w-3.5" />
          Change Password
        </Button>
      </Section>
    </div>
  );
}

"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import {
  Calendar, Clock, Video, Search, X, ChevronRight,
  Plus, Users, Loader2, CheckCircle2, AlertCircle,
  Mic, Brain, User, Globe, CalendarClock, XCircle,
} from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils/cn";
import { useAuthStore } from "@/lib/stores/auth.store";
import {
  useApplications,
  useInterviews,
  useJobs,
  useScheduleInterview,
  useGoogleIntegrationStatus,
} from "@/lib/hooks";
import { googleIntegrationApi, interviewsApi } from "@/lib/api";
import type { Application } from "@/types";

// ── Types ────────────────────────────────────────────────────────────────────

interface InterviewRecord {
  id: string;
  applicationId: string;
  candidateName: string;
  jobTitle: string;
  interviewType: string;
  status: string;
  scheduledStart: string | null;
  meetingUrl: string | null;
}

// INST.md §4 — user-facing interview statuses are limited to four. Legacy
// statuses (draft/in_progress/schedule_in_progress/no_show) still render via
// safe display mapping so existing rows never crash the list, but they are
// not selectable filters and "scheduled" absorbs the legacy in-flight ones.
const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  scheduled:    { label: "Scheduled",   color: "border-primary/30 bg-primary/10 text-primary" },
  completed:    { label: "Completed",   color: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400" },
  cancelled:    { label: "Canceled",    color: "border-rose-500/30 bg-rose-500/10 text-rose-400" },
  canceled:     { label: "Canceled",    color: "border-rose-500/30 bg-rose-500/10 text-rose-400" },
  rescheduled:  { label: "Rescheduled", color: "border-amber-500/30 bg-amber-500/10 text-amber-400" },
  // ── Legacy (display-only; mapped to "Scheduled" so the row still shows) ──
  in_progress:  { label: "Scheduled",   color: "border-primary/30 bg-primary/10 text-primary" },
  draft:        { label: "Scheduled",   color: "border-primary/30 bg-primary/10 text-primary" },
  no_show:      { label: "Canceled",    color: "border-rose-500/30 bg-rose-500/10 text-rose-400" },
};

// The only statuses HR can filter by (INST.md §4).
const USER_FACING_STATUSES = ["scheduled", "completed", "cancelled", "rescheduled"] as const;

const TYPE_ICONS: Record<string, typeof Video> = {
  technical:  Brain,
  hr:         User,
  panel:      Users,
  video:      Video,
  mixed:      Video,
};

// ── Schedule Modal ────────────────────────────────────────────────────────────

const INTERVIEW_TYPES: { value: string; label: string }[] = [
  { value: "technical", label: "Technical" },
  { value: "hr", label: "HR" },
  { value: "culture_fit", label: "Culture Fit" },
  { value: "video", label: "Video" },
  { value: "panel", label: "Panel" },
];

function ScheduleModal({
  applications,
  orgId,
  onClose,
}: {
  applications: Application[];
  orgId: string;
  onClose: () => void;
}) {
  const [applicationId, setApplicationId] = useState("");
  const [appQuery, setAppQuery] = useState("");
  const [showResults, setShowResults] = useState(false);
  const [interviewType, setInterviewType] = useState("technical");
  const [slotStart, setSlotStart] = useState("");
  const [slotEnd, setSlotEnd] = useState("");
  const [meetingUrl, setMeetingUrl] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const scheduleInterview = useScheduleInterview();
  const { data: googleStatus } = useGoogleIntegrationStatus();

  const googleConnected = googleStatus?.connected ?? false;
  const selectedApp = applications.find((a) => a.id === applicationId);

  // INST.md §1 — type-ahead over candidate name/alias, job title, app id.
  const matches = (() => {
    const q = appQuery.trim().toLowerCase();
    const pool = applications;
    if (!q) return pool.slice(0, 25);
    return pool
      .filter((a) => {
        const name = (a.candidate?.name ?? "").toLowerCase();
        const alias = (a.candidate?.alias ?? "").toLowerCase();
        const title = (a.candidate?.title ?? "").toLowerCase();
        const job = (a.job?.title ?? "").toLowerCase();
        return (
          name.includes(q) || alias.includes(q) || title.includes(q) ||
          job.includes(q) || a.id.toLowerCase().includes(q)
        );
      })
      .slice(0, 25);
  })();

  function validUrl(value: string): boolean {
    if (!value.trim()) return true; // optional
    try {
      const u = new URL(value);
      return u.protocol === "http:" || u.protocol === "https:";
    } catch {
      return false;
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (!applicationId) {
      setFormError("Select a candidate/application from the search results.");
      return;
    }
    if (!slotStart || !slotEnd) {
      setFormError("Start and end time are both required.");
      return;
    }
    if (new Date(slotEnd) <= new Date(slotStart)) {
      setFormError("End time must be after start time.");
      return;
    }
    if (!validUrl(meetingUrl)) {
      setFormError("Meeting URL must be a valid http(s) URL.");
      return;
    }
    scheduleInterview.mutate(
      {
        application_id: applicationId,
        organization_id: orgId,
        interview_type: interviewType,
        slot_start: new Date(slotStart).toISOString(),
        slot_end: new Date(slotEnd).toISOString(),
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        meeting_provider: googleConnected ? "google_meet" : meetingUrl ? "manual" : "google_meet",
        manual_meeting_url: meetingUrl || null,
        create_calendar_event: googleConnected,
      },
      {
        onSuccess: () => onClose(),
      },
    );
  };

  function pickApp(a: Application) {
    setApplicationId(a.id);
    setAppQuery(`${a.candidate?.name ?? a.candidate?.alias ?? "Candidate"} — ${a.job?.title ?? ""}`);
    setShowResults(false);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="glass gradient-border rounded-2xl p-6 w-full max-w-lg"
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="font-heading text-base font-bold text-foreground flex items-center gap-2">
            <Calendar className="h-4 w-4 text-primary" /> Schedule Interview
          </h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Application type-ahead */}
          <div className="relative">
            <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Application / Candidate</label>
            <div className="relative mt-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground/60" />
              <input
                value={appQuery}
                onChange={(e) => {
                  setAppQuery(e.target.value);
                  setApplicationId("");
                  setShowResults(true);
                }}
                onFocus={() => setShowResults(true)}
                placeholder="Search by candidate, job title, or application ID…"
                className="w-full rounded-lg border border-border/40 bg-background pl-9 pr-3 py-2 text-[13px] text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/40"
              />
            </div>
            {showResults && (
              <div className="absolute z-20 mt-1 w-full max-h-64 overflow-y-auto rounded-lg border border-border/50 bg-background shadow-xl">
                {matches.length === 0 ? (
                  <p className="px-3 py-3 text-[12px] text-muted-foreground">No matching applications.</p>
                ) : (
                  matches.map((a) => (
                    <button
                      key={a.id}
                      type="button"
                      onClick={() => pickApp(a)}
                      className="w-full text-left px-3 py-2 hover:bg-muted/40 border-b border-border/20 last:border-0"
                    >
                      <p className="text-[13px] font-medium text-foreground truncate">
                        {a.candidate?.name ?? a.candidate?.alias ?? "Candidate"}
                      </p>
                      <p className="text-[11px] text-muted-foreground truncate">
                        {a.job?.title ?? a.jobId} · #{a.id.slice(0, 8)}
                        {a.status ? ` · ${String(a.status).replace(/_/g, " ")}` : ""}
                      </p>
                    </button>
                  ))
                )}
              </div>
            )}
            {selectedApp && (
              <p className="mt-1 text-[11px] text-emerald-400">
                Selected: {selectedApp.candidate?.name ?? selectedApp.candidate?.alias} · #{selectedApp.id.slice(0, 8)}
              </p>
            )}
          </div>

          {/* Type */}
          <div>
            <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Interview Type</label>
            <div className="mt-1 flex flex-wrap gap-2">
              {INTERVIEW_TYPES.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => setInterviewType(t.value)}
                  className={cn(
                    "rounded-full border px-3 py-1 text-xs font-medium transition-all",
                    interviewType === t.value
                      ? "border-primary/40 bg-primary/15 text-primary"
                      : "border-border/50 text-muted-foreground hover:border-border hover:text-foreground"
                  )}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {/* Time slots */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Start</label>
              <input
                type="datetime-local"
                required
                value={slotStart}
                onChange={(e) => setSlotStart(e.target.value)}
                className="mt-1 w-full rounded-lg border border-border/40 bg-background px-3 py-2 text-[13px] text-foreground focus:outline-none focus:ring-1 focus:ring-primary/40"
              />
            </div>
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">End</label>
              <input
                type="datetime-local"
                required
                value={slotEnd}
                onChange={(e) => setSlotEnd(e.target.value)}
                className="mt-1 w-full rounded-lg border border-border/40 bg-background px-3 py-2 text-[13px] text-foreground focus:outline-none focus:ring-1 focus:ring-primary/40"
              />
            </div>
          </div>

          {/* Meeting URL */}
          <div>
            <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Meeting URL (optional)</label>
            <input
              type="url"
              placeholder="https://meet.google.com/…"
              value={meetingUrl}
              onChange={(e) => setMeetingUrl(e.target.value)}
              className="mt-1 w-full rounded-lg border border-border/40 bg-background px-3 py-2 text-[13px] text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/40"
            />
          </div>

          {formError && (
            <p className="text-xs text-rose-400">{formError}</p>
          )}

          {/* Google Calendar status */}
          <div className={cn(
            "flex items-center gap-2 rounded-lg border px-3 py-2 text-xs",
            googleConnected
              ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-400"
              : "border-amber-500/30 bg-amber-500/5 text-amber-400",
          )}>
            <Globe className="h-3.5 w-3.5 shrink-0" />
            <span className="flex-1">
              {googleConnected
                ? `Google Calendar connected (${googleStatus?.email})`
                : "Google Calendar not connected"}
            </span>
            {!googleConnected && (
              <Button
                size="sm"
                variant="ghost"
                className="h-7 text-[11px]"
                onClick={async () => {
                  const { authorize_url } = await googleIntegrationApi.connect();
                  const w = window.open(authorize_url, "google-oauth", "width=600,height=700");
                  const handler = (e: MessageEvent) => {
                    if (e.data?.type === "paths-google-oauth") {
                      window.removeEventListener("message", handler);
                      w?.close();
                      window.location.reload();
                    }
                  };
                  window.addEventListener("message", handler);
                }}
              >
                Connect
              </Button>
            )}
          </div>

          {scheduleInterview.error && (
            <p className="text-xs text-rose-400">{String((scheduleInterview.error as Error).message)}</p>
          )}

          <div className="flex gap-2 pt-2">
            <Button type="button" variant="outline" className="flex-1" onClick={onClose}>Cancel</Button>
            <Button type="submit" className="flex-1 glow-blue gap-2" disabled={scheduleInterview.isPending}>
              {scheduleInterview.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Calendar className="h-4 w-4" />}
              Schedule
            </Button>
          </div>
        </form>
      </motion.div>
    </div>
  );
}

// ── Reschedule Modal ──────────────────────────────────────────────────────────

function RescheduleModal({
  interview,
  pending,
  onClose,
  onSubmit,
}: {
  interview: InterviewRecord;
  pending: boolean;
  onClose: () => void;
  onSubmit: (newStartIso: string, newEndIso: string) => void;
}) {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!start || !end) {
      setError("Pick a new start and end time.");
      return;
    }
    if (new Date(end) <= new Date(start)) {
      setError("End time must be after start time.");
      return;
    }
    onSubmit(new Date(start).toISOString(), new Date(end).toISOString());
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="glass gradient-border rounded-2xl p-6 w-full max-w-md"
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-heading text-base font-bold text-foreground flex items-center gap-2">
            <CalendarClock className="h-4 w-4 text-amber-400" /> Reschedule interview
          </h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>
        <p className="text-[12px] text-muted-foreground mb-4 truncate">
          {interview.candidateName} · {interview.jobTitle}
        </p>
        <form onSubmit={submit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">New start</label>
              <input
                type="datetime-local"
                required
                value={start}
                onChange={(e) => setStart(e.target.value)}
                className="mt-1 w-full rounded-lg border border-border/40 bg-background px-3 py-2 text-[13px] text-foreground focus:outline-none focus:ring-1 focus:ring-primary/40"
              />
            </div>
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">New end</label>
              <input
                type="datetime-local"
                required
                value={end}
                onChange={(e) => setEnd(e.target.value)}
                className="mt-1 w-full rounded-lg border border-border/40 bg-background px-3 py-2 text-[13px] text-foreground focus:outline-none focus:ring-1 focus:ring-primary/40"
              />
            </div>
          </div>
          {error && <p className="text-xs text-rose-400">{error}</p>}
          <div className="flex gap-2 pt-1">
            <Button type="button" variant="outline" className="flex-1" onClick={onClose}>Cancel</Button>
            <Button type="submit" className="flex-1 gap-2 bg-amber-600 hover:bg-amber-500 text-white" disabled={pending}>
              {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarClock className="h-4 w-4" />}
              Reschedule
            </Button>
          </div>
        </form>
      </motion.div>
    </div>
  );
}

// ── Interview Card ────────────────────────────────────────────────────────────

function InterviewCard({
  interview,
  onCancel,
  onReschedule,
  busy,
}: {
  interview: InterviewRecord;
  onCancel: (iv: InterviewRecord) => void;
  onReschedule: (iv: InterviewRecord) => void;
  busy: boolean;
}) {
  const cfg = STATUS_CONFIG[interview.status] ?? { label: interview.status, color: "border-muted/30 text-muted-foreground" };
  const TypeIcon = TYPE_ICONS[interview.interviewType] ?? Video;
  // Cancel / reschedule only make sense while the interview is still active
  // (not already completed or canceled).
  const terminal =
    interview.status === "completed" ||
    interview.status === "cancelled" ||
    interview.status === "canceled" ||
    interview.status === "no_show";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass gradient-border rounded-xl p-4 flex items-center gap-4 hover:ring-1 hover:ring-primary/20 transition-all"
    >
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 ring-1 ring-primary/20">
        <TypeIcon className="h-4 w-4 text-primary" />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap mb-0.5">
          <p className="font-heading text-[14px] font-bold text-foreground truncate">{interview.candidateName}</p>
          <Badge variant="outline" className={cn("text-[10px]", cfg.color)}>{cfg.label}</Badge>
          <Badge variant="outline" className="text-[10px] border-muted/30 text-muted-foreground">
            {interview.interviewType.replace("_", " ")}
          </Badge>
        </div>
        <p className="text-[12px] text-muted-foreground truncate">{interview.jobTitle}</p>
        {interview.scheduledStart && (
          <div className="flex items-center gap-1.5 mt-1 text-[11px] text-muted-foreground/70">
            <Clock className="h-3 w-3" />
            {new Date(interview.scheduledStart).toLocaleString()}
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 shrink-0">
        {interview.meetingUrl && (
          <a
            href={interview.meetingUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 rounded-lg border border-primary/30 bg-primary/10 px-3 py-1.5 text-[11px] font-medium text-primary hover:bg-primary/20 transition-colors"
          >
            <Video className="h-3 w-3" /> Join
          </a>
        )}
        <Link href={`/interviews/${interview.id}`}>
          <Button variant="ghost" size="sm" className="gap-1 text-xs text-muted-foreground">
            Manage <ChevronRight className="h-3.5 w-3.5" />
          </Button>
        </Link>
        {!terminal && (
          <>
            <Button
              variant="ghost"
              size="sm"
              className="gap-1 text-xs text-amber-400"
              disabled={busy}
              onClick={() => onReschedule(interview)}
            >
              <CalendarClock className="h-3.5 w-3.5" /> Reschedule
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="gap-1 text-xs text-rose-400"
              disabled={busy}
              onClick={() => onCancel(interview)}
            >
              {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <XCircle className="h-3.5 w-3.5" />} Cancel
            </Button>
          </>
        )}
      </div>
    </motion.div>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function InterviewsPage() {
  const { user } = useAuthStore();
  const orgId = user?.orgId ?? "";
  const qc = useQueryClient();
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("scheduled");
  const [showModal, setShowModal] = useState(false);
  const [rescheduleTarget, setRescheduleTarget] = useState<InterviewRecord | null>(null);

  const { data: applications = [], isLoading: appsLoading } = useApplications();
  const { data: interviews = [], isLoading: interviewsLoading } = useInterviews(orgId);

  // ── Cancel / Reschedule (per-row actions) ──────────────────────────────
  const cancelMutation = useMutation({
    mutationFn: (interviewId: string) => interviewsApi.cancel(interviewId, orgId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["interviews", orgId] });
      setStatusFilter("cancelled"); // jump to the Canceled tab
      toast.success("Interview canceled.");
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Could not cancel interview."),
  });

  const rescheduleMutation = useMutation({
    mutationFn: (vars: { interviewId: string; new_start: string; new_end: string }) =>
      interviewsApi.reschedule(vars.interviewId, orgId, {
        new_start: vars.new_start,
        new_end: vars.new_end,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["interviews", orgId] });
      setRescheduleTarget(null);
      setStatusFilter("rescheduled"); // jump to the Rescheduled tab
      toast.success("Interview rescheduled.");
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Could not reschedule interview."),
  });

  const busyId =
    cancelMutation.isPending ? (cancelMutation.variables as string)
    : rescheduleMutation.isPending ? rescheduleMutation.variables?.interviewId
    : null;

  // Map any stored status onto one of the four user-facing buckets so legacy
  // rows (draft / in_progress / no_show) still appear under a valid filter.
  const normalizeStatus = (s: string): string => {
    if (s === "in_progress" || s === "draft") return "scheduled";
    if (s === "no_show" || s === "canceled") return "cancelled";
    return s;
  };

  const filtered = interviews.filter((iv) => {
    const q = query.toLowerCase();
    const matchesQ = !q || iv.candidateName.toLowerCase().includes(q) || iv.jobTitle.toLowerCase().includes(q);
    const matchesStatus = normalizeStatus(iv.status) === statusFilter;
    return matchesQ && matchesStatus;
  });

  const statuses = [...USER_FACING_STATUSES];
  const statusLabel = (s: string) => STATUS_CONFIG[s]?.label ?? s;

  return (
    <>
      <AnimatePresence>
        {showModal && (
          <ScheduleModal
            applications={applications}
            orgId={orgId}
            onClose={() => setShowModal(false)}
          />
        )}
        {rescheduleTarget && (
          <RescheduleModal
            interview={rescheduleTarget}
            pending={rescheduleMutation.isPending}
            onClose={() => setRescheduleTarget(null)}
            onSubmit={(new_start, new_end) =>
              rescheduleMutation.mutate({
                interviewId: rescheduleTarget.id,
                new_start,
                new_end,
              })
            }
          />
        )}
      </AnimatePresence>

      <div className="h-full overflow-y-auto">
        <div className="px-6 py-6 max-w-5xl mx-auto">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center justify-between mb-6"
          >
            <div>
              <h1 className="font-heading text-2xl font-bold text-foreground">Interview Intelligence</h1>
              <p className="mt-0.5 text-sm text-muted-foreground">Schedule interviews, capture the post-meeting transcript, and run grounded AI analysis.</p>
            </div>
            <Button className="gap-2 glow-blue" onClick={() => setShowModal(true)}>
              <Plus className="h-4 w-4" /> Schedule Interview
            </Button>
          </motion.div>

          {/* Stats */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-6"
          >
            {[
              { label: "Total", count: interviews.length, color: "text-foreground" },
              {
                label: "Scheduled",
                count: interviews.filter((i) => normalizeStatus(i.status) === "scheduled").length,
                color: "text-primary",
              },
              { label: "Completed", count: interviews.filter((i) => normalizeStatus(i.status) === "completed").length, color: "text-emerald-400" },
              { label: "Canceled", count: interviews.filter((i) => normalizeStatus(i.status) === "cancelled").length, color: "text-rose-400" },
              { label: "Rescheduled", count: interviews.filter((i) => normalizeStatus(i.status) === "rescheduled").length, color: "text-amber-400" },
            ].map(({ label, count, color }) => (
              <div key={label} className="glass gradient-border rounded-xl p-4 text-center">
                <p className={cn("font-heading text-2xl font-bold", color)}>{count}</p>
                <p className="text-[11px] text-muted-foreground">{label}</p>
              </div>
            ))}
          </motion.div>

          {/* Filters */}
          <div className="flex flex-col gap-3 mb-5">
            <div className="relative">
              <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search candidate or job…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="h-10 pl-10 pr-4"
              />
              {query && (
                <button onClick={() => setQuery("")} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-muted-foreground">
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>

            <div className="flex flex-wrap gap-2">
              {statuses.map((s) => (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s)}
                  className={cn(
                    "rounded-full border px-3 py-1 text-xs font-medium transition-all",
                    statusFilter === s
                      ? "border-primary/40 bg-primary/15 text-primary"
                      : "border-border/50 text-muted-foreground hover:border-border hover:text-foreground"
                  )}
                >
                  {statusLabel(s)}
                </button>
              ))}
            </div>
          </div>

          {/* List */}
          <div className="space-y-3">
            {interviewsLoading || appsLoading ? (
              <div className="flex items-center justify-center py-16">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" /> Loading interviews…
                </div>
              </div>
            ) : filtered.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-border/40 py-16 text-center">
                <Calendar className="mx-auto mb-3 h-10 w-10 text-muted-foreground/30" />
                <p className="text-sm text-muted-foreground">No interviews found.</p>
                <Button className="mt-4 glow-blue gap-2" size="sm" onClick={() => setShowModal(true)}>
                  <Plus className="h-4 w-4" /> Schedule First Interview
                </Button>
              </div>
            ) : (
              filtered.map((iv) => (
                <InterviewCard
                  key={iv.id}
                  interview={iv}
                  busy={busyId === iv.id}
                  onCancel={(i) => cancelMutation.mutate(i.id)}
                  onReschedule={(i) => setRescheduleTarget(i)}
                />
              ))
            )}
          </div>
        </div>
      </div>
    </>
  );
}

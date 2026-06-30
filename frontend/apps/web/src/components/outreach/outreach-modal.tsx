"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Loader2,
  Send,
  Sparkles,
  RefreshCcw,
  Save,
  Calendar as CalendarIcon,
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
} from "lucide-react";
import {
  useGenerateOutreachEmail,
  useGoogleIntegrationConnect,
  useGoogleIntegrationStatus,
  useSaveOutreachDraft,
  useSendOutreachAgent,
} from "@/lib/hooks";
import { outreachAgentApi, type BackendOutreachCreateBody } from "@/lib/api";

/** Local LabeledInput wrapper — the project's `Input` doesn't take `label`. */
function L({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
      {label}
      {children}
    </label>
  );
}

const DAYS = [
  { code: 0, label: "Mon" },
  { code: 1, label: "Tue" },
  { code: 2, label: "Wed" },
  { code: 3, label: "Thu" },
  { code: 4, label: "Fri" },
  { code: 5, label: "Sat" },
  { code: 6, label: "Sun" },
];

type AvailabilityWindow = {
  day_of_week: number;
  start_time: string;
  end_time: string;
};

const DEFAULT_WINDOWS: AvailabilityWindow[] = [
  { day_of_week: 0, start_time: "10:00", end_time: "13:00" },
  { day_of_week: 2, start_time: "13:00", end_time: "17:00" },
  { day_of_week: 4, start_time: "10:00", end_time: "12:00" },
];

/** Purpose of the "complete your profile / create your account" outreach. */
const PROFILE_COMPLETION = "Complete Profile";

/** What HR can outreach for — the email is drafted differently for each. */
const OUTREACH_PURPOSES: { value: string; title: string; desc: string }[] = [
  {
    value: "HR Interview",
    title: "HR Interview",
    desc: "Background, motivation & fit with the team and culture.",
  },
  {
    value: "Technical Interview",
    title: "Technical Interview",
    desc: "Hands-on skills and problem-solving for the role.",
  },
  {
    value: "Mixed Interview",
    title: "Mixed Interview",
    desc: "Get to know the person and their ability to adapt to the company's environment.",
  },
  {
    value: PROFILE_COMPLETION,
    title: "Complete Profile Request",
    desc: "Invite the candidate to create their own account on PATHS and complete their profile.",
  },
];

export type OutreachModalProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  candidate: {
    id: string;
    name: string | null;
    email: string | null;
    title?: string | null;
  };
  job?: {
    id: string;
    title: string;
  } | null;
};

export function OutreachModal({
  open,
  onOpenChange,
  candidate,
  job,
}: OutreachModalProps) {
  const { data: googleStatus, refetch: refetchGoogle } =
    useGoogleIntegrationStatus();
  const generate = useGenerateOutreachEmail();
  const saveDraft = useSaveOutreachDraft();
  const send = useSendOutreachAgent();
  const connect = useGoogleIntegrationConnect();

  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [recipient, setRecipient] = useState(candidate.email ?? "");
  const prevCandidateId = useRef(candidate.id);
  // Null until HR picks which interview this outreach is for. The email is only
  // drafted once a type is chosen, and is tailored to that type.
  const [interviewType, setInterviewType] = useState<string | null>(null);
  const [duration, setDuration] = useState(30);
  const [buffer, setBuffer] = useState(10);
  const [tz, setTz] = useState("Africa/Cairo");
  const [windows, setWindows] = useState<AvailabilityWindow[]>(DEFAULT_WINDOWS);
  const [previewLink, setPreviewLink] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<
    | { type: "info"; message: string }
    | { type: "error"; message: string }
    | { type: "success"; message: string }
    | null
  >(null);

  if (prevCandidateId.current !== candidate.id) {
    prevCandidateId.current = candidate.id;
    setRecipient((prev) => prev || candidate.email || "");
    // New candidate → start fresh: HR re-picks the interview type.
    setInterviewType(null);
    setSubject("");
    setBody("");
    setPreviewLink(null);
  }

  // Listen for popup-window message from /google-integration/callback.
  useEffect(() => {
    function onMessage(ev: MessageEvent) {
      const data = ev.data as { type?: string; success?: boolean; message?: string } | null;
      if (data?.type === "paths-google-oauth") {
        if (data.success) {
          setFeedback({ type: "success", message: "Google account connected." });
        } else {
          setFeedback({
            type: "error",
            message: `Google connection failed: ${data.message ?? "unknown"}`,
          });
        }
        void refetchGoogle();
      }
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [refetchGoogle]);

  // "Complete Profile Request" sends a plain email (no booking link, no HR
  // availability, no Google dependency) — gates differ accordingly.
  const isProfileCompletion = interviewType === PROFILE_COMPLETION;
  const [pcSending, setPcSending] = useState(false);

  const canSend = isProfileCompletion
    ? Boolean(recipient.trim()) && Boolean(subject.trim()) && Boolean(body.trim())
    : Boolean(googleStatus?.connected) &&
      Boolean(recipient.trim()) &&
      Boolean(subject.trim()) &&
      body.includes("{{SCHEDULING_LINK}}");

  const sendBlockedReason = useMemo(() => {
    if (!recipient.trim()) return "Candidate has no email — set one before sending.";
    if (!subject.trim()) return "Subject is required.";
    if (isProfileCompletion) {
      if (!body.trim()) return "Email body is required.";
      return null;
    }
    if (!body.includes("{{SCHEDULING_LINK}}"))
      return "Body must keep the {{SCHEDULING_LINK}} placeholder.";
    if (!googleStatus?.connected)
      return "Connect Google Calendar and Gmail to send outreach.";
    return null;
  }, [recipient, subject, body, googleStatus?.connected, isProfileCompletion]);

  function buildPayload(): BackendOutreachCreateBody {
    return {
      candidate_id: candidate.id,
      job_id: job?.id ?? null,
      subject: subject.trim(),
      email_body: body,
      interview_type: interviewType ?? "HR Interview",
      duration_minutes: duration,
      buffer_minutes: buffer,
      timezone: tz,
      availability: windows.map((w) => ({
        day_of_week: w.day_of_week,
        start_time: w.start_time,
        end_time: w.end_time,
        timezone: tz,
      })),
      recipient_email: recipient.trim() || undefined,
    };
  }

  async function onGenerate(typeOverride?: string) {
    const t = typeOverride ?? interviewType ?? "HR Interview";
    setFeedback(null);
    // Complete-profile request → deterministic invite to create an account.
    if (t === PROFILE_COMPLETION) {
      try {
        const r = await outreachAgentApi.profileCompletionGenerate({
          candidate_id: candidate.id,
        });
        setSubject(r.subject);
        setBody(r.body);
      } catch (e) {
        setFeedback({
          type: "error",
          message: e instanceof Error ? e.message : "Could not generate email.",
        });
      }
      return;
    }
    try {
      const r = await generate.mutateAsync({
        candidate_id: candidate.id,
        job_id: job?.id ?? null,
        interview_type: t,
      });
      setSubject(r.subject);
      setBody(r.body);
      if (r.fallback) {
        setFeedback({
          type: "info",
          message: "Generated using offline template (LLM unavailable).",
        });
      }
    } catch (e) {
      setFeedback({
        type: "error",
        message: e instanceof Error ? e.message : "Could not generate email.",
      });
    }
  }

  // HR picks the interview type → tailor and draft the email for that type.
  function chooseType(value: string) {
    setInterviewType(value);
    setSubject("");
    setBody("");
    setPreviewLink(null);
    void onGenerate(value);
  }

  async function onSaveDraft() {
    setFeedback(null);
    try {
      const r = await saveDraft.mutateAsync(buildPayload());
      setPreviewLink(r.booking_link);
      setFeedback({
        type: "success",
        message: "Draft saved. Booking link is ready to preview.",
      });
    } catch (e) {
      setFeedback({
        type: "error",
        message: e instanceof Error ? e.message : "Could not save draft.",
      });
    }
  }

  async function onSend() {
    if (sendBlockedReason) {
      setFeedback({ type: "error", message: sendBlockedReason });
      return;
    }
    setFeedback(null);
    // Complete-profile request → plain email, no booking link / calendar.
    if (isProfileCompletion) {
      setPcSending(true);
      try {
        await outreachAgentApi.profileCompletionSend({
          candidate_id: candidate.id,
          subject: subject.trim(),
          body,
          recipient_email: recipient.trim() || undefined,
        });
        setFeedback({
          type: "success",
          message:
            "Outreach sent. The candidate received an invitation to create their account and complete their profile.",
        });
      } catch (e) {
        setFeedback({
          type: "error",
          message: e instanceof Error ? e.message : "Could not send outreach.",
        });
      } finally {
        setPcSending(false);
      }
      return;
    }
    try {
      const r = await send.mutateAsync(buildPayload());
      if (!r.ok) {
        setFeedback({
          type: "error",
          message: r.error ?? "Send failed.",
        });
        return;
      }
      setFeedback({
        type: "success",
        message: "Outreach sent. The candidate will receive the booking link by email.",
      });
    } catch (e) {
      setFeedback({
        type: "error",
        message: e instanceof Error ? e.message : "Could not send outreach.",
      });
    }
  }

  async function onConnectGoogle() {
    setFeedback(null);
    try {
      const r = await connect.mutateAsync();
      const popup = window.open(
        r.authorize_url,
        "paths-google-oauth",
        "width=560,height=720,popup=1",
      );
      if (!popup) {
        setFeedback({
          type: "error",
          message: "Popup blocked. Allow popups and retry.",
        });
      }
    } catch (e) {
      setFeedback({
        type: "error",
        message: e instanceof Error ? e.message : "Could not start Google connect.",
      });
    }
  }

  function setWindow(i: number, patch: Partial<AvailabilityWindow>) {
    setWindows((prev) => prev.map((w, idx) => (idx === i ? { ...w, ...patch } : w)));
  }

  function removeWindow(i: number) {
    setWindows((prev) => prev.filter((_, idx) => idx !== i));
  }

  function addWindow() {
    setWindows((prev) => [
      ...prev,
      { day_of_week: 1, start_time: "10:00", end_time: "12:00" },
    ]);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="glass border-border/60 max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Send className="h-4 w-4 text-primary" /> Outreach to {candidate.name ?? "candidate"}
          </DialogTitle>
        </DialogHeader>

        {/* Google connection state — irrelevant for a complete-profile
            request (plain email, no calendar). */}
        {!isProfileCompletion && (
          <GoogleStatusBanner
            status={googleStatus}
            onConnect={() => void onConnectGoogle()}
            connecting={connect.isPending}
          />
        )}

        {feedback && (
          <div
            className={
              "rounded-lg border px-3 py-2 text-[13px] " +
              (feedback.type === "error"
                ? "border-red-500/30 bg-red-500/10 text-red-300"
                : feedback.type === "success"
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                  : "border-amber-500/30 bg-amber-500/10 text-amber-200")
            }
          >
            {feedback.message}
          </div>
        )}

        {/* Summary */}
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <div className="rounded-xl border border-border/40 bg-muted/20 p-3">
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground">Candidate</p>
            <p className="mt-1 text-sm font-semibold">{candidate.name ?? "Unknown"}</p>
            <p className="text-[12px] text-muted-foreground">{candidate.title ?? "—"}</p>
            <p className="text-[12px] text-muted-foreground">
              {candidate.email ?? "no email on file"}
            </p>
          </div>
          <div className="rounded-xl border border-border/40 bg-muted/20 p-3">
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground">Job</p>
            <p className="mt-1 text-sm font-semibold">{job?.title ?? "—"}</p>
            <p className="text-[12px] text-muted-foreground">
              {job?.id ? `Job id ${job.id.slice(0, 8)}…` : "No job linked"}
            </p>
          </div>
        </div>

        {/* Purpose chooser — asked before drafting; the email is tailored to it. */}
        <div className="space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            What is this outreach for?
          </p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {OUTREACH_PURPOSES.map((it) => {
              const selected = interviewType === it.value;
              return (
                <button
                  key={it.value}
                  type="button"
                  onClick={() => chooseType(it.value)}
                  disabled={generate.isPending}
                  className={
                    "rounded-xl border p-3 text-left transition-colors disabled:opacity-60 " +
                    (selected
                      ? "border-primary/60 bg-primary/10 ring-1 ring-primary/30"
                      : "border-border/40 bg-muted/20 hover:border-primary/40 hover:bg-primary/5")
                  }
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className={"text-sm font-semibold " + (selected ? "text-primary" : "text-foreground")}>
                      {it.title}
                    </p>
                    {selected && <CheckCircle2 className="h-4 w-4 shrink-0 text-primary" />}
                  </div>
                  <p className="mt-1 text-[11px] leading-snug text-muted-foreground">{it.desc}</p>
                </button>
              );
            })}
          </div>
        </div>

        {/* Email editor — only after a purpose is chosen */}
        {!interviewType ? (
          <div className="rounded-xl border border-dashed border-border/50 px-4 py-8 text-center">
            <Sparkles className="mx-auto mb-2 h-6 w-6 text-muted-foreground/40" />
            <p className="text-sm font-medium text-muted-foreground">Pick what this outreach is for above</p>
            <p className="mt-0.5 text-[12px] text-muted-foreground/70">
              The Outreach Agent will draft an email tailored to your choice.
            </p>
          </div>
        ) : (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="border-primary/30 bg-primary/5 text-[11px] text-primary">
              {isProfileCompletion ? "Complete Profile Request" : interviewType}
            </Badge>
            <Button size="sm" variant="secondary" onClick={() => void onGenerate()} disabled={generate.isPending}>
              {generate.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
              {subject || body ? "Regenerate" : "Generate Email"}
            </Button>
            {!isProfileCompletion && (
              <Button size="sm" variant="ghost" onClick={() => void onSaveDraft()} disabled={saveDraft.isPending}>
                {saveDraft.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
                Save Draft
              </Button>
            )}
            {!isProfileCompletion && previewLink && (
              <a
                href={previewLink}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-[12px] text-primary hover:underline"
              >
                Preview booking link <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>

          <L label="Recipient (To)">
            <Input
              value={recipient}
              onChange={(e) => setRecipient(e.target.value)}
              placeholder="candidate@example.com"
            />
          </L>

          <L label="Subject">
            <Input
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
            />
          </L>

          <div>
            <label className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              {isProfileCompletion ? "Body" : <>Body (must keep {"{{SCHEDULING_LINK}}"})</>}
            </label>
            <Textarea
              rows={10}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="The Outreach Agent will draft a personalized message here…"
            />
          </div>
        </div>
        )}

        {/* Availability + interview details — not needed for a
            complete-profile request (plain email, nothing to schedule). */}
        {!isProfileCompletion && (
        <div className="space-y-3 rounded-xl border border-border/40 bg-muted/20 p-3">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-widest text-muted-foreground">
            <CalendarIcon className="h-3 w-3" /> HR availability
          </div>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <L label="Interview type">
              <div className="flex h-9 items-center rounded-md border border-border bg-muted/30 px-3 text-sm text-foreground">
                {interviewType ?? "—"}
              </div>
            </L>
            <L label="Duration (min)">
              <Input
                type="number"
                min={5}
                max={240}
                value={duration}
                onChange={(e) => setDuration(Number(e.target.value))}
              />
            </L>
            <L label="Buffer (min)">
              <Input
                type="number"
                min={0}
                max={60}
                value={buffer}
                onChange={(e) => setBuffer(Number(e.target.value))}
              />
            </L>
            <L label="Timezone">
              <Input
                value={tz}
                onChange={(e) => setTz(e.target.value)}
              />
            </L>
          </div>
          <div className="space-y-2">
            {windows.map((w, i) => (
              <div key={i} className="grid grid-cols-2 items-end gap-2 md:grid-cols-4">
                <label className="flex flex-col gap-1 text-[11px] uppercase tracking-wider text-muted-foreground">
                  Day
                  <select
                    value={w.day_of_week}
                    onChange={(e) =>
                      setWindow(i, { day_of_week: Number(e.target.value) })
                    }
                    className="rounded-md border border-border bg-background px-2 py-1 text-sm"
                  >
                    {DAYS.map((d) => (
                      <option key={d.code} value={d.code}>
                        {d.label}
                      </option>
                    ))}
                  </select>
                </label>
                <L label="Start">
                  <Input
                    type="time"
                    value={w.start_time}
                    onChange={(e) => setWindow(i, { start_time: e.target.value })}
                  />
                </L>
                <L label="End">
                  <Input
                    type="time"
                    value={w.end_time}
                    onChange={(e) => setWindow(i, { end_time: e.target.value })}
                  />
                </L>
                <Button size="sm" variant="ghost" onClick={() => removeWindow(i)}>
                  Remove
                </Button>
              </div>
            ))}
            <Button size="sm" variant="ghost" onClick={addWindow}>
              + Add another window
            </Button>
          </div>
        </div>
        )}

        <DialogFooter className="flex-col gap-2 sm:flex-row sm:justify-between">
          <div className="text-[12px] text-muted-foreground">
            HR reviews and clicks <strong>Send</strong>. Nothing is sent automatically.
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="ghost" onClick={() => onOpenChange(false)}>
              Close
            </Button>
            <Button
              onClick={() => void onSend()}
              disabled={!canSend || send.isPending || pcSending}
              title={sendBlockedReason ?? undefined}
            >
              {send.isPending || pcSending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Send className="h-3 w-3" />}
              Send Outreach
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function GoogleStatusBanner(props: {
  status:
    | {
        connected: boolean;
        configured: boolean;
        email: string | null;
        last_error: string | null;
      }
    | undefined;
  onConnect: () => void;
  connecting: boolean;
}) {
  const s = props.status;
  if (!s) {
    return (
      <div className="rounded-lg border border-border/40 bg-muted/20 px-3 py-2 text-[12px] text-muted-foreground">
        Checking Google connection…
      </div>
    );
  }
  if (s.connected) {
    return (
      <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-[12px] text-emerald-300 flex items-center gap-2">
        <CheckCircle2 className="h-3 w-3" />
        Google connected as <strong>{s.email ?? "—"}</strong>. Sending will use Gmail and create a Google Meet link automatically.
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[12px] text-amber-200 flex flex-wrap items-center gap-2">
      <AlertTriangle className="h-3 w-3" />
      <span>
        {s.configured
          ? "Connect Google Calendar and Gmail to send outreach."
          : "Google OAuth is not configured on the server. Outreach can be drafted but not sent."}
      </span>
      {s.configured && (
        <Button size="sm" variant="secondary" onClick={props.onConnect} disabled={props.connecting}>
          {props.connecting ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
          Connect Google
        </Button>
      )}
      {s.last_error && (
        <Badge variant="outline" className="border-red-500/30 text-red-300">
          {s.last_error.slice(0, 60)}
        </Badge>
      )}
    </div>
  );
}

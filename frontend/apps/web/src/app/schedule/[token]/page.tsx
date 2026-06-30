"use client";

import { use, useMemo, useState } from "react";
import {
  Loader2,
  Calendar as CalendarIcon,
  CheckCircle2,
  XCircle,
  Building2,
  Briefcase,
  Clock,
  Globe,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useBookPublicSlot, usePublicSchedule } from "@/lib/hooks";
import { cn } from "@/lib/utils/cn";

export default function PublicSchedulePage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = use(params);
  const { data, isLoading, isError, error, refetch } = usePublicSchedule(token);
  const book = useBookPublicSlot();

  const [selected, setSelected] = useState<{ start: string; end: string } | null>(null);
  const [confirm, setConfirm] = useState<
    | { type: "success"; message: string; meet: string | null; start: string; end: string }
    | { type: "error"; message: string }
    | null
  >(null);

  const grouped = useMemo(() => groupSlotsByDay(data?.slots ?? []), [data?.slots]);

  async function onConfirm() {
    if (!selected || !token) return;
    setConfirm(null);
    try {
      const r = await book.mutateAsync({
        token,
        start: selected.start,
        end: selected.end,
      });
      if (!r.ok) {
        setConfirm({
          type: "error",
          message: friendlyError(r.error),
        });
        await refetch();
        return;
      }
      setConfirm({
        type: "success",
        message: "Your interview has been scheduled successfully.",
        meet: r.google_meet_link ?? null,
        start: r.selected_start_time ?? selected.start,
        end: r.selected_end_time ?? selected.end,
      });
    } catch (e) {
      setConfirm({
        type: "error",
        message: e instanceof Error ? e.message : "Booking failed.",
      });
    }
  }

  if (isLoading) {
    return (
      <Centered>
        <Loader2 className="h-5 w-5 animate-spin text-primary" />
        <p className="mt-2 text-sm text-muted-foreground">Loading availability…</p>
      </Centered>
    );
  }

  if (isError || !data) {
    return (
      <Centered>
        <XCircle className="h-6 w-6 text-red-400" />
        <p className="mt-2 text-sm text-red-400">
          {friendlyTopError(error instanceof Error ? error.message : "Could not load this scheduling link.")}
        </p>
      </Centered>
    );
  }

  if (data.booked && data.booking) {
    return (
      <PublicShell>
        <SuccessCard
          orgName={data.organization_name}
          jobTitle={data.job_title}
          start={data.booking.selected_start_time}
          end={data.booking.selected_end_time}
          meet={data.booking.google_meet_link}
          tz={data.booking.timezone}
          message="Your interview is already scheduled."
        />
      </PublicShell>
    );
  }

  if (confirm?.type === "success") {
    return (
      <PublicShell>
        <SuccessCard
          orgName={data.organization_name}
          jobTitle={data.job_title}
          start={confirm.start}
          end={confirm.end}
          meet={confirm.meet}
          tz={data.timezone}
          message={confirm.message}
        />
      </PublicShell>
    );
  }

  return (
    <PublicShell>
      <Header
        orgName={data.organization_name}
        jobTitle={data.job_title}
        candidateName={data.candidate_name}
        interviewType={data.interview_type}
        durationMinutes={data.duration_minutes}
        timezone={data.timezone}
      />

      {confirm?.type === "error" && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-[13px] text-red-300">
          {confirm.message}
        </div>
      )}

      {data.slots.length === 0 ? (
        <div className="rounded-xl border border-border/40 bg-muted/20 p-6 text-center text-sm text-muted-foreground">
          No availability has been published for this invitation. Please reply to the
          email or wait for the recruiter to share new times.
        </div>
      ) : (
        <div className="space-y-5">
          {grouped.map((day) => (
            <div key={day.label}>
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                {day.label}
              </p>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
                {day.slots.map((s) => {
                  const active = selected?.start === s.start && selected?.end === s.end;
                  return (
                    <button
                      key={s.start}
                      type="button"
                      onClick={() => setSelected({ start: s.start, end: s.end })}
                      className={cn(
                        "rounded-lg border px-3 py-2 text-sm transition",
                        active
                          ? "border-primary/60 bg-primary/15 text-foreground"
                          : "border-border/50 bg-muted/20 text-muted-foreground hover:bg-muted/40 hover:text-foreground",
                      )}
                    >
                      {formatTime(s.start, data.timezone)}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {selected && (
        <div className="sticky bottom-0 mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/40 bg-background/95 p-3 backdrop-blur">
          <div className="text-sm">
            <span className="text-muted-foreground">Selected: </span>
            <span className="font-medium">{formatLong(selected.start, data.timezone)}</span>
          </div>
          <Button onClick={() => void onConfirm()} disabled={book.isPending}>
            {book.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <CalendarIcon className="h-3 w-3" />}
            Confirm slot
          </Button>
        </div>
      )}
    </PublicShell>
  );
}

// ── Layout helpers ────────────────────────────────────────────────────────

function PublicShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background px-4 py-8">
      <div className="mx-auto max-w-2xl space-y-5">{children}</div>
    </div>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="flex flex-col items-center text-center">{children}</div>
    </div>
  );
}

function Header(props: {
  orgName: string | null;
  jobTitle: string | null;
  candidateName: string | null;
  interviewType: string | null;
  durationMinutes: number;
  timezone: string;
}) {
  return (
    <div className="rounded-2xl border border-border/40 bg-muted/10 p-5">
      <p className="text-[11px] uppercase tracking-widest text-primary">Schedule your interview</p>
      <h1 className="mt-1 text-2xl font-semibold">
        {props.candidateName ? `Hi ${props.candidateName.split(" ")[0]}` : "Hello"}
      </h1>
      <div className="mt-3 grid grid-cols-1 gap-2 text-[13px] text-muted-foreground sm:grid-cols-2">
        {props.orgName && (
          <span className="inline-flex items-center gap-2">
            <Building2 className="h-3.5 w-3.5" /> {props.orgName}
          </span>
        )}
        {props.jobTitle && (
          <span className="inline-flex items-center gap-2">
            <Briefcase className="h-3.5 w-3.5" /> {props.jobTitle}
          </span>
        )}
        <span className="inline-flex items-center gap-2">
          <Clock className="h-3.5 w-3.5" /> {props.durationMinutes} minutes
          {props.interviewType ? ` · ${props.interviewType}` : ""}
        </span>
        <span className="inline-flex items-center gap-2">
          <Globe className="h-3.5 w-3.5" /> {props.timezone}
        </span>
      </div>
    </div>
  );
}

function SuccessCard(props: {
  orgName: string | null;
  jobTitle: string | null;
  start: string;
  end: string;
  meet: string | null;
  tz: string;
  message: string;
}) {
  return (
    <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/5 p-6">
      <div className="flex items-center gap-2 text-emerald-300">
        <CheckCircle2 className="h-5 w-5" />
        <p className="text-sm font-semibold">{props.message}</p>
      </div>
      <p className="mt-3 text-base font-semibold text-foreground">
        {formatLong(props.start, props.tz)}
      </p>
      <p className="text-[12px] text-muted-foreground">
        {props.orgName ?? ""}
        {props.jobTitle ? ` · ${props.jobTitle}` : ""}
      </p>
      {props.meet && (
        <a
          href={props.meet}
          target="_blank"
          rel="noreferrer"
          className="mt-4 inline-flex items-center gap-2 rounded-lg border border-primary/40 bg-primary/10 px-3 py-2 text-sm text-primary hover:bg-primary/20"
        >
          Join with Google Meet
        </a>
      )}
      <p className="mt-3 text-[11px] text-muted-foreground">
        A calendar invite has been sent to your email if Google Calendar is connected on the recruiter side.
      </p>
    </div>
  );
}

// ── Formatting + grouping ─────────────────────────────────────────────────

type SlotDay = { label: string; slots: { start: string; end: string }[] };

function groupSlotsByDay(slots: { start: string; end: string }[]): SlotDay[] {
  const map = new Map<string, SlotDay>();
  for (const s of slots) {
    const d = new Date(s.start);
    const key = d.toISOString().slice(0, 10);
    const label = d.toLocaleDateString(undefined, {
      weekday: "long",
      month: "short",
      day: "numeric",
    });
    if (!map.has(key)) map.set(key, { label, slots: [] });
    map.get(key)!.slots.push({ start: s.start, end: s.end });
  }
  return [...map.values()].sort((a, b) =>
    a.slots[0].start.localeCompare(b.slots[0].start),
  );
}

function formatTime(iso: string, _tz: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function formatLong(iso: string, _tz: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    weekday: "long",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function friendlyError(error: string | null): string {
  switch (error) {
    case "token_not_found":
      return "This link is no longer valid.";
    case "token_expired":
      return "This scheduling link has expired. Please ask the recruiter to send a new one.";
    case "already_booked":
      return "This invitation has already been booked.";
    case "slot_not_available":
      return "That slot was just taken. Please pick another one.";
    case "invalid_slot_format":
    case "invalid_slot_range":
      return "Invalid slot. Please try again.";
    default:
      return error ?? "Booking failed.";
  }
}

function friendlyTopError(message: string): string {
  if (/token_not_found/i.test(message)) return "This scheduling link is invalid or no longer active.";
  if (/token_expired/i.test(message)) return "This scheduling link has expired.";
  if (/session_cancelled/i.test(message)) return "This interview invitation has been cancelled.";
  return message;
}

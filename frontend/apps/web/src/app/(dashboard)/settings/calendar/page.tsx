"use client";

/**
 * Calendar Integration settings page.
 *
 * Connects the company workspace to Google Calendar for automated interview
 * scheduling. The page is intentionally honest about its state:
 *
 *   1. If the backend endpoint /api/v1/google-integration/status is missing
 *      (current default after the May 7 sync), the page surfaces this as a
 *      "Calendar backend not available" warning rather than pretending to be
 *      connected. No fake data is displayed.
 *
 *   2. If the endpoint exists but `configured === false`, the page prints
 *      the exact env vars the backend operator needs to set
 *      (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_CALENDAR_ID /
 *      GOOGLE_REDIRECT_URI).
 *
 *   3. If the endpoint exists and `configured === true` but the org has not
 *      yet connected, the user can click Connect, which redirects them
 *      through Google's OAuth consent screen.
 *
 *   4. If the org is already connected, real connection metadata is shown
 *      (account email, scopes, token expiry, last error if any).
 *
 * Manual interview creation in /interviews continues to work in every state;
 * Google Calendar only auto-creates events when fully connected.
 */

import { useState } from "react";
import { motion } from "framer-motion";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CalendarClock, CheckCircle2, AlertTriangle, Loader2,
  Plug, Unplug, Info, ShieldAlert, ExternalLink, Mail,
} from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { googleIntegrationApi } from "@/lib/api";

const REQUIRED_ENV_VARS = [
  "GOOGLE_CLIENT_ID",
  "GOOGLE_CLIENT_SECRET",
  "GOOGLE_CALENDAR_ID",
  "GOOGLE_REDIRECT_URI",
];

function StatusPill({
  tone,
  label,
}: {
  tone: "ok" | "warn" | "error" | "neutral";
  label: string;
}) {
  const cls = {
    ok: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    warn: "bg-amber-500/10 text-amber-400 border-amber-500/30",
    error: "bg-red-500/10 text-red-400 border-red-500/30",
    neutral: "bg-muted/30 text-muted-foreground border-border/40",
  }[tone];
  return (
    <Badge variant="outline" className={`text-[10px] ${cls}`}>
      {label}
    </Badge>
  );
}

export default function CalendarSettingsPage() {
  const qc = useQueryClient();
  const [connectErr, setConnectErr] = useState<string | null>(null);

  const status = useQuery({
    queryKey: ["google-integration", "status"],
    queryFn: googleIntegrationApi.status,
    retry: false,
    refetchOnWindowFocus: false,
  });

  const disconnect = useMutation({
    mutationFn: () => googleIntegrationApi.disconnect(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["google-integration"] });
    },
  });

  const handleConnect = async () => {
    setConnectErr(null);
    try {
      const result = await googleIntegrationApi.connect();
      if (result?.authorize_url) {
        window.location.href = result.authorize_url;
      } else {
        setConnectErr(
          "Backend did not return an authorize URL. Check Google OAuth configuration.",
        );
      }
    } catch (e) {
      setConnectErr(
        e instanceof Error
          ? e.message
          : "Could not start the Google OAuth flow.",
      );
    }
  };

  // ── Derive UI state from query result ─────────────────────────────────
  // The endpoint may be (a) entirely missing on the backend, (b) present
  // but with the integration not configured, (c) configured but not yet
  // connected for this org, or (d) connected.
  const isLoading = status.isLoading;
  const fetchError = status.isError ? status.error : null;
  const data = status.data;

  // Treat any network/4xx error as "endpoint not available." The api client
  // throws on non-2xx, so any thrown error here means we should surface the
  // honest backend-missing state rather than guessing.
  const backendUnavailable = !!fetchError;
  const configured = !!data?.configured;
  const connected = !!data?.connected;
  const hasError = !!data?.last_error;

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6 max-w-4xl">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-3"
      >
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
          <CalendarClock className="h-5 w-5 text-primary" />
        </div>
        <div>
          <h1 className="font-heading text-xl font-bold tracking-tight text-foreground">
            Calendar Integration
          </h1>
          <p className="text-sm text-muted-foreground">
            Connect Google Calendar to automate interview scheduling and
            availability checks.
          </p>
        </div>
      </motion.div>

      {/* Loading */}
      {isLoading && (
        <div className="glass rounded-2xl p-6 flex items-center gap-3 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Checking calendar
          status…
        </div>
      )}

      {/* (a) Backend endpoint missing entirely */}
      {!isLoading && backendUnavailable && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass rounded-2xl p-6 space-y-4 border border-amber-500/30 bg-amber-500/5"
        >
          <div className="flex items-center gap-3">
            <AlertTriangle className="h-5 w-5 text-amber-400" />
            <h2 className="text-base font-semibold text-foreground">
              Calendar backend not available
            </h2>
            <StatusPill tone="warn" label="Backend missing" />
          </div>
          <p className="text-sm text-muted-foreground">
            The endpoint{" "}
            <code className="font-mono text-xs bg-muted/50 px-1.5 py-0.5 rounded">
              /api/v1/google-integration/status
            </code>{" "}
            did not respond. Google Calendar features (auto-scheduling,
            availability checks, calendar event creation) cannot work until
            the backend integration is mounted.
          </p>
          <div className="rounded-lg border border-border/40 bg-muted/10 p-4 space-y-2">
            <p className="text-xs font-semibold text-foreground">
              Required environment variables (set on the backend)
            </p>
            <ul className="space-y-1 text-xs text-muted-foreground font-mono">
              {REQUIRED_ENV_VARS.map((v) => (
                <li key={v}>• {v}</li>
              ))}
            </ul>
          </div>
          <p className="text-[11px] text-muted-foreground">
            Until calendar is restored, interviews can still be created
            manually from{" "}
            <Link href="/interviews" className="text-primary hover:underline">
              Interviews
            </Link>
            . Recruiters will need to send calendar invites outside the
            platform.
          </p>
        </motion.div>
      )}

      {/* (b) Endpoint present but not configured */}
      {!isLoading && !backendUnavailable && !configured && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass rounded-2xl p-6 space-y-4 border border-amber-500/30 bg-amber-500/5"
        >
          <div className="flex items-center gap-3">
            <ShieldAlert className="h-5 w-5 text-amber-400" />
            <h2 className="text-base font-semibold text-foreground">
              Google Calendar is not configured
            </h2>
            <StatusPill tone="warn" label="Not configured" />
          </div>
          <p className="text-sm text-muted-foreground">
            The backend reports{" "}
            <code className="font-mono text-xs bg-muted/50 px-1 rounded">
              configured: false
            </code>
            . The Google integration cannot start an OAuth flow until the
            following environment variables are set:
          </p>
          <ul className="space-y-1 text-xs text-muted-foreground font-mono">
            {REQUIRED_ENV_VARS.map((v) => (
              <li key={v}>• {v}</li>
            ))}
          </ul>
        </motion.div>
      )}

      {/* (c) Configured but not connected for this org */}
      {!isLoading && !backendUnavailable && configured && !connected && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass rounded-2xl p-6 space-y-4"
        >
          <div className="flex items-center gap-3">
            <CalendarClock className="h-5 w-5 text-primary" />
            <h2 className="text-base font-semibold text-foreground">
              Connect your Google Calendar
            </h2>
            <StatusPill tone="neutral" label="Not connected" />
          </div>
          <p className="text-sm text-muted-foreground">
            We will redirect you to Google&apos;s consent screen. The
            integration requests read access to your interviewers&apos;
            primary calendars and write access to create interview events.
          </p>
          <div className="flex items-center gap-3">
            <Button
              size="sm"
              onClick={handleConnect}
              className="gap-2"
              disabled={status.isFetching}
            >
              <Plug className="h-3.5 w-3.5" /> Connect Google Calendar
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => status.refetch()}
              disabled={status.isFetching}
            >
              {status.isFetching ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : null}
              Refresh status
            </Button>
          </div>
          {connectErr && (
            <p className="text-xs text-red-400">{connectErr}</p>
          )}
        </motion.div>
      )}

      {/* (d) Connected */}
      {!isLoading && !backendUnavailable && configured && connected && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass rounded-2xl p-6 space-y-4 border border-emerald-500/30 bg-emerald-500/5"
        >
          <div className="flex items-center gap-3">
            <CheckCircle2 className="h-5 w-5 text-emerald-400" />
            <h2 className="text-base font-semibold text-foreground">
              Connected
            </h2>
            <StatusPill tone="ok" label="Active" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="glass rounded-xl p-4 space-y-1">
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
                Account
              </p>
              <p className="flex items-center gap-2 text-sm font-medium text-foreground truncate">
                <Mail className="h-3.5 w-3.5 text-muted-foreground" />
                {data?.email ?? "—"}
              </p>
            </div>
            <div className="glass rounded-xl p-4 space-y-1">
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
                Token expires
              </p>
              <p className="text-sm text-foreground">
                {data?.expires_at
                  ? new Date(data.expires_at).toLocaleString()
                  : "—"}
              </p>
            </div>
            <div className="glass rounded-xl p-4 space-y-1 sm:col-span-2">
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
                Granted scopes
              </p>
              {data?.scopes && data.scopes.length > 0 ? (
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {data.scopes.map((s) => (
                    <code
                      key={s}
                      className="text-[10px] font-mono bg-muted/40 text-muted-foreground px-1.5 py-0.5 rounded"
                    >
                      {s}
                    </code>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">—</p>
              )}
            </div>
            {hasError && (
              <div className="glass rounded-xl p-4 space-y-1 sm:col-span-2 border border-red-500/30 bg-red-500/5">
                <p className="text-[11px] uppercase tracking-wider text-red-400 flex items-center gap-1">
                  <AlertTriangle className="h-3 w-3" /> Last error
                </p>
                <p className="text-xs text-muted-foreground">
                  {data?.last_error}
                </p>
              </div>
            )}
          </div>
          <div className="flex items-center gap-3 pt-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => disconnect.mutate()}
              disabled={disconnect.isPending}
              className="gap-2"
            >
              {disconnect.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Unplug className="h-3.5 w-3.5" />
              )}
              Disconnect
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => status.refetch()}
              disabled={status.isFetching}
            >
              {status.isFetching ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : null}
              Refresh
            </Button>
          </div>
        </motion.div>
      )}

      {/* How it works */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="glass rounded-xl p-6 space-y-3"
      >
        <div className="flex items-center gap-2">
          <Info className="h-4 w-4 text-primary" />
          <h2 className="text-sm font-semibold uppercase tracking-wider text-foreground">
            How calendar scheduling works
          </h2>
        </div>
        <ol className="space-y-2 text-xs text-muted-foreground list-decimal list-inside">
          <li>
            A recruiter or hiring manager picks a candidate + interview from{" "}
            <Link href="/interviews" className="text-primary hover:underline">
              /interviews
            </Link>
            .
          </li>
          <li>
            The platform queries Google Calendar for interviewer availability
            in the requested window.
          </li>
          <li>
            The candidate receives a public booking link with the available
            slots (no PATHS account required).
          </li>
          <li>The candidate selects a slot.</li>
          <li>
            The platform creates the Google Calendar event and emails invites
            to candidate + interviewers.
          </li>
          <li>
            Interview status updates in PATHS and the event appears under
            upcoming interviews.
          </li>
        </ol>
        <p className="text-[11px] text-muted-foreground/70 pt-2">
          Calendar events are created with a Google Meet link by default. The
          public booking link is signed with a one-time token and only works
          for the candidate it was issued to.
        </p>
      </motion.div>

      {/* Help link */}
      <p className="text-xs text-muted-foreground">
        Need help? See{" "}
        <a
          href="https://developers.google.com/calendar/api/guides/auth"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline inline-flex items-center gap-1"
        >
          Google Calendar API auth docs
          <ExternalLink className="h-3 w-3" />
        </a>
        .
      </p>
    </div>
  );
}

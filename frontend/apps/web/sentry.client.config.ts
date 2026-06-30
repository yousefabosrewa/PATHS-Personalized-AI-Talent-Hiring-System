/**
 * Sentry browser-side initialisation — PATHS-178
 *
 * This file is imported automatically by @sentry/nextjs when
 * NEXT_PUBLIC_SENTRY_DSN is set.  Leave the DSN empty in local dev to
 * keep the bundle lean and avoid noise in the Sentry project.
 *
 * Session Replay is deliberately disabled (replaysSessionSampleRate = 0)
 * because PATHS processes candidate CVs and interview transcripts —
 * recording sessions would be a GDPR liability.
 */

import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,

  // Capture 10 % of traces for performance monitoring.
  // Raise to 1.0 temporarily if you need to diagnose a specific slowness.
  tracesSampleRate: Number(process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE ?? 0.1),

  // Release is set by CI to the short git SHA (e.g. "abc1234").
  // Source maps are uploaded against this release so stack traces are
  // de-minified automatically.
  release: process.env.NEXT_PUBLIC_APP_VERSION,

  environment: process.env.NODE_ENV,

  // No session replay — GDPR risk with candidate data.
  replaysSessionSampleRate: 0,
  replaysOnErrorSampleRate: 0,

  // Propagate trace headers to the PATHS backend so a single correlation
  // ID links the Next.js span to the FastAPI correlation_id log field.
  tracePropagationTargets: [
    "localhost",
    /^https:\/\/api\.paths\.ai/,
  ],

  // Do not send PII automatically inferred by Sentry.
  sendDefaultPii: false,

  // Silence noisy, unactionable errors from browser extensions etc.
  ignoreErrors: [
    "ResizeObserver loop limit exceeded",
    "ResizeObserver loop completed with undelivered notifications",
    /^Network Error$/,
    /^Load failed$/,
  ],

  beforeSend(event) {
    // Strip any URL query-params that might carry auth tokens
    if (event.request?.url) {
      try {
        const url = new URL(event.request.url);
        ["token", "access_token", "refresh_token", "code"].forEach((p) =>
          url.searchParams.delete(p)
        );
        event.request.url = url.toString();
      } catch {
        // URL parse failed — leave as-is
      }
    }
    return event;
  },
});

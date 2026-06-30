/**
 * Sentry Edge Runtime initialisation — PATHS-178
 *
 * Loaded via src/instrumentation.ts when NEXT_RUNTIME === "edge".
 * Used by middleware and any edge API routes.
 */

import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  tracesSampleRate: Number(process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE ?? 0.1),
  release: process.env.NEXT_PUBLIC_APP_VERSION,
  environment: process.env.NODE_ENV,
  sendDefaultPii: false,
});

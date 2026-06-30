/**
 * Next.js Instrumentation hook — PATHS-178
 *
 * This file is the single entry point for all server-side telemetry.
 * Next.js calls `register()` once per worker process before any routes
 * are served.  It delegates to the correct Sentry config based on the
 * current runtime environment.
 *
 * @see https://nextjs.org/docs/app/building-your-application/optimizing/instrumentation
 */

export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("../sentry.server.config");
  }

  if (process.env.NEXT_RUNTIME === "edge") {
    await import("../sentry.edge.config");
  }
}

/**
 * Sentry `onRequestError` hook — surfaces unhandled server errors to Sentry
 * with the full request context (route, method, status).
 *
 * Only available in Next.js 15+.  Safely ignored on earlier versions.
 */
export const onRequestError = async (
  ...args: Parameters<typeof import("@sentry/nextjs").captureRequestError>
) => {
  const { captureRequestError } = await import("@sentry/nextjs");
  captureRequestError(...args);
};

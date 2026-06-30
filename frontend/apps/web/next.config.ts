/**
 * Next.js configuration — PATHS
 *
 * Wrapped with @sentry/nextjs when the package is installed (PATHS-178).
 * If the package isn't present (e.g. fresh checkout before `pnpm install`)
 * the plain config is exported so `next dev` still works.
 */

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",

  // Next.js 16 builds with Turbopack by default. When @sentry/nextjs is
  // installed (as it is in a full `pnpm install`, e.g. the Docker image) its
  // wrapper injects a `webpack` config, and Turbopack then refuses to build
  // unless a `turbopack` config is also present. An empty object is the
  // officially-recommended acknowledgement — see the Next 16 build error:
  // "setting an empty turbopack config in your Next config file (turbopack: {})".
  turbopack: {},

  // Expose the git SHA to the browser bundle so Sentry can link errors to
  // the correct release.  Set NEXT_PUBLIC_APP_VERSION=<sha> in CI.
  env: {
    NEXT_PUBLIC_APP_VERSION: process.env.NEXT_PUBLIC_APP_VERSION ?? "local",
  },
};

// Wrap with Sentry only when the package is available.
// Run `pnpm install` once to enable source-map upload and SDK instrumentation.
let finalConfig: NextConfig = nextConfig;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { withSentryConfig } = require("@sentry/nextjs");
  finalConfig = withSentryConfig(nextConfig, {
    silent: !process.env.CI,
    org: process.env.SENTRY_ORG,
    project: process.env.SENTRY_PROJECT,
    widenClientFileUpload: true,
    hideSourceMaps: true,
    disableLogger: true,
    automaticVercelMonitors: false,
    tunnelRoute: undefined,
  });
} catch {
  // @sentry/nextjs not installed — run `pnpm install` to enable it
}

export default finalConfig;

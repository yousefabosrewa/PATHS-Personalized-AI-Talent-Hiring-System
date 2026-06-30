/**
 * PATHS Status Page — PATHS-185
 *
 * Shows real-time platform health by polling the backend health endpoint.
 * Refreshes every 30 seconds so users can monitor ongoing incidents.
 *
 * Route: /status
 */

import type { Metadata } from "next";
import { StatusPageClient } from "./StatusPageClient";

export const metadata: Metadata = {
  title: "Platform Status — PATHS",
  description: "Real-time status of the PATHS platform services.",
};

// Revalidate every 30 s so CDN caches stay fresh without full SSR every hit.
export const revalidate = 30;

export default function StatusPage() {
  return <StatusPageClient />;
}

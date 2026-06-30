import type { MetadataRoute } from "next";

const BASE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://paths.app";
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

/**
 * PATHS dynamic sitemap.
 *
 * Covers:
 * - Static marketing routes
 * - Auth routes (low priority, noindex in robots)
 * - All published public jobs (fetched at build / ISR time)
 *
 * PATHS-131 (Phase 6)
 */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date().toISOString();

  // ── Static routes ─────────────────────────────────────────────────────
  const staticRoutes: MetadataRoute.Sitemap = [
    { url: BASE, lastModified: now, changeFrequency: "weekly", priority: 1.0 },
    { url: `${BASE}/pricing`, lastModified: now, changeFrequency: "weekly", priority: 0.9 },
    { url: `${BASE}/jobs`, lastModified: now, changeFrequency: "daily", priority: 0.9 },
    { url: `${BASE}/for-companies`, lastModified: now, changeFrequency: "monthly", priority: 0.7 },
    { url: `${BASE}/for-candidates`, lastModified: now, changeFrequency: "monthly", priority: 0.7 },
    { url: `${BASE}/for-recruiters`, lastModified: now, changeFrequency: "monthly", priority: 0.6 },
    { url: `${BASE}/how-it-works`, lastModified: now, changeFrequency: "monthly", priority: 0.6 },
    { url: `${BASE}/product`, lastModified: now, changeFrequency: "monthly", priority: 0.5 },
  ];

  // ── Dynamic: public job listings ──────────────────────────────────────
  let jobRoutes: MetadataRoute.Sitemap = [];
  try {
    const res = await fetch(`${API}/api/v1/public/jobs?page_size=500`, {
      next: { revalidate: 3600 }, // ISR — re-generate hourly
    });
    if (res.ok) {
      const jobs: Array<{ slug: string; date_posted: string | null }> = await res.json();
      jobRoutes = jobs.map((job) => ({
        url: `${BASE}/jobs/${job.slug}`,
        lastModified: job.date_posted ?? now,
        changeFrequency: "weekly" as const,
        priority: 0.8,
      }));
    }
  } catch {
    // Silently skip — sitemap without dynamic jobs is still valid
  }

  return [...staticRoutes, ...jobRoutes];
}

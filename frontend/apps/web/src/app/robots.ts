import type { MetadataRoute } from "next";

const BASE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://paths.app";

/**
 * PATHS robots.txt generation.
 *
 * - Allow all crawlers on public marketing + job board routes.
 * - Block dashboard, admin, candidate-portal, and auth routes from crawlers.
 * - Block the API origin.
 *
 * PATHS-131 (Phase 6)
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: [
          "/",
          "/pricing",
          "/jobs",
          "/jobs/",
          "/for-companies",
          "/for-candidates",
          "/for-recruiters",
          "/how-it-works",
          "/product",
        ],
        disallow: [
          // Auth pages — no SEO value
          "/login",
          "/company-signup",
          "/candidate-signup",
          "/forgot-password",
          "/reset-password/",
          "/pending-approval",
          "/rejected",
          // Internal app routes
          "/dashboard",
          "/jobs/new",
          "/billing",
          "/settings",
          "/approvals",
          "/audit",
          "/sourcing",
          "/outreach",
          "/reports",
          "/org/",
          "/interviews/",
          "/onboarding/",
          // Candidate portal (auth-gated)
          "/candidate/",
          // Admin portals
          "/admin/",
          "/owner/",
          // Health + debug
          "/health",
          "/_health",
          "/api/",
        ],
      },
    ],
    sitemap: `${BASE}/sitemap.xml`,
    host: BASE,
  };
}

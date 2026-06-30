/**
 * PATHS — Owner portal API client.
 *
 * Wraps the /api/v1/owner/* endpoints. Requires account_type='platform_admin'
 * (owner role). Backend enforces this server-side.
 *
 * PATHS-149–152 (Phase 7 — Admin & Owner Portals)
 */

import { api } from "./client";

// ── Types ────────────────────────────────────────────────────────────────────

export interface OwnerRevenueSummary {
  mrr_cents: number;
  arr_cents: number;
  churn_rate_30d: number;
  new_orgs_this_month: number;
  new_orgs_last_month: number;
  active_seats_used: number;
  revenue_by_plan: { plan: string; cents: number; pct: number }[];
  top_customers: { org_id: string; name: string; mrr_cents?: number; plan?: string }[];
  alerts: { kind: string; org_id: string; message: string }[];
}

export interface OwnerRevenuePoint {
  date: string | null;
  amount_cents: number;
  currency: string;
}

export interface OwnerCustomer {
  org_id: string;
  name: string;
  status: string;
  plan: string | null;
  health_score: number;
  created_at: string | null;
}

export interface OwnerOrg {
  id: string;
  name: string;
  slug: string;
  status: string;
  created_at: string | null;
}

export interface OwnerPlan {
  id: string;
  name: string;
  code: string;
  price_monthly_cents: number;
  price_annual_cents: number;
  currency: string;
  limits: Record<string, unknown>;
  features: string[];
  is_public: boolean;
}

export interface OwnerPlatformConfig {
  display_name: string;
  support_email: string | null;
  legal_company_name: string | null;
  maintenance_mode: boolean;
  email_templates: Record<string, unknown>;
}

export interface OwnerMarketingAnalytics {
  sessions: number;
  signups: number;
  conversions: number;
  by_utm_source: { source: string; sessions: number; signups: number }[];
}

export interface OwnerAnnouncement {
  id: string;
  content: string;
  in_app_banner_enabled: boolean;
  banner_color: string;
  sent_at: string | null;
  created_at: string;
}

// ── API ───────────────────────────────────────────────────────────────────────

export const ownerApi = {
  // Revenue
  revenueSummary: () => api.get<OwnerRevenueSummary>("/api/v1/owner/revenue-summary"),
  revenueAnalytics: (params?: { from?: string; to?: string }) => {
    const qs = new URLSearchParams();
    if (params?.from) qs.set("from", params.from);
    if (params?.to) qs.set("to", params.to);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return api.get<OwnerRevenuePoint[]>(`/api/v1/owner/analytics/revenue${suffix}`);
  },

  // Customers + orgs
  listCustomers: (params?: { health?: string; plan?: string }) => {
    const qs = new URLSearchParams();
    if (params?.health) qs.set("health", params.health);
    if (params?.plan) qs.set("plan", params.plan);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return api.get<OwnerCustomer[]>(`/api/v1/owner/customers${suffix}`);
  },
  listOrgs: (params?: { q?: string; plan?: string }) => {
    const qs = new URLSearchParams();
    if (params?.q) qs.set("q", params.q);
    if (params?.plan) qs.set("plan", params.plan);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return api.get<OwnerOrg[]>(`/api/v1/owner/orgs${suffix}`);
  },

  // Plans
  listPlans: () => api.get<OwnerPlan[]>("/api/v1/owner/plans"),
  createPlan: (data: Omit<OwnerPlan, "id">) =>
    api.post<{ id: string; code: string }>("/api/v1/owner/plans", data),
  updatePlan: (id: string, data: Partial<OwnerPlan>) =>
    api.put<{ id: string; code: string }>(`/api/v1/owner/plans/${id}`, data),

  // Platform config
  getPlatformConfig: () => api.get<OwnerPlatformConfig>("/api/v1/owner/platform-config"),
  updatePlatformConfig: (data: Partial<OwnerPlatformConfig>) =>
    api.put<{ status: string }>("/api/v1/owner/platform-config", data),

  // Marketing analytics
  marketingAnalytics: () =>
    api.get<OwnerMarketingAnalytics>("/api/v1/owner/analytics/marketing"),

  // Announcements
  listAnnouncements: () => api.get<OwnerAnnouncement[]>("/api/v1/owner/announcements"),
  createAnnouncement: (data: {
    content: string;
    audience?: Record<string, unknown>;
    in_app_banner_enabled?: boolean;
    banner_color?: string;
    scheduled_at?: string | null;
  }) => api.post<{ id: string; status: string }>("/api/v1/owner/announcements", data),
};

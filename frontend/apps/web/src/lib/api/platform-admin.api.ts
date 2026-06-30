/**
 * PATHS — Platform admin API client.
 *
 * Wraps the /api/v1/admin/* endpoints. Every call requires the user to have
 * account_type='platform_admin' on the backend; the backend enforces this
 * server-side so a non-admin caller will receive 403 even with a valid JWT.
 */

import { api } from "./client";

// ── Backend response types ───────────────────────────────────────────────

export interface AdminOrgRequestRow {
  id: string;
  organization_id: string;
  organization_name: string;
  organization_slug: string;
  requester_user_id: string;
  requester_name: string;
  requester_email: string;
  contact_role: string | null;
  contact_phone: string | null;
  status: "pending" | "approved" | "rejected";
  submitted_at: string;
  reviewed_at: string | null;
  rejection_reason: string | null;
}

export interface AdminOrgRequestDetail extends AdminOrgRequestRow {
  organization_industry: string | null;
  organization_contact_email: string | null;
  additional_info: string | null;
}

export interface AdminOrgRow {
  id: string;
  name: string;
  slug: string;
  status: "pending_approval" | "active" | "rejected" | "suspended";
  is_active: boolean;
  industry: string | null;
  contact_email: string | null;
  member_count: number;
  created_at: string;
}

export interface AdminUserRow {
  id: string;
  email: string;
  full_name: string;
  account_type: string;
  is_active: boolean;
  created_at: string;
}

export interface AdminAuditRow {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  actor_user_id: string | null;
  created_at: string;
}

export interface AdminDashboardStats {
  pending_requests: number;
  approved_requests: number;
  rejected_requests: number;
  total_organizations: number;
  active_organizations: number;
  suspended_organizations: number;
  total_users: number;
  candidates: number;
  organization_members: number;
  platform_admins: number;
}

export interface AdminPlatformStats {
  total_orgs: number;
  active_orgs: number;
  pending_orgs: number;
  total_candidates: number;
  total_jobs: number;
  total_users: number;
  total_agent_runs: number;
  failed_agent_runs: number;
}

export interface AdminOrgDossier {
  id: string;
  name: string;
  slug: string;
  status: string;
  industry: string | null;
  contact_email: string | null;
  created_at: string | null;
  health_score: number;
  subscription: {
    plan: string | null;
    status: string | null;
    billing_cycle: string | null;
  } | null;
  members: {
    user_id: string;
    email: string;
    full_name: string;
    role_code: string;
    is_active: boolean;
  }[];
  recent_jobs: {
    id: string;
    title: string;
    status: string;
    created_at: string | null;
  }[];
}

export interface ImpersonationResult {
  access_token: string;
  token_type: string;
  expires_in: number;
  impersonation_session_id: string;
  target_user_email: string;
  target_org?: string;
}

export interface AdminAgentRun {
  id: string;
  organization_id: string;
  run_type: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  current_node: string | null;
  triggered_by: string | null;
  entity_type: string | null;
  entity_id: string | null;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string | null;
}

export interface AdminSystemHealth {
  overall: "healthy" | "degraded";
  services: {
    postgres: Record<string, unknown>;
    apache_age: Record<string, unknown>;
    qdrant: Record<string, unknown>;
    ollama: Record<string, unknown>;
  };
  agent_runs_failed_24h: number;
  checked_at: string;
}

export interface AdminFeatureFlagOverride {
  org_id: string;
  enabled: boolean;
  set_at: string;
}

export interface AdminFeatureFlag {
  id: string;
  code: string;
  description: string | null;
  enabled: boolean;
  created_at: string;
  overrides: AdminFeatureFlagOverride[];
}

export interface AdminPlatformSettings {
  display_name: string;
  support_email: string | null;
  legal_company_name: string | null;
  maintenance_mode: boolean;
  email_templates: Record<string, unknown>;
  updated_at: string | null;
}

// ── API surface ──────────────────────────────────────────────────────────

export const platformAdminApi = {
  // Dashboard
  dashboardStats: () =>
    api.get<AdminDashboardStats>("/api/v1/admin/dashboard-stats"),

  // Organisation access requests
  listRequests: (params?: { status?: string; q?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.q) qs.set("q", params.q);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return api.get<AdminOrgRequestRow[]>(`/api/v1/admin/organization-requests${suffix}`);
  },
  getRequest: (id: string) =>
    api.get<AdminOrgRequestDetail>(`/api/v1/admin/organization-requests/${id}`),
  approveRequest: (id: string) =>
    api.post<AdminOrgRequestDetail>(`/api/v1/admin/organization-requests/${id}/approve`),
  rejectRequest: (id: string, reason: string) =>
    api.post<AdminOrgRequestDetail>(
      `/api/v1/admin/organization-requests/${id}/reject`,
      { reason },
    ),

  // Organisations
  listOrganizations: (params?: { status?: string; q?: string }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.q) qs.set("q", params.q);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return api.get<AdminOrgRow[]>(`/api/v1/admin/organizations${suffix}`);
  },
  suspendOrganization: (id: string, reason: string) =>
    api.post<AdminOrgRow>(`/api/v1/admin/organizations/${id}/suspend`, { reason }),
  unsuspendOrganization: (id: string) =>
    api.post<AdminOrgRow>(`/api/v1/admin/organizations/${id}/unsuspend`),

  // Users
  listUsers: (params?: { account_type?: string; q?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.account_type) qs.set("account_type", params.account_type);
    if (params?.q) qs.set("q", params.q);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return api.get<AdminUserRow[]>(`/api/v1/admin/users${suffix}`);
  },

  // Audit feed
  listAudit: (params?: { action_prefix?: string; entity_type?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.action_prefix) qs.set("action_prefix", params.action_prefix);
    if (params?.entity_type) qs.set("entity_type", params.entity_type);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return api.get<AdminAuditRow[]>(`/api/v1/admin/audit${suffix}`);
  },

  // Rich platform stats (PATHS-142)
  platformStats: () => api.get<AdminPlatformStats>("/api/v1/admin/stats"),

  // Org dossier + impersonation (PATHS-143)
  getOrgDossier: (id: string) =>
    api.get<AdminOrgDossier>(`/api/v1/admin/organizations/${id}`),
  impersonateOrg: (id: string, reason: string) =>
    api.post<ImpersonationResult>(`/api/v1/admin/organizations/${id}/impersonate`, { reason }),

  // User suspend + impersonation (PATHS-144)
  suspendUser: (id: string, suspended: boolean) =>
    api.put<{ user_id: string; is_active: boolean }>(`/api/v1/admin/users/${id}/suspend`, { suspended }),
  impersonateUser: (id: string, reason: string) =>
    api.post<ImpersonationResult>(`/api/v1/admin/users/${id}/impersonate`, { reason }),

  // Agent runs (PATHS-145)
  listAgentRuns: (params?: { run_type?: string; status?: string; org_id?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.run_type) qs.set("run_type", params.run_type);
    if (params?.status) qs.set("status", params.status);
    if (params?.org_id) qs.set("org_id", params.org_id);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return api.get<AdminAgentRun[]>(`/api/v1/admin/agent-runs${suffix}`);
  },
  retryAgentRun: (id: string) =>
    api.post<{ id: string; status: string }>(`/api/v1/admin/agent-runs/${id}/retry`),

  // System health (PATHS-146)
  systemHealth: () => api.get<AdminSystemHealth>("/api/v1/admin/system-health"),

  // Feature flags (PATHS-147)
  listFeatureFlags: () => api.get<AdminFeatureFlag[]>("/api/v1/admin/feature-flags"),
  createFeatureFlag: (data: { code: string; description?: string; enabled?: boolean }) =>
    api.post<{ id: string; code: string; enabled: boolean }>("/api/v1/admin/feature-flags", data),
  updateFeatureFlag: (id: string, data: { enabled: boolean; description?: string }) =>
    api.put<{ id: string; code: string; enabled: boolean }>(`/api/v1/admin/feature-flags/${id}`, data),
  upsertFlagOrgOverride: (flagId: string, orgId: string, enabled: boolean) =>
    api.post<{ flag_id: string; org_id: string; enabled: boolean }>(
      `/api/v1/admin/feature-flags/${flagId}/org-override`,
      { org_id: orgId, enabled },
    ),

  // Platform settings (PATHS-148)
  getPlatformSettings: () => api.get<AdminPlatformSettings>("/api/v1/admin/settings"),
  updatePlatformSettings: (data: Partial<AdminPlatformSettings>) =>
    api.put<{ status: string }>("/api/v1/admin/settings", data),
};

/**
 * Auth API calls — wraps the backend /api/v1/auth/* endpoints.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

export interface BackendUser {
  id: string;
  email: string;
  full_name: string;
  account_type: string;
  is_platform_admin?: boolean;
  organization?: {
    organization_id: string;
    organization_name: string;
    role_code: string;
    status?: string;
  } | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: BackendUser;
}

/** Map backend user shape → frontend User shape */
export function mapBackendUser(backendUser: BackendUser, token: string) {
  const org = backendUser.organization;
  // Map role_code → frontend UserRole enum value
  const roleMap: Record<string, string> = {
    org_admin: "admin",
    recruiter: "recruiter",
    hr: "recruiter",
    hr_manager: "hiring_manager",
    hiring_manager: "hiring_manager",
    interviewer: "interviewer",
    candidate: "candidate",
  };
  let role: string;
  if (backendUser.account_type === "platform_admin" || backendUser.is_platform_admin) {
    role = "super_admin";
  } else if (org) {
    role = roleMap[org.role_code] ?? "recruiter";
  } else if (backendUser.account_type === "candidate") {
    role = "candidate";
  } else {
    role = "recruiter";
  }

  return {
    id: backendUser.id,
    email: backendUser.email,
    name: backendUser.full_name,
    role,
    accountType: backendUser.account_type,
    isPlatformAdmin: !!backendUser.is_platform_admin || backendUser.account_type === "platform_admin",
    organizationStatus: (org?.status as
      | "pending_approval"
      | "active"
      | "rejected"
      | "suspended"
      | undefined) ?? null,
    permissions: [] as string[],
    orgId: org?.organization_id ?? "",
    orgName: org?.organization_name ?? "",
    avatar: `https://api.dicebear.com/9.x/avataaars/svg?seed=${encodeURIComponent(backendUser.email)}`,
    createdAt: new Date().toISOString(),
    lastLogin: new Date().toISOString(),
    mfaEnabled: false,
    status: "active" as const,
    // Store token alongside user for the API client to read
    _token: token,
  };
}

export interface OrganizationRegisterPayload {
  organization_name: string;
  organization_slug: string;
  industry?: string | null;
  organization_email?: string | null;
  company_website?: string | null;
  company_size?: string | null;
  company_type?: string | null;
  first_admin_full_name: string;
  first_admin_email: string;
  first_admin_password: string;
  first_admin_job_title?: string | null;
  first_admin_phone?: string | null;
  accept_terms: boolean;
  confirm_authorized: boolean;
}

export interface OrganizationRegisterResponse {
  organization_id: string;
  user_id: string;
  role_code: string;
  message: string;
}

function formatApiErrorDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e) => (typeof e === "object" && e && "msg" in e ? String((e as { msg: string }).msg) : JSON.stringify(e)))
      .join(". ");
  }
  // Structured errors like account-lockout / rate-limit return an object
  // ({code, message}) — surface the human message instead of "[object Object]".
  if (detail && typeof detail === "object") {
    const o = detail as { message?: unknown; msg?: unknown; detail?: unknown };
    if (typeof o.message === "string") return o.message;
    if (typeof o.msg === "string") return o.msg;
    if (typeof o.detail === "string") return o.detail;
  }
  return "Request failed";
}

export async function registerOrganizationApi(
  payload: OrganizationRegisterPayload,
): Promise<OrganizationRegisterResponse> {
  const res = await fetch(`${BASE_URL}/api/v1/auth/register/organization`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    let detail: unknown = "Registration failed";
    try {
      const err = await res.json();
      detail = err?.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(formatApiErrorDetail(detail));
  }

  return res.json() as Promise<OrganizationRegisterResponse>;
}

export async function loginApi(
  email: string,
  password: string,
): Promise<{ user: ReturnType<typeof mapBackendUser>; token: string }> {
  const res = await fetch(`${BASE_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    let detail: unknown = "Invalid credentials";
    try {
      const err = await res.json();
      detail = err?.detail ?? detail;
    } catch { /* ignore */ }
    throw new Error(formatApiErrorDetail(detail));
  }

  const data: LoginResponse = await res.json();
  return {
    token: data.access_token,
    user: mapBackendUser(data.user, data.access_token),
  };
}

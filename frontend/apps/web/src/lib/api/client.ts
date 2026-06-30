/**
 * PATHS API client — thin fetch wrapper.
 * - Reads NEXT_PUBLIC_API_URL for the base URL.
 * - Attaches Authorization: Bearer <token> from localStorage (paths-auth store).
 * - Throws ApiError on non-2xx responses.
 * - All methods return the parsed JSON body.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

/**
 * Coerce a FastAPI error ``detail`` into a readable string.
 * FastAPI returns ``detail`` as a plain string for HTTPException, but as an
 * array of ``{loc, msg, type}`` objects for 422 validation errors. Passing the
 * array straight into ``new Error()`` renders as "[object Object]", so we
 * flatten validation errors into "field: message" text instead.
 */
export function formatErrorDetail(detail: unknown): string | null {
  if (detail == null) return null;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((d) => {
      if (d && typeof d === "object") {
        const obj = d as { loc?: unknown[]; msg?: unknown };
        const loc = Array.isArray(obj.loc)
          ? obj.loc.filter((p) => p !== "body" && p !== "query").join(".")
          : "";
        const msg = obj.msg != null ? String(obj.msg) : JSON.stringify(d);
        return loc ? `${loc}: ${msg}` : msg;
      }
      return String(d);
    });
    const joined = parts.filter(Boolean).join("; ");
    return joined || null;
  }
  if (typeof detail === "object") {
    const obj = detail as { msg?: unknown; message?: unknown; detail?: unknown };
    if (obj.msg != null) return String(obj.msg);
    if (obj.message != null) return String(obj.message);
    if (typeof obj.detail === "string") return obj.detail;
    try {
      return JSON.stringify(detail);
    } catch {
      return null;
    }
  }
  return String(detail);
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    // Read from the Zustand persist key
    const raw = localStorage.getItem("paths-auth");
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    // Support both stored shapes: { state: { token } } and legacy { state: { user: { _token } } }
    return parsed?.state?.token ?? parsed?.state?.user?._token ?? null;
  } catch {
    return null;
  }
}

/** Rough JWT shape check (three base64url segments). */
function tokenLooksLikeJwt(token: string): boolean {
  const parts = token.split(".");
  if (parts.length !== 3) return false;
  return parts.every((p) => p.length > 0);
}

const DEMO_LOGIN_MSG =
  "This action needs a real backend login. Sign out, then sign in with your organization email and password (the same account registered in PATHS). Demo / mock sessions cannot call protected APIs.";

function pathNeedsRealJwt(path: string): boolean {
  if (!path.startsWith("/api/v1/")) return false;
  if (path.includes("/auth/login")) return false;
  if (
    path.includes("/register/candidate") ||
    path.includes("/register/organization")
  ) {
    return false;
  }
  if (path.startsWith("/api/v1/jobs/public")) return false;
  if (path.startsWith("/api/v1/schedule/")) return false;
  if (path === "/api/v1/health" || path.startsWith("/api/v1/health/")) return false;
  return true;
}

function assertRealJwtIfRequired(path: string): void {
  if (!pathNeedsRealJwt(path)) return;
  const token = getToken();
  if (!token) return;
  if (token === "mock-token" || !tokenLooksLikeJwt(token)) {
    throw new ApiError(401, DEMO_LOGIN_MSG);
  }
}

const SESSION_EXPIRED_MSG = "Your session has expired — please sign in again.";

/**
 * A 401 on a request that DID carry a token means the JWT expired (tokens
 * have a finite lifetime) or was invalidated. Clear the dead session and send
 * the user to the login page instead of surfacing a cryptic
 * "Could not validate credentials" inside whatever they were doing.
 * Returns true when a redirect was triggered.
 */
function handleExpiredSession(status: number, path: string, hadToken: boolean): boolean {
  if (status !== 401 || !hadToken) return false;
  if (typeof window === "undefined") return false;
  // Never hijack auth endpoints (a wrong password is a legitimate 401) and
  // never loop when already on the login page.
  if (path.includes("/auth/")) return false;
  if (window.location.pathname.startsWith("/login")) return false;
  try {
    localStorage.removeItem("paths-auth");
  } catch { /* ignore */ }
  window.location.href = "/login";
  return true;
}

async function requestForm<T>(path: string, body: FormData): Promise<T> {
  assertRealJwtIfRequired(path);
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE_URL}${path}`, { method: "POST", headers, body });

  if (!res.ok) {
    if (handleExpiredSession(res.status, path, Boolean(token))) {
      throw new ApiError(401, SESSION_EXPIRED_MSG);
    }
    let detail = `HTTP ${res.status}`;
    try { const err = await res.json(); detail = formatErrorDetail(err?.detail) ?? detail; } catch { /* ignore */ }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export interface RequestOptions {
  /** Abort the request after this many ms (e.g. long-running AI calls). */
  timeoutMs?: number;
  extraHeaders?: Record<string, string>;
}

/**
 * GET a binary response (e.g. a PDF) with the bearer token attached.
 * A plain `<a href>` can't send the Authorization header and resolves
 * against the frontend origin, so file downloads must go through here.
 */
async function requestBlob(path: string, opts?: RequestOptions): Promise<Blob> {
  assertRealJwtIfRequired(path);
  const token = getToken();
  const headers: Record<string, string> = { ...opts?.extraHeaders };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const controller = opts?.timeoutMs ? new AbortController() : undefined;
  const timer =
    controller && opts?.timeoutMs
      ? setTimeout(() => controller.abort(), opts.timeoutMs)
      : undefined;

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      method: "GET",
      headers,
      signal: controller?.signal,
    });
  } catch (err) {
    if (timer) clearTimeout(timer);
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError(408, "The download took too long. Please try again.");
    }
    throw err;
  }
  if (timer) clearTimeout(timer);
  if (!res.ok) {
    if (handleExpiredSession(res.status, path, Boolean(token))) {
      throw new ApiError(401, SESSION_EXPIRED_MSG);
    }
    let detail = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      detail = formatErrorDetail(err?.detail) ?? detail;
    } catch { /* ignore */ }
    throw new ApiError(res.status, detail);
  }
  return res.blob();
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  opts?: RequestOptions,
): Promise<T> {
  assertRealJwtIfRequired(path);
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...opts?.extraHeaders,
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  // Optional client-side timeout. Used by slow AI endpoints (JD analysis,
  // match explanation) so the request resolves within a few minutes rather
  // than hanging indefinitely on a stalled upstream.
  const controller = opts?.timeoutMs ? new AbortController() : undefined;
  const timer =
    controller && opts?.timeoutMs
      ? setTimeout(() => controller.abort(), opts.timeoutMs)
      : undefined;

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller?.signal,
    });
  } catch (err) {
    if (timer) clearTimeout(timer);
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError(
        408,
        "This is taking longer than expected. Please try again in a moment.",
      );
    }
    throw err;
  }
  if (timer) clearTimeout(timer);

  if (!res.ok) {
    if (handleExpiredSession(res.status, path, Boolean(token))) {
      throw new ApiError(401, SESSION_EXPIRED_MSG);
    }
    let detail = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      detail = formatErrorDetail(err?.detail) ?? detail;
    } catch { /* ignore */ }
    throw new ApiError(res.status, detail);
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  get:      <T>(path: string, opts?: RequestOptions) => request<T>("GET", path, undefined, opts),
  post:     <T>(path: string, body?: unknown, opts?: RequestOptions) => request<T>("POST", path, body, opts),
  put:      <T>(path: string, body?: unknown, opts?: RequestOptions) => request<T>("PUT", path, body, opts),
  patch:    <T>(path: string, body?: unknown, opts?: RequestOptions) => request<T>("PATCH", path, body, opts),
  delete:   <T>(path: string) => request<T>("DELETE", path),
  postForm: <T>(path: string, body: FormData) => requestForm<T>(path, body),
  getBlob:  (path: string, opts?: RequestOptions) => requestBlob(path, opts),
};

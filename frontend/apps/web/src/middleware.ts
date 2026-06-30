/**
 * PATHS — Next.js middleware route guard.
 *
 * Server-side redirect for protected routes. The auth source of truth lives
 * in the JWT payload (claims set by the backend during login). The frontend
 * stores the JWT under localStorage (Zustand persist), but middleware runs
 * at the edge with no access to localStorage. We therefore base middleware
 * decisions on a non-sensitive cookie that the auth store mirrors. If the
 * cookie is missing we send the user to /login — the page-level guards in
 * each layout perform the precise checks once the client hydrates.
 *
 * Goal of this layer: cheap, fast first-pass that prevents server-rendered
 * dashboard pages from being requested at all by unauthenticated users.
 * Authoritative gating is enforced by the BACKEND endpoints — middleware
 * cannot be relied on alone.
 */

import { NextRequest, NextResponse } from "next/server";

const PUBLIC_PREFIXES = [
  "/",
  "/login",
  "/candidate-signup",
  "/company-signup",
  "/forbidden",
  "/pending-approval",
  "/rejected",
  "/careers",
  "/for-candidates",
  "/for-companies",
  "/how-it-works",
  "/blog",
  "/_next",
  "/favicon",
  "/api",
  "/icons",
  "/images",
];

// Routes that require some form of session. The actual role check happens
// in the page layout — middleware only enforces "must be logged in".
const PROTECTED_PREFIXES = [
  "/admin",
  "/dashboard",
  "/candidate",
  "/onboarding",
  "/settings",
];

function isPublic(pathname: string): boolean {
  if (pathname === "/") return true;
  return PUBLIC_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

function isProtected(pathname: string): boolean {
  return PROTECTED_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  if (!isProtected(pathname)) {
    return NextResponse.next();
  }
  if (isPublic(pathname)) {
    return NextResponse.next();
  }

  // Mirror cookie set by the client via the auth store (best-effort hint).
  // The /login page sets `paths-session=1`; logout clears it.
  const hasSession = req.cookies.get("paths-session")?.value === "1";
  if (!hasSession) {
    const loginUrl = req.nextUrl.clone();
    loginUrl.pathname = "/login";
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/admin/:path*",
    "/dashboard/:path*",
    "/candidate/:path*",
    "/onboarding/:path*",
    "/settings/:path*",
  ],
};

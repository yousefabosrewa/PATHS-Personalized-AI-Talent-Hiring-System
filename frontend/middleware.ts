import { NextResponse, type NextRequest } from "next/server";

const AUTH_COOKIE = "paths_auth";

function isProtectedPath(pathname: string) {
  return pathname.startsWith("/candidate") || pathname.startsWith("/org");
}

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (!isProtectedPath(pathname)) return NextResponse.next();

  const token = req.cookies.get(AUTH_COOKIE)?.value;
  if (token) return NextResponse.next();

  const url = req.nextUrl.clone();
  url.pathname = "/login";
  url.searchParams.set("next", `${pathname}${req.nextUrl.search}`);
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/candidate/:path*", "/org/:path*"],
};

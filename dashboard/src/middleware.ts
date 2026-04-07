import { NextRequest, NextResponse } from "next/server";

const AUTH_COOKIE = "apex_auth";
const PASSWORD = process.env.DASHBOARD_PASSWORD || "apex2026";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (pathname === "/login" || pathname.startsWith("/_next") || pathname.startsWith("/favicon")) {
    return NextResponse.next();
  }

  if (pathname.startsWith("/api/auth")) {
    return NextResponse.next();
  }

  const authCookie = request.cookies.get(AUTH_COOKIE);
  if (authCookie?.value === PASSWORD) {
    return NextResponse.next();
  }

  const loginUrl = new URL("/login", request.url);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};

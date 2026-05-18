import { NextRequest, NextResponse } from "next/server";

/**
 * Dashboard auth gate.
 *
 * Cookie-based: client logs in at /login, server sets `apex_auth` cookie
 * to the value of DASHBOARD_PASSWORD. Middleware checks the cookie equals
 * the env password on every request.
 *
 * DASHBOARD_PASSWORD lives in Doppler `prd` config (Doppler→Vercel auto-sync).
 * The legacy default `apex2026` was removed during the Plan A migration —
 * anyone with a stale cookie carrying that value will be redirected to /login
 * on the next request.
 */

const AUTH_COOKIE = "apex_auth";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Bypass auth for: login page, Next.js internals, /api/auth/*, /api/healthz
  // (others under /api/* still get gated — the dashboard's API routes that
  //  proxy to backend require an authed session).
  if (pathname === "/login" || pathname.startsWith("/_next") || pathname.startsWith("/favicon")) {
    return NextResponse.next();
  }
  if (pathname.startsWith("/api/auth") || pathname === "/api/healthz") {
    return NextResponse.next();
  }

  const expected = process.env.DASHBOARD_PASSWORD;
  if (!expected) {
    // Fail closed: if password env isn't set, deny everyone (except bypass
    // paths above). Avoids the historical "default password" footgun.
    return new NextResponse("Dashboard not configured (DASHBOARD_PASSWORD unset)", { status: 503 });
  }

  const authCookie = request.cookies.get(AUTH_COOKIE);
  if (authCookie?.value === expected) {
    return NextResponse.next();
  }

  const loginUrl = new URL("/login", request.url);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};

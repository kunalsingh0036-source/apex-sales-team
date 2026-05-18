import { NextRequest, NextResponse } from "next/server";

/**
 * /api/auth/login — sets the apex_auth cookie when password matches.
 *
 * Default `apex2026` removed during Plan A migration. DASHBOARD_PASSWORD
 * must come from Doppler `prd` (auto-synced to Vercel). If unset, all
 * login attempts fail with 503 — same fail-closed posture as middleware.ts.
 */

export async function POST(request: NextRequest) {
  const expected = process.env.DASHBOARD_PASSWORD;
  if (!expected) {
    return NextResponse.json(
      { error: "Dashboard not configured (DASHBOARD_PASSWORD unset)" },
      { status: 503 },
    );
  }

  let body: { password?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid request" }, { status: 400 });
  }

  if (typeof body.password !== "string" || body.password !== expected) {
    return NextResponse.json({ error: "Invalid password" }, { status: 401 });
  }

  const response = NextResponse.json({ ok: true });
  response.cookies.set("apex_auth", expected, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 60 * 60 * 24 * 30, // 30 days
    path: "/",
  });
  return response;
}

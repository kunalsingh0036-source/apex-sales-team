import { NextRequest, NextResponse } from "next/server";

const PASSWORD = process.env.DASHBOARD_PASSWORD || "apex2026";

export async function POST(request: NextRequest) {
  const body = await request.json();

  if (body.password === PASSWORD) {
    const response = NextResponse.json({ ok: true });
    response.cookies.set("apex_auth", PASSWORD, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 60 * 60 * 24 * 30, // 30 days
      path: "/",
    });
    return response;
  }

  return NextResponse.json({ error: "Invalid password" }, { status: 401 });
}

import { NextResponse } from "next/server";

/**
 * Substrate liveness probe — see ~/Claude Code/_template/ARCHITECTURE.md §5.
 *
 * - 200 OK when this Next.js process is up AND the backend's /healthz is reachable.
 * - 503 with check details when something's degraded.
 * - Whitelisted in middleware.ts so external monitors (Better Stack) can hit it
 *   without auth.
 */

export const dynamic = "force-dynamic";
export const revalidate = 0;

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";
const BACKEND_BASE = API_URL.replace(/\/api\/v1\/?$/, "");

export async function GET() {
  const checks: Record<string, "ok" | "fail"> = { process: "ok" };
  const errors: Record<string, string> = {};

  if (BACKEND_BASE) {
    try {
      const r = await fetch(`${BACKEND_BASE}/healthz`, {
        signal: AbortSignal.timeout(5000),
      });
      if (r.ok) checks.backend = "ok";
      else {
        checks.backend = "fail";
        errors.backend = `HTTP ${r.status}`;
      }
    } catch (err) {
      checks.backend = "fail";
      errors.backend = err instanceof Error ? err.message : String(err);
    }
  } else {
    checks.backend = "fail";
    errors.backend = "NEXT_PUBLIC_API_URL not set";
  }

  const healthy = Object.values(checks).every((v) => v === "ok");

  return NextResponse.json(
    {
      status: healthy ? "ok" : "degraded",
      service: "apex-sales-dashboard",
      checks,
      ...(Object.keys(errors).length > 0 ? { errors } : {}),
      timestamp: new Date().toISOString(),
    },
    { status: healthy ? 200 : 503 },
  );
}

/**
 * Structured logging — substrate observability path.
 *
 * Per ~/Claude Code/_template/ARCHITECTURE.md §5: errors and noteworthy
 * events go to stdout/stderr as JSON. Better Stack ingests them via Vercel
 * log drain (when the project is on a plan that supports it).
 *
 * Same JSON shape as TCS / HelmTech / template — Better Stack alert rules
 * work identically across the fleet.
 */

type Level = "debug" | "info" | "warn" | "error";

type LogEntry = {
  event: string;
  level: Level;
  service: string;
  timestamp: string;
  [k: string]: unknown;
};

const SERVICE = "apex-sales-dashboard";

function emit(entry: LogEntry) {
  const line = JSON.stringify(entry);
  if (entry.level === "error" || entry.level === "warn") {
    console.error(line);
  } else {
    console.log(line);
  }
}

export function logEvent(
  event: string,
  level: Level,
  data: Record<string, unknown> = {},
) {
  emit({
    event,
    level,
    service: SERVICE,
    timestamp: new Date().toISOString(),
    ...data,
  });
}

export function logError(
  event: string,
  err: unknown,
  context: Record<string, unknown> = {},
) {
  const e = err instanceof Error ? err : new Error(String(err));
  emit({
    event,
    level: "error",
    service: SERVICE,
    timestamp: new Date().toISOString(),
    error_message: e.message,
    error_name: e.name,
    stack: e.stack,
    ...context,
  });
}

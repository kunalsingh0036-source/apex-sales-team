"""
Structured logging — substrate observability path.

Per ~/Claude Code/_template/ARCHITECTURE.md §5: errors and noteworthy
events go to stdout/stderr as JSON. Better Stack ingests via the Railway
log drain (configured at the Railway service level, not in code).

Mirrors dashboard's `src/lib/observability.ts` and the TCS / HelmTech
helpers exactly — same JSON shape so Better Stack alert rules work
identically across the fleet.
"""

import json
import sys
import traceback
from datetime import datetime, timezone
from typing import Any, Literal

Level = Literal["debug", "info", "warn", "error"]

SERVICE = "apex-sales-backend"


def _emit(entry: dict[str, Any]) -> None:
    line = json.dumps(entry)
    if entry["level"] in ("error", "warn"):
        print(line, file=sys.stderr, flush=True)
    else:
        print(line, flush=True)


def log_event(event: str, level: Level, **data: Any) -> None:
    _emit(
        {
            "event": event,
            "level": level,
            "service": SERVICE,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        }
    )


def log_error(event: str, err: BaseException, **context: Any) -> None:
    _emit(
        {
            "event": event,
            "level": "error",
            "service": SERVICE,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_message": str(err),
            "error_name": type(err).__name__,
            "stack": "".join(traceback.format_exception(err)),
            **context,
        }
    )

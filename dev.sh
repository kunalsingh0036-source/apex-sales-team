#!/bin/bash
# ─── Apex Sales Agent — Local Dev Runner ──────────────────────
# Starts all services: Backend API, Celery Worker, Celery Beat, Dashboard
# Usage: ./dev.sh [start|stop|restart|status|logs]
# ─────────────────────────────────────────────────────────────

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
DASHBOARD_DIR="$ROOT_DIR/dashboard"
VENV="$BACKEND_DIR/.venv/bin"
PID_DIR="$ROOT_DIR/.pids"
LOG_DIR="$ROOT_DIR/.logs"

# Ports
BACKEND_PORT=8001
DASHBOARD_PORT=3001

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

mkdir -p "$PID_DIR" "$LOG_DIR"

# ─── Helpers ──────────────────────────────────────────────────

log() { echo -e "${CYAN}[apex]${NC} $1"; }
ok()  { echo -e "${GREEN}  ✓${NC} $1"; }
err() { echo -e "${RED}  ✗${NC} $1"; }
warn(){ echo -e "${YELLOW}  !${NC} $1"; }

save_pid() { echo "$2" > "$PID_DIR/$1.pid"; }

read_pid() {
    local pidfile="$PID_DIR/$1.pid"
    if [ -f "$pidfile" ]; then
        cat "$pidfile"
    fi
}

is_running() {
    local pid=$(read_pid "$1")
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        return 0
    fi
    return 1
}

kill_service() {
    local name="$1"
    local pid=$(read_pid "$name")
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null
        # Also kill children (celery forks)
        pkill -P "$pid" 2>/dev/null || true
        rm -f "$PID_DIR/$name.pid"
        ok "Stopped $name (pid $pid)"
    else
        rm -f "$PID_DIR/$name.pid"
    fi
}

wait_for_port() {
    local port=$1 name=$2 max=30
    for i in $(seq 1 $max); do
        if lsof -ti :$port >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    err "$name did not start on port $port"
    return 1
}

# ─── Preflight Checks ────────────────────────────────────────

preflight() {
    log "Running preflight checks..."

    # Check .env
    if [ ! -f "$ROOT_DIR/.env" ]; then
        err ".env file not found. Copy .env.example and configure."
        exit 1
    fi
    ok ".env found"

    # Check venv
    if [ ! -f "$VENV/python" ]; then
        err "Python venv not found at $VENV. Run: python -m venv $BACKEND_DIR/.venv && pip install -r requirements.txt"
        exit 1
    fi
    ok "Python venv ready"

    # Check Redis (try direct, then any Docker container with redis)
    if redis-cli ping >/dev/null 2>&1; then
        ok "Redis available"
    elif docker ps --format '{{.Names}}' 2>/dev/null | grep -q redis; then
        REDIS_CONTAINER=$(docker ps --format '{{.Names}}' | grep redis | head -1)
        if docker exec "$REDIS_CONTAINER" redis-cli ping >/dev/null 2>&1; then
            ok "Redis available (Docker: $REDIS_CONTAINER)"
        else
            err "Redis container found but not responding"
            exit 1
        fi
    else
        err "Redis not running. Start it: docker run -d -p 6379:6379 --name apex-redis redis:7-alpine"
        exit 1
    fi

    # Check Postgres (try direct, then any Docker container with postgres)
    if pg_isready -h localhost -p 5432 -U apex -d apex_outreach >/dev/null 2>&1; then
        ok "PostgreSQL available"
    elif docker ps --format '{{.Names}}' 2>/dev/null | grep -q postgres; then
        PG_CONTAINER=$(docker ps --format '{{.Names}}' | grep postgres | head -1)
        if docker exec "$PG_CONTAINER" pg_isready -U apex -d apex_outreach >/dev/null 2>&1; then
            ok "PostgreSQL available (Docker: $PG_CONTAINER)"
        else
            err "Postgres container found but apex_outreach DB not ready"
            exit 1
        fi
    else
        err "PostgreSQL not running. Start Docker containers."
        exit 1
    fi

    # Check port conflicts
    for port in $BACKEND_PORT $DASHBOARD_PORT; do
        pid=$(lsof -ti :$port 2>/dev/null | head -1)
        if [ -n "$pid" ]; then
            proc=$(ps -p $pid -o comm= 2>/dev/null || echo "unknown")
            err "Port $port already in use by $proc (pid $pid). Run ./dev.sh stop first."
            exit 1
        fi
    done
    ok "Ports $BACKEND_PORT, $DASHBOARD_PORT available"

    # Check node_modules
    if [ ! -d "$DASHBOARD_DIR/node_modules" ]; then
        warn "Dashboard node_modules missing. Installing..."
        cd "$DASHBOARD_DIR" && npm install
    fi
    ok "Dashboard dependencies ready"
}

# ─── Start Services ──────────────────────────────────────────

start_backend() {
    if is_running "backend"; then
        warn "Backend already running (pid $(read_pid backend))"
        return
    fi

    # Kill any stray process on the port
    lsof -ti :$BACKEND_PORT | xargs kill 2>/dev/null || true
    sleep 1

    cd "$BACKEND_DIR"
    "$VENV/uvicorn" app.main:app --host 0.0.0.0 --port $BACKEND_PORT --reload \
        >> "$LOG_DIR/backend.log" 2>&1 &
    save_pid "backend" $!

    if wait_for_port $BACKEND_PORT "Backend"; then
        ok "Backend started on port $BACKEND_PORT (pid $!)"
    fi
}

start_celery_worker() {
    if is_running "celery-worker"; then
        warn "Celery worker already running (pid $(read_pid celery-worker))"
        return
    fi

    cd "$BACKEND_DIR"
    # Clear pycache to avoid stale code
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

    "$VENV/python" -m celery -A app.workers.celery_app worker \
        --loglevel=info --concurrency=2 \
        -Q email,linkedin,whatsapp,social,ai,enrichment,analytics,automation,celery \
        >> "$LOG_DIR/celery-worker.log" 2>&1 &
    save_pid "celery-worker" $!
    ok "Celery worker started (pid $!)"
}

start_celery_beat() {
    if is_running "celery-beat"; then
        warn "Celery beat already running (pid $(read_pid celery-beat))"
        return
    fi

    cd "$BACKEND_DIR"
    rm -f celerybeat-schedule celerybeat-schedule.db 2>/dev/null

    "$VENV/python" -m celery -A app.workers.celery_app beat \
        --loglevel=info \
        >> "$LOG_DIR/celery-beat.log" 2>&1 &
    save_pid "celery-beat" $!
    ok "Celery beat started (pid $!)"
}

start_dashboard() {
    if is_running "dashboard"; then
        warn "Dashboard already running (pid $(read_pid dashboard))"
        return
    fi

    # Kill any stray process on the port
    lsof -ti :$DASHBOARD_PORT | xargs kill 2>/dev/null || true
    sleep 1

    cd "$DASHBOARD_DIR"
    # Clear stale build cache to prevent webpack module errors
    rm -rf .next 2>/dev/null

    npx next dev --port $DASHBOARD_PORT \
        >> "$LOG_DIR/dashboard.log" 2>&1 &
    save_pid "dashboard" $!

    if wait_for_port $DASHBOARD_PORT "Dashboard"; then
        ok "Dashboard started on port $DASHBOARD_PORT (pid $!)"
    fi
}

# ─── Commands ─────────────────────────────────────────────────

cmd_start() {
    log "Starting Apex Sales Agent..."
    echo ""
    preflight
    echo ""

    # Run database migrations
    log "Running database migrations..."
    cd "$BACKEND_DIR"
    "$VENV/python" -m alembic upgrade head >> "$LOG_DIR/migrations.log" 2>&1
    if [ $? -eq 0 ]; then
        ok "Database migrations up to date"
    else
        warn "Migration warning (may be fine if DB is already synced). Check $LOG_DIR/migrations.log"
    fi
    echo ""

    start_backend
    start_celery_worker
    start_celery_beat
    start_dashboard
    echo ""
    log "All services running!"
    echo ""
    echo -e "  ${CYAN}Dashboard:${NC}  http://localhost:$DASHBOARD_PORT"
    echo -e "  ${CYAN}Backend:${NC}    http://localhost:$BACKEND_PORT"
    echo -e "  ${CYAN}API Docs:${NC}   http://localhost:$BACKEND_PORT/docs"
    echo ""
    echo -e "  ${YELLOW}Logs:${NC}       ./dev.sh logs [backend|worker|beat|dashboard]"
    echo -e "  ${YELLOW}Stop:${NC}       ./dev.sh stop"
    echo ""
}

cmd_stop() {
    log "Stopping all services..."
    kill_service "dashboard"
    kill_service "celery-beat"
    kill_service "celery-worker"
    kill_service "backend"
    # Clean up any strays on our ports
    lsof -ti :$BACKEND_PORT | xargs kill 2>/dev/null || true
    lsof -ti :$DASHBOARD_PORT | xargs kill 2>/dev/null || true
    ok "All services stopped"
}

cmd_restart() {
    cmd_stop
    sleep 2
    cmd_start
}

cmd_status() {
    log "Service Status:"
    for svc in backend celery-worker celery-beat dashboard; do
        if is_running "$svc"; then
            ok "$svc — running (pid $(read_pid $svc))"
        else
            err "$svc — stopped"
        fi
    done

    echo ""
    # Quick health check
    if curl -s http://localhost:$BACKEND_PORT/health >/dev/null 2>&1; then
        ok "Backend API — healthy"
    else
        err "Backend API — not responding"
    fi
}

cmd_logs() {
    local service="${1:-all}"
    case "$service" in
        backend)  tail -f "$LOG_DIR/backend.log" ;;
        worker)   tail -f "$LOG_DIR/celery-worker.log" ;;
        beat)     tail -f "$LOG_DIR/celery-beat.log" ;;
        dashboard) tail -f "$LOG_DIR/dashboard.log" ;;
        all)      tail -f "$LOG_DIR"/*.log ;;
        *)        err "Unknown service: $service. Use: backend, worker, beat, dashboard, all" ;;
    esac
}

# ─── Main ─────────────────────────────────────────────────────

case "${1:-start}" in
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    restart) cmd_restart ;;
    status)  cmd_status ;;
    logs)    cmd_logs "$2" ;;
    *)       echo "Usage: ./dev.sh [start|stop|restart|status|logs]" ;;
esac

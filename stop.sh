#!/usr/bin/env bash
# SRT Flow - Stop Frontend & Backend

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
GRAY='\033[0;90m'
RESET='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo -e "${CYAN}========================================${RESET}"
echo -e "${CYAN}  SRT Flow - Stopping Services${RESET}"
echo -e "${CYAN}========================================${RESET}"
echo ""

# Read PORT from .env
PORT="8081"
if [ -f "$PROJECT_ROOT/.env" ]; then
    _port=$(grep -E '^PORT=(.+)$' "$PROJECT_ROOT/.env" | cut -d'=' -f2 | tr -d '[:space:]')
    [ -n "$_port" ] && PORT="$_port"
fi

FRONTEND_PORT="3000"

# Helper: kill all processes listening on a given port
stop_port() {
    local port="$1"
    local label="$2"
    local killed=false

    # Try ss first, fallback to lsof
    local pids
    if command -v ss &>/dev/null; then
        pids=$(ss -tlnp "sport = :$port" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | sort -u)
    fi
    if [ -z "$pids" ] && command -v lsof &>/dev/null; then
        pids=$(lsof -ti tcp:"$port" 2>/dev/null | sort -u)
    fi

    for pid in $pids; do
        local name
        name=$(ps -p "$pid" -o comm= 2>/dev/null || echo "unknown")
        echo -e "  ${YELLOW}Killing process: $name (PID $pid)${RESET}"
        kill -9 "$pid" 2>/dev/null && killed=true
    done

    if $killed; then
        echo -e "  ${GREEN}$label stopped.${RESET}"
    else
        echo -e "  ${GRAY}No process found on port $port.${RESET}"
    fi
}

# [1/2] Stop backend
echo -e "${GREEN}[1/2] Stopping backend (port $PORT)...${RESET}"
stop_port "$PORT" "Backend"

# Fallback: kill by PID file
if [ -f "$PROJECT_ROOT/.backend.pid" ]; then
    pid=$(cat "$PROJECT_ROOT/.backend.pid")
    if kill -0 "$pid" 2>/dev/null; then
        echo -e "  ${YELLOW}Killing backend from PID file (PID $pid)${RESET}"
        kill -9 "$pid" 2>/dev/null
    fi
    rm -f "$PROJECT_ROOT/.backend.pid"
fi

# Fallback: kill python/uvicorn processes
while IFS= read -r pid; do
    [ -z "$pid" ] && continue
    echo -e "  ${YELLOW}Killing leftover uvicorn (PID $pid)${RESET}"
    kill -9 "$pid" 2>/dev/null
done < <(pgrep -f 'uvicorn backend.app.main' 2>/dev/null)

# [2/2] Stop frontend
echo -e "${GREEN}[2/2] Stopping frontend (port $FRONTEND_PORT)...${RESET}"
stop_port "$FRONTEND_PORT" "Frontend"

# Fallback: kill by PID file
if [ -f "$PROJECT_ROOT/.frontend.pid" ]; then
    pid=$(cat "$PROJECT_ROOT/.frontend.pid")
    if kill -0 "$pid" 2>/dev/null; then
        echo -e "  ${YELLOW}Killing frontend from PID file (PID $pid)${RESET}"
        kill -9 "$pid" 2>/dev/null
    fi
    rm -f "$PROJECT_ROOT/.frontend.pid"
fi

# Fallback: kill node/vite processes
while IFS= read -r pid; do
    [ -z "$pid" ] && continue
    echo -e "  ${YELLOW}Killing leftover vite node (PID $pid)${RESET}"
    kill -9 "$pid" 2>/dev/null
done < <(pgrep -f 'vite' 2>/dev/null)

echo ""
echo -e "${CYAN}========================================${RESET}"
echo -e "${CYAN}  All services stopped.${RESET}"
echo -e "${CYAN}========================================${RESET}"
echo ""

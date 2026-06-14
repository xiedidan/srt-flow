#!/usr/bin/env bash
# SRT Flow - Start Frontend & Backend
set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RESET='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo ""
echo -e "${CYAN}========================================${RESET}"
echo -e "${CYAN}  SRT Flow - Starting Services${RESET}"
echo -e "${CYAN}========================================${RESET}"
echo ""

# Read PORT from .env
PORT="8081"
if [ -f ".env" ]; then
    _port=$(grep -E '^PORT=(.+)$' .env | cut -d'=' -f2 | tr -d '[:space:]')
    [ -n "$_port" ] && PORT="$_port"
fi

# Ensure log directory exists
mkdir -p data/logs

# Start backend
echo -e "${GREEN}[1/2] Starting backend (port $PORT)...${RESET}"
nohup bash -c "
    source '$PROJECT_ROOT/venv/bin/activate'
    cd '$PROJECT_ROOT'
    uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT --log-level info
" > data/logs/backend.log 2>&1 &
echo $! > .backend.pid
echo "  Backend PID: $(cat .backend.pid) | Log: data/logs/backend.log"

sleep 2

# Start frontend
echo -e "${GREEN}[2/2] Starting frontend...${RESET}"
nohup bash -c "
    cd '$PROJECT_ROOT/frontend'
    npm run dev
" > data/logs/frontend.log 2>&1 &
echo $! > .frontend.pid
echo "  Frontend PID: $(cat .frontend.pid) | Log: data/logs/frontend.log"

echo ""
echo -e "${CYAN}========================================${RESET}"
echo -e "${YELLOW}  Backend:  http://localhost:$PORT${RESET}"
echo -e "${YELLOW}  Frontend: http://localhost:3000${RESET}"
echo -e "${CYAN}========================================${RESET}"
echo ""

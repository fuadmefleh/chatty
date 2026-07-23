#!/bin/bash
# start_web.sh — Start the Atlas web stack
#   - chatty-web-server  (FastAPI, port 8016)
#   - order-explorer-backend (FastAPI/uvicorn, port 8015)
#   - order-explorer-frontend (Vite dev server, port 5173)
#
# Usage:
#   ./start_web.sh           # start all three
#   ./start_web.sh --build   # build the frontend first, then start

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

BUILD=false
for arg in "$@"; do
    [[ "$arg" == "--build" ]] && BUILD=true
done

# ── Virtual environment ───────────────────────────────────────────────────────
if [ -d "venv" ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source venv/bin/activate
else
    echo -e "${RED}No virtual environment found. Run: python -m venv venv && pip install -r requirements.txt${NC}"
    exit 1
fi

# ── .env check ────────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    exit 1
fi

# Source env so CHATTY_WEB_API_KEY / WEB_USER_ID are available for the check
set -a; source .env; set +a

if [ -z "${CHATTY_WEB_API_KEY:-}" ]; then
    echo -e "${YELLOW}Warning: CHATTY_WEB_API_KEY is not set in .env — using default 'changeme'${NC}"
fi

# ── Frontend build (optional) ─────────────────────────────────────────────────
FRONTEND_DIR="$SCRIPT_DIR/order_explorer_site/frontend"
if $BUILD; then
    echo -e "${CYAN}Building frontend...${NC}"
    cd "$FRONTEND_DIR"
    npm install --silent
    npm run build
    cd "$SCRIPT_DIR"
    echo -e "${GREEN}Frontend built.${NC}"
fi

# ── Kill any existing processes on our ports ──────────────────────────────────
for PORT in 8015 8016; do
    PID=$(lsof -ti tcp:"$PORT" 2>/dev/null || true)
    if [ -n "$PID" ]; then
        echo -e "${YELLOW}Stopping existing process on port $PORT (PID $PID)...${NC}"
        kill "$PID" 2>/dev/null || true
        sleep 1
    fi
done

# ── Start services ────────────────────────────────────────────────────────────
mkdir -p "$SCRIPT_DIR/logs"

echo -e "${GREEN}Starting chatty-web-server (port 8016)...${NC}"
nohup python "$SCRIPT_DIR/chatty_web_server.py" \
    >> "$SCRIPT_DIR/logs/chatty-web-out.log" \
    2>> "$SCRIPT_DIR/logs/chatty-web-error.log" &
WEB_PID=$!
echo "  PID: $WEB_PID"

echo -e "${GREEN}Starting order-explorer-backend (port 8015)...${NC}"
nohup bash -c "cd '$SCRIPT_DIR/order_explorer_site/backend' && \
    '$SCRIPT_DIR/venv/bin/uvicorn' main:app --host 0.0.0.0 --port 8015" \
    >> "$SCRIPT_DIR/logs/order-backend-out.log" \
    2>> "$SCRIPT_DIR/logs/order-backend-error.log" &
BACKEND_PID=$!
echo "  PID: $BACKEND_PID"

echo -e "${GREEN}Starting frontend (port 5173)...${NC}"
if $BUILD && [ -d "$FRONTEND_DIR/dist" ]; then
    # Serve production build
    nohup npx --prefix "$FRONTEND_DIR" vite preview --host 0.0.0.0 --port 5173 \
        >> "$SCRIPT_DIR/logs/order-frontend-out.log" \
        2>> "$SCRIPT_DIR/logs/order-frontend-error.log" &
else
    # Dev server
    nohup npx --prefix "$FRONTEND_DIR" vite --host 0.0.0.0 --port 5173 \
        >> "$SCRIPT_DIR/logs/order-frontend-out.log" \
        2>> "$SCRIPT_DIR/logs/order-frontend-error.log" &
fi
FRONTEND_PID=$!
echo "  PID: $FRONTEND_PID"

# ── Wait for servers to be ready ──────────────────────────────────────────────
echo -e "${CYAN}Waiting for services to start...${NC}"
sleep 4

for PORT in 8015 8016 5173; do
    if curl -s --max-time 2 "http://localhost:$PORT" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓ Port $PORT ready${NC}"
    else
        echo -e "  ${YELLOW}⚠ Port $PORT not responding yet (check logs)${NC}"
    fi
done

echo ""
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}  Atlas Web Stack running!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo -e "  Dashboard:    ${CYAN}http://localhost:5173${NC}"
echo -e "  Atlas API:   ${CYAN}http://localhost:8016${NC}"
echo -e "  Orders API:   ${CYAN}http://localhost:8015${NC}"
echo ""
echo -e "  Logs:         ${YELLOW}tail -f logs/chatty-web-out.log${NC}"
echo -e "  Stop all:     ${YELLOW}kill $WEB_PID $BACKEND_PID $FRONTEND_PID${NC}"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"

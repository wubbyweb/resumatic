#!/usr/bin/env bash
# =============================================================================
# Resumatic — Start Script for Frontend and Backend
# =============================================================================
# Usage:
#   ./start.sh               # Starts both Backend (port 8000) and Frontend (port 3000)
#   ./start.sh --unified     # Starts unified FastAPI server (serves both on port 8000)
#   ./start.sh --backend     # Starts only the FastAPI backend (port 8000)
#   ./start.sh --frontend    # Starts only the standalone frontend (port 3000)
# =============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$PROJECT_DIR"

BACKEND_PORT="${PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
HOST="${HOST:-127.0.0.1}"

MODE="both"
if [ "$1" = "--unified" ]; then
  MODE="unified"
elif [ "$1" = "--backend" ] || [ "$1" = "--backend-only" ]; then
  MODE="backend"
elif [ "$1" = "--frontend" ] || [ "$1" = "--frontend-only" ]; then
  MODE="frontend"
elif [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
  echo "Resumatic Startup Script"
  echo ""
  echo "Usage:"
  echo "  ./start.sh             Start both backend (:8000) and frontend (:3000)"
  echo "  ./start.sh --unified   Start unified FastAPI server (:8000) serving API + UI"
  echo "  ./start.sh --backend   Start only the FastAPI backend (:8000)"
  echo "  ./start.sh --frontend  Start only the frontend web server (:3000)"
  echo "  ./start.sh --help      Show this help message"
  exit 0
fi

# -----------------------------------------------------------------------------
# 1. Virtual Environment Activation
# -----------------------------------------------------------------------------
if [ -f "$PROJECT_DIR/.venv/bin/activate" ]; then
  echo "⚙️  Activating virtual environment (.venv)..."
  # shellcheck source=/dev/null
  source "$PROJECT_DIR/.venv/bin/activate"
fi

# -----------------------------------------------------------------------------
# 2. Check Python & Dependencies
# -----------------------------------------------------------------------------
PYTHON_CMD="python3"
if command -v python >/dev/null 2>&1; then
  PYTHON_CMD="python"
fi

# Check for .env file
if [ ! -f "$PROJECT_DIR/.env" ]; then
  echo "⚠️  Warning: .env file not found."
  if [ -f "$PROJECT_DIR/.env.example" ]; then
    echo "💡 Creating .env from .env.example (please add your OPENAI_API_KEY or GOOGLE_API_KEY)..."
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
  fi
fi

# -----------------------------------------------------------------------------
# 3. Process cleanup handler on exit
# -----------------------------------------------------------------------------
PIDS=()

cleanup() {
  echo ""
  echo "🛑 Stopping services..."
  for pid in "${PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  wait 2>/dev/null || true
  echo "✅ Resumatic shutdown complete."
}

trap cleanup INT TERM EXIT

# -----------------------------------------------------------------------------
# 4. Launch Services
# -----------------------------------------------------------------------------

echo ""
echo "=========================================================="
echo "           🎯 Resumatic AI Resume Tailor                 "
echo "=========================================================="

if [ "$MODE" = "unified" ]; then
  echo "🚀 Mode: Unified (FastAPI serves API + Frontend UI)"
  echo ""
  echo "  👉 Web Application: http://$HOST:$BACKEND_PORT"
  echo "  👉 API Healthcheck: http://$HOST:$BACKEND_PORT/health"
  echo "  👉 Swagger Docs:    http://$HOST:$BACKEND_PORT/docs"
  echo "=========================================================="
  echo ""
  "$PYTHON_CMD" -m uvicorn main:app --reload --host "$HOST" --port "$BACKEND_PORT"

elif [ "$MODE" = "backend" ]; then
  echo "🚀 Mode: Backend Only"
  echo ""
  echo "  👉 Backend API:     http://$HOST:$BACKEND_PORT"
  echo "  👉 Swagger Docs:    http://$HOST:$BACKEND_PORT/docs"
  echo "=========================================================="
  echo ""
  "$PYTHON_CMD" -m uvicorn main:app --reload --host "$HOST" --port "$BACKEND_PORT"

elif [ "$MODE" = "frontend" ]; then
  echo "🚀 Mode: Frontend Only"
  echo ""
  echo "  👉 Frontend Web UI: http://$HOST:$FRONTEND_PORT"
  echo "  👉 Expected Backend: http://$HOST:$BACKEND_PORT"
  echo "=========================================================="
  echo ""
  "$PYTHON_CMD" -m http.server "$FRONTEND_PORT" --directory "$PROJECT_DIR/frontend" --bind "$HOST"

else
  # Default: start both backend and frontend
  echo "🚀 Mode: Starting both Backend & Frontend"
  echo ""
  echo "  👉 Frontend Web UI: http://$HOST:$FRONTEND_PORT"
  echo "  👉 Unified Web UI:  http://$HOST:$BACKEND_PORT"
  echo "  👉 Backend API:     http://$HOST:$BACKEND_PORT"
  echo "  👉 Swagger Docs:    http://$HOST:$BACKEND_PORT/docs"
  echo "  👉 API Healthcheck: http://$HOST:$BACKEND_PORT/health"
  echo "=========================================================="
  echo ""

  # Start Frontend static server in background
  echo "Starting Frontend server on port $FRONTEND_PORT..."
  "$PYTHON_CMD" -m http.server "$FRONTEND_PORT" --directory "$PROJECT_DIR/frontend" --bind "$HOST" >/dev/null 2>&1 &
  FRONTEND_PID=$!
  PIDS+=("$FRONTEND_PID")

  # Start Backend in foreground
  echo "Starting Backend API on port $BACKEND_PORT..."
  "$PYTHON_CMD" -m uvicorn main:app --reload --host "$HOST" --port "$BACKEND_PORT" &
  BACKEND_PID=$!
  PIDS+=("$BACKEND_PID")

  # Wait for any process to exit
  wait -n "${PIDS[@]}" 2>/dev/null || wait
fi

#!/bin/bash
# Start both frontend and backend for local development

set -e

echo "=== Bookshelf Portal - Dev Mode ==="
echo ""

# Check dependencies
command -v python3 >/dev/null 2>&1 || { echo "Python 3 is required."; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js is required."; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "npm is required."; exit 1; }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

# Setup backend venv if needed
if [ ! -d "$BACKEND_DIR/.venv" ]; then
  echo "Creating Python virtual environment..."
  python3 -m venv "$BACKEND_DIR/.venv"
  "$BACKEND_DIR/.venv/bin/pip" install -q -r "$BACKEND_DIR/requirements.txt"
  echo "Backend dependencies installed"
fi

# Install frontend deps if needed
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "Installing frontend dependencies..."
  cd "$FRONTEND_DIR" && npm install
  echo "Frontend dependencies installed"
fi

# Start backend
echo ""
echo "Starting backend on http://localhost:8788 ..."
cd "$BACKEND_DIR"
.venv/bin/uvicorn app.main:app --reload --port 8788 &
BACKEND_PID=$!

sleep 1

# Start frontend
echo "Starting frontend on http://localhost:5173 ..."
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "==================================="
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:8788"
echo "  Mock mode: ON (no Bookshelf needed)"
echo "  Password:  family"
echo "==================================="
echo ""
echo "Press Ctrl+C to stop both servers."
echo ""

# Cleanup on exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'" EXIT INT TERM

wait

#!/bin/bash
set -e
PORT=8000
PID=$(lsof -ti :$PORT 2>/dev/null || true)
if [ -n "$PID" ]; then
  echo "Killing existing process on port $PORT (PID $PID)..."
  kill -9 $PID
  sleep 1
fi
if lsof -i :$PORT > /dev/null 2>&1; then
  echo "WARNING: port $PORT still occupied after kill, check manually."
  lsof -i :$PORT
  exit 1
fi
echo "Port $PORT clear. Starting backend..."
cd /home/corby/jamm-os
source .venv/bin/activate
exec .venv/bin/uvicorn app.main:app --port 8000 --reload

#!/bin/bash
set -e
PORT=3000
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
echo "Port $PORT clear. Wiping .next cache..."
cd /home/corby/jamm-os/frontend
rm -rf .next
echo "Starting frontend..."
exec npm run dev

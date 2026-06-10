#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

CACHE_PORT="${HOME}/.cache/stats-sheets/port"
cleanup() {
  if [[ -n "${SERVER_PID:-}" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

python server.py &
SERVER_PID=$!

BASE_URL=""
for _ in $(seq 1 40); do
  if [[ -f "$CACHE_PORT" ]]; then
    PORT="$(cat "$CACHE_PORT")"
    BASE_URL="http://127.0.0.1:${PORT}"
    if curl -sf "${BASE_URL}/heartbeat" >/dev/null 2>&1; then
      break
    fi
  fi
  sleep 0.25
done

if [[ -z "$BASE_URL" ]] || ! curl -sf "${BASE_URL}/heartbeat" >/dev/null 2>&1; then
  echo "Server failed to start" >&2
  exit 1
fi

export BASE_URL

if [[ ! -d node_modules/@playwright/test ]]; then
  npm install --no-audit --no-fund
  npx playwright install chromium
fi

npm run test:e2e

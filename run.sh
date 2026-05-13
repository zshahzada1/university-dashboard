#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

MODE="${1:-prod}"

if [ "$MODE" = "dev" ]; then
  ( cd backend && .venv/bin/uvicorn app.main:app --reload --port 8765 ) &
  BPID=$!
  ( cd frontend && npm run dev ) &
  FPID=$!
  trap "kill $BPID $FPID 2>/dev/null || true" EXIT
  wait
else
  ( cd frontend && [ -d dist ] || npm run build )
  cd backend && .venv/bin/uvicorn app.main:app --port 8765
fi

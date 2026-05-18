#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/scripts"
VENV="$SCRIPT_DIR/scripts/.venv/bin/python"
PYTHON="${VENV:-python3}"
exec "$PYTHON" -m bb_sync "$@"

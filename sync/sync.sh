#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/scripts"
VENV="$SCRIPT_DIR/scripts/.venv/bin/python"
if [ -x "$VENV" ]; then PYTHON="$VENV"; else PYTHON="python3"; fi
exec "$PYTHON" -m bb_sync "$@"

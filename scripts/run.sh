#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$ROOT_DIR/.venv-macos/bin/python"

if [ ! -x "$VENV_PY" ]; then
  echo "Missing .venv-macos. Run ./scripts/setup.sh first."
  exit 1
fi

cd "$ROOT_DIR"
exec "$VENV_PY" -m uvicorn main:app --host 0.0.0.0 --port 8080

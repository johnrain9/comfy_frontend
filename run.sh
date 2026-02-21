#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ -x "./venv/bin/uvicorn" ]; then
  exec ./venv/bin/uvicorn app:app --host 0.0.0.0 --port "${PORT:-8585}"
fi
exec uvicorn app:app --host 0.0.0.0 --port "${PORT:-8585}"

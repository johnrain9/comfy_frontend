#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
API_BASE="${VIDEO_QUEUE_API:-http://127.0.0.1:8585}"

cd "$ROOT"

echo "[baseline] API base: $API_BASE"

echo "\n== API: health =="
curl -fsS "$API_BASE/api/health" | python -m json.tool

echo "\n== API: workflows =="
curl -fsS "$API_BASE/api/workflows" | python -m json.tool

echo "\n== API: jobs =="
curl -fsS "$API_BASE/api/jobs" | python -m json.tool

echo "\n== CLI: list =="
./venv/bin/python cli.py list

echo "\n== CLI: status =="
./venv/bin/python cli.py status

echo "\n== Baseline tests (Task 0) =="
PYTHONPATH=. ./venv/bin/pytest -q tests/test_task0_baseline.py

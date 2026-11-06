#!/usr/bin/env bash
# check: the Construction Verification Command (STATE.md test_command; AI-DLC verification-command.txt).
# Runs Ruff, then the whole pytest suite with line coverage on src/gsm8k (fails under 80%), on the CPU,
# with this folder's caches, through scripts/in-env.sh.
set -u; ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
scripts/in-env.sh .venv/bin/ruff check src tests || exit $?
scripts/in-env.sh .venv/bin/ruff format --check src tests || exit $?
scripts/in-env.sh .venv/bin/python -m pytest -q --cov=src/gsm8k --cov-report=term-missing:skip-covered \
  --cov-fail-under=80 "$@"

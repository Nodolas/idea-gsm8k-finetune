#!/usr/bin/env bash
# check: the Construction Verification Command (STATE.md test_command; AI-DLC verification-command.txt).
# Runs Ruff, then the website's lint, type check and Vitest suite (once package.json exists), then the whole pytest suite with line coverage on src/gsm8k (fails under 80%), on the CPU,
# with this folder's caches, through scripts/in-env.sh.
set -u; ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
scripts/in-env.sh .venv/bin/ruff check src tests || exit $?
scripts/in-env.sh .venv/bin/ruff format --check src tests || exit $?
if [ -f package.json ]; then
  scripts/in-env.sh npm run web:lint || exit $?
  scripts/in-env.sh npm run web:typecheck || exit $?
  scripts/in-env.sh npm run web:test || exit $?
fi
scripts/in-env.sh .venv/bin/python -m pytest -q --cov=src/gsm8k --cov-report=term-missing:skip-covered \
  --cov-fail-under=80 "$@"

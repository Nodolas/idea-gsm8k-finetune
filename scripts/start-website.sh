#!/usr/bin/env bash
# start-website: start the run service, the run-queue worker and the website (all on 127.0.0.1 only),
# then open the website in the browser. Anything already running is left as it is. Started by the
# desktop launcher gsm8k-lab.desktop; logs go to outputs/website/. Stop with scripts/stop-website.sh.
set -u; ROOT=$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd); cd "$ROOT"
LOG="$ROOT/outputs/website"; mkdir -p "$LOG"
up() { curl -s -o /dev/null --max-time 1 "$1"; }

up http://127.0.0.1:8000/api/v1/status ||
  setsid nohup scripts/in-env.sh .venv/bin/python -m gsm8k serve --port 8000 > "$LOG/serve.log" 2>&1 < /dev/null &
# The worker keeps the GPU visible: the runs it launches use it.
pgrep -f "gsm8k worker" > /dev/null ||
  setsid nohup scripts/in-env.sh --gpu .venv/bin/python -m gsm8k worker > "$LOG/worker.log" 2>&1 < /dev/null &
up http://127.0.0.1:5173/ ||
  setsid nohup scripts/in-env.sh npm run web:dev > "$LOG/web.log" 2>&1 < /dev/null &

for _ in $(seq 1 60); do
  up http://127.0.0.1:5173/ && up http://127.0.0.1:8000/api/v1/status && break
  sleep 1
done
xdg-open http://127.0.0.1:5173/ > /dev/null 2>&1 &

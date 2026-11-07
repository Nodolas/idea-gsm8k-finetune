#!/usr/bin/env bash
# stop-website: stop the website, the run service and the run-queue worker started by start-website.sh.
# A run that is already training keeps going (it runs in its own session); queued runs wait until
# the worker is started again.
pkill -f "vite --config web/vite.config.ts"
pkill -f "gsm8k serve --port 8000"
pkill -f "gsm8k worker"
exit 0

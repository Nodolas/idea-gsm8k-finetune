# Local commands (unit-of-work.md U4). Nothing here deploys; the service listens on 127.0.0.1 only.

PORT ?= 8000

.PHONY: serve

# The run service and the run-queue worker as two local processes. The worker keeps the GPU visible
# (--gpu), because the runs it launches use it; the service never needs it. Ctrl-C stops both; a run
# the worker started lives in its own session and keeps going.
serve:
	@trap 'trap - INT TERM EXIT; kill 0' INT TERM EXIT; \
	scripts/in-env.sh --gpu .venv/bin/python -m gsm8k worker & \
	scripts/in-env.sh .venv/bin/python -m gsm8k serve --port $(PORT) & \
	wait

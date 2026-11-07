"""``gsm8k serve [--port 8000]``: the run service on 127.0.0.1 only (NFR6, AC3.1.5; contract C6).

There is deliberately no option to bind another address: the service controls GPU runs and is only
for this PC. The service itself never imports training code (ADR-006); runs are launched by the
separate ``gsm8k worker`` process. uvicorn and the app are imported only when the command runs.
"""

from __future__ import annotations

import argparse

HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def _port(text: str) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected a port number, got {text!r}") from exc
    if not 1 <= value <= 65535:
        raise argparse.ArgumentTypeError(f"expected a port number from 1 to 65535, got {value}")
    return value


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "serve",
        help="serve the run service API on 127.0.0.1",
        description="Serve the run service HTTP API and live event stream on 127.0.0.1 only.",
    )
    parser.add_argument("--port", type=_port, default=DEFAULT_PORT, help="port on 127.0.0.1 (default 8000)")
    parser.set_defaults(func=serve_command)


def serve_command(args: argparse.Namespace) -> int:
    import uvicorn

    from gsm8k.service.app import create_app

    try:
        uvicorn.run(create_app(), host=HOST, port=args.port)
    except SystemExit as exc:  # uvicorn exits when it cannot bind the port
        return exc.code if isinstance(exc.code, int) else 1
    return 0

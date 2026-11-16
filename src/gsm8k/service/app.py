"""RunService: the local HTTP API (contract C6, ``/api/v1``) and live event stream (contract C7).

The service only reads and controls runs through RunControl (``gsm8k.run_control``) and RunRecords; it
never imports training or evaluation code, torch, transformers, peft, trl or lm_eval (ADR-006): a run
is launched by the worker as its own ``gsm8k`` process. It is served on 127.0.0.1 only (NFR6,
``gsm8k serve``). Every error body is the C6 Error object ``{"error": <code>, "message": <text>, ...}``.

The event stream sends the complete lines of the active run's ``metrics.jsonl`` (a line counts only
once it ends with a newline), each with the SSE id ``<run_id>:<line number>``, plus ``status`` and
``queue`` events whenever they change. Everything is read from files on each poll, so a fresh service
instance (a restart) resumes the same run, and ``Last-Event-ID`` resends only the lines after it.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import re
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated, Any

import anyio
from fastapi import Body, FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from gsm8k import reasoning_report, run_config
from gsm8k.run_control import finalists as run_finalists
from gsm8k.run_control import launch, runs, status, stop
from gsm8k.run_control import queue as run_queue
from gsm8k.run_records import paths
from gsm8k.service import course_routes, lab_routes, progress
from gsm8k.service import gpu as gpu_module

API_PREFIX = "/api/v1"
CHECK_TTL_SECONDS = 600.0  # a check expires after 10 minutes (C6, check_expired)
STREAM_POLL_SECONDS = 0.5  # a new metrics line is sent within 1 second (C7, NFR10)
STREAM_RETRY_MS = 3000  # the browser reconnects after 3 seconds (C7)
KEEPALIVE_SECONDS = 15.0  # a comment line keeps the connection alive (C7)
NO_ACTIVE_RUN = "No run is active"
SECOND_CONFIRMATION_NEEDED = "A test-split evaluation needs a second confirmation"
CHECK_EXPIRED = "This check expired; check the run again"
# Methods the website does not start in this version (US10.3, AC10.3.4); run them with the gsm8k CLI.
NOT_STARTED_FROM_SERVICE = ("cotgen", "selfcot")

_FIELD_NAMES = tuple(f.name for f in dataclasses.fields(run_config.RunConfig))
_DEFAULTS = {f.name: f.default for f in dataclasses.fields(run_config.RunConfig)}
_UNKNOWN_FIELD = re.compile(r"Unknown configuration field: ([A-Za-z0-9_]+)")
_EVENT_ID = re.compile(r"^(.+):([0-9]+)$")

logger = logging.getLogger(__name__)


class ServiceError(Exception):
    """An error answered with a C6 Error body."""

    def __init__(self, status_code: int, error: str, message: str, **extra: Any):
        super().__init__(message)
        self.status_code = status_code
        self.error = error
        self.message = message
        self.extra = {key: value for key, value in extra.items() if value is not None}


class ConfirmRequest(BaseModel):
    check_id: str
    second_confirmation: bool = False


@dataclasses.dataclass
class _Check:
    needs_second_confirmation: bool
    created: float


# --- complete-lines metrics reading (C2 metrics.jsonl) ----------------------------------------------


def read_metrics(path: Path, after: int = 0) -> tuple[list[dict], int]:
    """The complete metrics lines after the first ``after`` complete lines, and the number of complete
    lines read in all (``next``). A line counts only once it ends with a newline; a complete line that
    is not a JSON object is counted but not returned. A missing file has no lines (C2)."""
    try:
        data = Path(path).read_bytes()
    except FileNotFoundError:
        return [], max(after, 0)
    end = data.rfind(b"\n")
    if end < 0:
        return [], max(after, 0)
    raw_lines = data[: end + 1].split(b"\n")[:-1]
    lines = [obj for obj in (_parse_line(raw) for raw in raw_lines[after:]) if obj is not None]
    return lines, max(after, len(raw_lines))


def _parse_line(raw: bytes) -> dict | None:
    try:
        obj = json.loads(raw.decode("utf-8"))
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


class _MetricsTail:
    """Follows one run's metrics.jsonl by byte offset, yielding each complete line once."""

    def __init__(self, run_id: str, path: Path, skip: int = 0):
        self.run_id = run_id
        self.path = path
        self.skip = skip
        self.offset = 0
        self.count = 0

    def read_new(self) -> list[tuple[int, dict]]:
        try:
            with self.path.open("rb") as f:
                f.seek(self.offset)
                data = f.read()
        except FileNotFoundError:
            return []
        except OSError as exc:
            logger.warning("Metrics could not be read: %s (%s)", self.path, exc)
            return []
        end = data.rfind(b"\n")
        if end < 0:
            return []
        chunk = data[: end + 1]
        self.offset += len(chunk)
        new: list[tuple[int, dict]] = []
        for raw in chunk.split(b"\n")[:-1]:
            self.count += 1
            if self.count <= self.skip:
                continue
            obj = _parse_line(raw)
            if obj is not None:
                new.append((self.count, obj))
        return new


# --- payloads ----------------------------------------------------------------------------------------


def _status_payload(st: Any, outputs: Path | None, *, nested: bool = False) -> dict:
    """C6 Status from a RunControl RunStatus (``last_run`` nested the same way, with ``evaluation: null``).

    ``evaluation`` is the running run's scoring progress (AC3.1.6), read from its folder under ``outputs``;
    null when the run is not RUNNING, has no run id, or its progress cannot be told.
    """
    last = getattr(st, "last_run", None)
    evaluation = None
    if not nested and outputs is not None and st.state == status.RUNNING and st.run_id:
        evaluation = progress.evaluation_progress(outputs, st.run_id)
    return {
        "status": st.state,
        "run_id": st.run_id,
        "reason": st.reason,
        "log_tail": list(st.log_tail or []),
        "started_at": getattr(st, "started_at", None),
        "last_run": _status_payload(last, outputs, nested=True) if last is not None else None,
        "evaluation": evaluation,
    }


def _queue_payload(entries: list) -> list[dict]:
    """The waiting runs in order, each a C3 queue entry with its ``position``."""
    return [dataclasses.asdict(entry) for entry in entries]


def _change_text(dial: str, value: Any) -> str:
    """One C6 change line ``"<dial>: <old> -> <new>"`` from RunControl's changes dict value."""
    if isinstance(value, dict) and ("old" in value or "new" in value):
        old, new = value.get("old"), value.get("new")
    elif isinstance(value, list | tuple) and len(value) == 2:
        old, new = value
    else:
        return f"{dial}: {value}"
    return f"{dial}: {_plain(old)} -> {_plain(new)}"


def _plain(value: Any) -> str:
    return json.dumps(value) if value is None or isinstance(value, bool) else str(value)


def _field_of(message: str) -> str | None:
    """The configuration field a RunControl error message names, if any."""
    match = _UNKNOWN_FIELD.search(message)
    if match:
        return match.group(1)
    first = message.split(" ", 1)[0]
    if first in _FIELD_NAMES:
        return first
    if message == run_config.TEST_SPLIT_MESSAGE:
        return "split"
    if message.startswith("Adapter"):
        return "adapter_path"
    return None


def _sse(event: str | None = None, data: Any = None, event_id: str | None = None) -> str:
    parts = []
    if event is not None:
        parts.append(f"event: {event}")
    if event_id is not None:
        parts.append(f"id: {event_id}")
    parts.append("data: " + json.dumps(data, separators=(",", ":")))
    return "\n".join(parts) + "\n\n"


# --- the Training Dials (C6 GET /dials, stories.md Training Dials) -------------------------------------
#
# Bounds as run_config.validate checks them; the defaults are the RunConfig defaults, so a run started
# with untouched dials hashes the same as one started with no dials.


def _dial(
    name: str,
    label: str,
    kind: str,
    help_text: str,
    *,
    options: list | None = None,
    low: float | None = None,
    high: float | None = None,
    allow_all: bool = False,
) -> dict:
    return {
        "name": name,
        "label": label,
        "kind": kind,
        "options": options,
        "min": low,
        "max": high,
        "allow_all": allow_all,
        "default": _DEFAULTS[name],
        "help": help_text,
    }


def _or_list(values: tuple) -> str:
    """``"a, b or c"``."""
    items = [str(value) for value in values]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " or " + items[-1]


def dial_specs() -> list[dict]:
    """The eleven Training Dials in stories.md order, each a C6 DialSpec."""
    max_seed = run_config.MAX_SEED
    train_size = run_config.TRAIN_SPLIT_SIZE
    return [
        _dial("model", "Model", "select", _or_list(run_config.MODELS), options=list(run_config.MODELS)),
        _dial("learning_rate", "Learning rate", "number", "1e-5 to 5e-4", low=1e-5, high=5e-4),
        _dial("epochs", "Epochs", "integer", "1 to 3 (whole number)", low=1, high=3),
        _dial(
            "lora_rank",
            "LoRA rank",
            "select",
            _or_list(run_config.LORA_RANKS),
            options=list(run_config.LORA_RANKS),
        ),
        _dial("lora_alpha", "LoRA alpha", "integer", "1 to 128 (whole number)", low=1, high=128),
        _dial(
            "max_seq_len",
            "Max sequence length",
            "integer",
            "256 to 1024 tokens (whole number)",
            low=256,
            high=1024,
        ),
        _dial(
            "train_examples",
            "Training examples",
            "integer",
            f"50 to {train_size}, or all",
            low=50,
            high=train_size,
            allow_all=True,
        ),
        _dial("batch_size", "Batch size", "integer", "1 to 16 (whole number)", low=1, high=16),
        _dial("warmup_ratio", "Warmup ratio", "number", "0 to 0.2", low=0.0, high=0.2),
        _dial("seed", "Random seed", "integer", f"0 to {max_seed} (whole number)", low=0, high=max_seed),
        _dial(
            "answer_format",
            "Answer format",
            "select",
            _or_list(run_config.ANSWER_FORMATS),
            options=list(run_config.ANSWER_FORMATS),
        ),
    ]


# --- the application -----------------------------------------------------------------------------------


class _Service:
    """The service's state: its file locations and the check ids it handed out."""

    def __init__(self, results: Path | None, finalists: Path | None, outputs: Path | None):
        self.results = Path(results) if results is not None else paths.DEFAULT_RESULTS
        self.finalists = Path(finalists) if finalists is not None else run_finalists.FINALISTS_DEFAULT
        self._outputs = Path(outputs) if outputs is not None else None
        self.checks: dict[str, _Check] = {}

    @property
    def outputs(self) -> Path:
        return self._outputs if self._outputs is not None else paths.outputs_root()

    # errors

    def run_log_error(self, exc: Exception) -> ServiceError:
        filename = getattr(exc, "filename", None) or str(self.results)
        return ServiceError(
            500, "run_log_unreadable", f"Run log could not be read: {filename}", file=str(filename)
        )

    def finalists_error(self) -> ServiceError:
        return ServiceError(
            500,
            "finalists_unreadable",
            f"Finalists file could not be read: {self.finalists}",
            file=str(self.finalists),
        )

    def check_error(self, exc: Exception) -> ServiceError:
        """Map a RunControl refusal of a check or confirm to its C6 error."""
        message = str(exc)
        if run_finalists.NOT_A_FINALIST in message:
            return ServiceError(409, "not_finalist", run_finalists.NOT_A_FINALIST)
        if str(self.finalists) in message:
            return self.finalists_error()
        if isinstance(exc, OSError) and not isinstance(exc, FileNotFoundError | PermissionError):
            return self.run_log_error(exc)
        if isinstance(exc, PermissionError) and not getattr(exc, "filename", None):
            return ServiceError(409, "confirmation_required", message or SECOND_CONFIRMATION_NEEDED)
        return ServiceError(422, "invalid_dial", message or type(exc).__name__, field=_field_of(message))

    # reading

    def finalist_ids(self) -> list[str]:
        try:
            return run_finalists.list_finalists(self.finalists)
        except (ValueError, OSError) as exc:
            raise self.finalists_error() from exc

    def queue_entries(self) -> list:
        return run_queue.list_queue(outputs=self._outputs)

    def run_folder(self, run_id: str) -> Path:
        if not isinstance(run_id, str) or not paths.RUN_ID_PATTERN.fullmatch(run_id):
            raise ServiceError(404, "not_found", f"Run not found: {run_id}")
        return self.outputs / run_id

    def read_json_file(self, path: Path) -> dict | None:
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except (OSError, UnicodeDecodeError) as exc:
            raise ServiceError(
                500, "internal", f"Run file could not be read: {path}", file=str(path)
            ) from exc
        try:
            data = json.loads(text)
        except ValueError as exc:
            raise ServiceError(
                500, "internal", f"Run file could not be read: {path}", file=str(path)
            ) from exc
        return data if isinstance(data, dict) else None

    def stream_snapshot(self) -> tuple[Any, list[dict] | None]:
        st = status.current_status(self._outputs)
        try:
            entries = _queue_payload(self.queue_entries())
        except (OSError, ValueError) as exc:
            logger.warning("Queue could not be read: %s", exc)
            entries = None
        return st, entries


def create_app(
    *, results: Path | None = None, finalists: Path | None = None, outputs: Path | None = None
) -> FastAPI:
    """The run service. ``results`` is the run log (default results/runs.csv), ``finalists`` the C4 file
    (default results/finalists.json), ``outputs`` the outputs folder (default: ``outputs_root()`` at call
    time). Creating the app reads and writes nothing."""
    svc = _Service(results, finalists, outputs)
    app = FastAPI(
        title="gsm8k run service",
        version="1.0.0",
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
    )

    @app.exception_handler(ServiceError)
    async def _service_error(request: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(
            {"error": exc.error, "message": exc.message, **exc.extra}, status_code=exc.status_code
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        first = errors[0] if errors else {}
        loc = [
            part
            for part in first.get("loc", ())
            if isinstance(part, str) and part not in ("body", "query", "path")
        ]
        field = loc[-1] if loc else None
        text = first.get("msg", "Invalid request")
        message = f"{field}: {text}" if field else text
        body: dict[str, Any] = {"error": "invalid_dial", "message": message}
        if field:
            body["field"] = field
        return JSONResponse(body, status_code=422)

    @app.exception_handler(Exception)
    async def _internal_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unexpected service error on %s %s", request.method, request.url.path)
        body: dict[str, Any] = {"error": "internal", "message": f"Internal service error: {exc}"}
        filename = getattr(exc, "filename", None)
        if filename:
            body["file"] = str(filename)
        return JSONResponse(body, status_code=500)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = str(exc.detail) if exc.detail else "Not found"
        return JSONResponse(
            {"error": "not_found", "message": message}, status_code=exc.status_code, headers=exc.headers
        )

    # --- lab (contract C8; error codes lab_busy, no_lab_run) ---

    lab_routes.register(app, API_PREFIX, lambda: svc.outputs, ServiceError)

    # --- course (contract C9; error codes course_busy, queue_full, use_lab, nothing_to_run,
    #     invalid_answers, invalid_text, progress_unreadable) ---

    course_routes.register(app, API_PREFIX, lambda: svc.outputs, ServiceError)

    # --- runs ---

    @app.get(f"{API_PREFIX}/runs")
    def list_runs() -> dict:
        try:
            summaries, skipped = runs.list_runs(svc.results, svc._outputs)
        except (OSError, ValueError) as exc:
            raise svc.run_log_error(exc) from exc
        chosen = set(svc.finalist_ids()) if summaries else set()
        return {
            "runs": [{**dataclasses.asdict(s), "finalist": s.run_id in chosen} for s in summaries],
            "skipped_rows": skipped,
        }

    @app.post(f"{API_PREFIX}/runs/check")
    def check_run(dials: Annotated[dict[str, Any], Body()]) -> dict:
        if "run_id" in dials:
            raise ServiceError(
                422, "invalid_dial", "run_id is chosen by the service, not given", field="run_id"
            )
        method = dials.get("method")
        if isinstance(method, str) and method in NOT_STARTED_FROM_SERVICE:
            raise ServiceError(
                422,
                "invalid_dial",
                f"method {method} is not started from the website; run it with the gsm8k command line",
                field="method",
            )
        kind = "train" if method in run_config.TRAINING_METHODS else "evaluate"
        try:
            checked = launch.check_run(
                dict(dials), kind=kind, results=svc.results, finalists=svc.finalists, outputs=svc._outputs
            )
        except run_queue.QueueFull as exc:
            raise ServiceError(409, "queue_full", str(exc)) from exc
        except (run_config.ConfigError, ValueError, OSError, LookupError) as exc:
            raise svc.check_error(exc) from exc
        config = checked.config if isinstance(checked.config, dict) else {}
        needs_second = bool(getattr(checked, "needs_second_confirmation", False)) or (
            kind == "evaluate" and config.get("split") == "test"
        )
        now = time.monotonic()
        for check_id in [k for k, c in svc.checks.items() if now - c.created > CHECK_TTL_SECONDS]:
            del svc.checks[check_id]
        svc.checks[checked.check_id] = _Check(needs_second_confirmation=needs_second, created=now)
        try:
            waiting = len(svc.queue_entries())
        except (OSError, ValueError):
            waiting = 0
        changes = checked.changes if isinstance(checked.changes, dict) else {}
        estimate = checked.estimate
        return {
            "check_id": checked.check_id,
            "attempt_id": checked.attempt_id,
            "model": checked.model,
            "method": checked.method,
            "kind": kind,
            "changes": [_change_text(dial, value) for dial, value in changes.items()],
            "estimate_s": estimate.seconds,
            "estimate_text": estimate.text,
            "over_cap": bool(estimate.over_cap),
            "command": [str(part) for part in checked.argv],
            "command_text": checked.command,
            "queue_position": waiting + 1,
            "needs_second_confirmation": needs_second,
            "config": config,
        }

    @app.post(f"{API_PREFIX}/runs/confirm")
    def confirm_run(body: ConfirmRequest) -> dict:
        check = svc.checks.get(body.check_id)
        if check is None:
            raise ServiceError(404, "not_found", f"No checked run with this id: {body.check_id}")
        if time.monotonic() - check.created > CHECK_TTL_SECONDS:
            del svc.checks[body.check_id]
            raise ServiceError(404, "check_expired", CHECK_EXPIRED)
        if check.needs_second_confirmation and not body.second_confirmation:
            raise ServiceError(409, "confirmation_required", SECOND_CONFIRMATION_NEEDED)
        try:
            result = launch.confirm(body.check_id, second_confirmation=body.second_confirmation)
        except run_queue.QueueFull as exc:
            raise ServiceError(409, "queue_full", str(exc)) from exc
        except launch.CheckExpired as exc:
            svc.checks.pop(body.check_id, None)
            raise ServiceError(404, "check_expired", str(exc) or CHECK_EXPIRED) from exc
        except launch.SecondConfirmationNeeded as exc:
            raise ServiceError(409, "confirmation_required", str(exc) or SECOND_CONFIRMATION_NEEDED) from exc
        except LookupError as exc:
            raise ServiceError(404, "not_found", f"No checked run with this id: {body.check_id}") from exc
        except (run_config.ConfigError, ValueError, OSError) as exc:
            raise svc.check_error(exc) from exc
        svc.checks.pop(body.check_id, None)
        return {
            "attempt_id": result.attempt_id,
            "state": result.state,
            "position": getattr(result, "position", None),
        }

    @app.get(f"{API_PREFIX}/runs/{{run_id}}")
    def run_detail(run_id: str) -> dict:
        folder = svc.run_folder(run_id)
        if not folder.is_dir():
            try:
                summaries, _ = runs.list_runs(svc.results, svc._outputs)
            except (OSError, ValueError) as exc:
                raise svc.run_log_error(exc) from exc
            if not any(s.run_id == run_id for s in summaries):
                raise ServiceError(404, "not_found", f"Run not found: {run_id}")
        run_state = svc.read_json_file(folder / "status.json")
        if run_state is None:
            current = status.current_status(svc._outputs)
            run_state = {"status": "running", "run_id": run_id} if current.run_id == run_id else {}
        return {
            "run_id": run_id,
            "config": svc.read_json_file(folder / "config.json") or {},
            "status": run_state,
            "timings": svc.read_json_file(folder / "timings.json") or {},
        }

    @app.get(f"{API_PREFIX}/runs/{{run_id}}/metrics")
    def run_metrics(run_id: str, after: Annotated[int, Query(ge=0)] = 0) -> dict:
        path = svc.run_folder(run_id) / "metrics.jsonl"
        try:
            lines, next_line = read_metrics(path, after)
        except OSError as exc:
            raise ServiceError(500, "internal", f"Metrics could not be read: {path}", file=str(path)) from exc
        return {"lines": lines, "next": next_line}

    # --- dials ---

    @app.get(f"{API_PREFIX}/dials")
    def get_dials() -> dict:
        return {"dials": dial_specs()}

    # --- the GPU's live figures (US4.5, AC4.5.9) ---

    @app.get(f"{API_PREFIX}/gpu")
    def get_gpu() -> dict:
        return gpu_module.read_gpu()  # never raises: an unreadable GPU is `available: false`, still 200

    # --- reasoning (US10.3) ---

    @app.get(f"{API_PREFIX}/reasoning")
    def get_reasoning(model: str = reasoning_report.DEFAULT_MODEL) -> dict:
        try:
            return reasoning_report.build_reasoning(model, svc.results, svc.outputs)
        except reasoning_report.UnknownModel as exc:
            raise ServiceError(422, "invalid_dial", str(exc), field="model") from exc
        except OSError as exc:
            raise svc.run_log_error(exc) from exc

    # --- status and stop ---

    @app.get(f"{API_PREFIX}/status")
    def get_status() -> dict:
        return _status_payload(status.current_status(svc._outputs), svc.outputs)

    @app.post(f"{API_PREFIX}/stop")
    def stop_run() -> dict:
        before = status.current_status(svc._outputs)
        if before.state != status.RUNNING:
            raise ServiceError(409, "no_active_run", NO_ACTIVE_RUN)
        try:
            message = stop.stop_active(outputs=svc._outputs)
        except Exception as exc:  # the service's own failure (C6 internal)
            logger.exception("Stopping run %s failed", before.run_id)
            raise ServiceError(500, "internal", f"The run could not be stopped: {exc}") from exc
        if NO_ACTIVE_RUN in message:
            raise ServiceError(409, "no_active_run", NO_ACTIVE_RUN)
        if before.run_id is not None:
            try:
                return _status_payload(status.run_status(before.run_id, svc._outputs), svc.outputs)
            except (LookupError, ValueError):
                pass
        return _status_payload(status.current_status(svc._outputs), svc.outputs)

    # --- queue ---

    @app.get(f"{API_PREFIX}/queue")
    def get_queue() -> dict:
        return {"entries": _queue_payload(svc.queue_entries())}

    @app.delete(f"{API_PREFIX}/queue/{{attempt_id}}", status_code=204)
    def remove_queued(attempt_id: str) -> Response:
        if attempt_id not in [entry.attempt_id for entry in svc.queue_entries()]:
            raise ServiceError(404, "not_found", f"Not in the queue: {attempt_id}")
        try:
            run_queue.remove(attempt_id, outputs=svc._outputs)
        except (LookupError, FileNotFoundError) as exc:
            raise ServiceError(404, "not_found", f"Not in the queue: {attempt_id}") from exc
        return Response(status_code=204)

    # --- finalists ---

    @app.get(f"{API_PREFIX}/finalists")
    def get_finalists() -> dict:
        return {"finalists": svc.finalist_ids()}

    @app.put(f"{API_PREFIX}/finalists/{{run_id}}")
    def mark_finalist(run_id: str) -> dict:
        try:
            run_finalists.mark(svc.finalists, run_id, svc.results)
        except LookupError as exc:
            raise ServiceError(404, "not_found", f"Run not found in the run log: {run_id}") from exc
        except ValueError as exc:
            raise svc.finalists_error() from exc
        except OSError as exc:
            raise svc.run_log_error(exc) from exc
        return {"finalists": svc.finalist_ids()}

    @app.delete(f"{API_PREFIX}/finalists/{{run_id}}")
    def unmark_finalist(run_id: str) -> dict:
        try:
            run_finalists.unmark(svc.finalists, run_id)
        except (ValueError, OSError) as exc:
            raise svc.finalists_error() from exc
        return {"finalists": svc.finalist_ids()}

    # --- live events (C7) ---

    @app.get(f"{API_PREFIX}/stream")
    async def stream(request: Request) -> StreamingResponse:
        resume = _EVENT_ID.match(request.headers.get("last-event-id", "").strip())
        resume_at = (resume.group(1), int(resume.group(2))) if resume else None
        return StreamingResponse(
            _events(svc, resume_at),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


async def _events(svc: _Service, resume_at: tuple[str, int] | None) -> AsyncIterator[str]:
    """The C7 event stream: retry first, then metric, status and queue events as they change."""
    yield f"retry: {STREAM_RETRY_MS}\n\n"
    tail: _MetricsTail | None = None
    last_status: dict | None = None
    last_queue: list[dict] | None = None
    last_sent = time.monotonic()
    while True:
        chunks: list[str] = []
        try:
            st, entries = svc.stream_snapshot()
        except (OSError, ValueError) as exc:
            logger.warning("Status could not be read: %s", exc)
            st, entries = None, None
        running = st is not None and st.state == status.RUNNING and st.run_id is not None
        if running and (tail is None or tail.run_id != st.run_id):
            if tail is not None:  # the previous run's last lines come first
                chunks.extend(_metric_chunks(tail))
            skip = resume_at[1] if resume_at is not None and resume_at[0] == st.run_id else 0
            tail = _MetricsTail(st.run_id, svc.outputs / st.run_id / "metrics.jsonl", skip)
        if tail is not None:
            chunks.extend(_metric_chunks(tail))
            if not running:
                tail = None
        if st is not None:
            payload = _status_payload(st, svc.outputs)
            if payload != last_status:
                chunks.append(_sse("status", payload))
                last_status = payload
        if entries is not None and entries != last_queue:
            chunks.append(_sse("queue", {"entries": entries}))
            last_queue = entries
        now = time.monotonic()
        if chunks:
            yield "".join(chunks)
            last_sent = now
        elif now - last_sent >= KEEPALIVE_SECONDS:
            yield ": keep-alive\n\n"
            last_sent = now
        await anyio.sleep(STREAM_POLL_SECONDS)


def _metric_chunks(tail: _MetricsTail) -> list[str]:
    return [
        _sse("metric", {**line, "run_id": tail.run_id}, event_id=f"{tail.run_id}:{number}")
        for number, line in tail.read_new()
    ]

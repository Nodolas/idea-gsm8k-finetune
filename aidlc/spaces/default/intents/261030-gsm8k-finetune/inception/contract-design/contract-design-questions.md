# Contract Design: Questions

The boundaries to pin down, from `inception/units-generation/unit-of-work-dependency.md` (Integration Points) and `inception/domain-design/components.md`:

- the run files every Python unit shares through RunRecords (`results/runs.csv`, `results/finalists.json`, `outputs/<run_id>/`, the lock and the queue), owned by u1-eval-skeleton and extended by u3-sft and u4-run-service
- the `gsm8k` commands that the worker in u4-run-service launches as processes (`gsm8k evaluate`, `gsm8k train`)
- the HTTP API from u4-run-service to u5-website
- the live metrics stream from u4-run-service to u5-website

Already settled: localhost only, no accounts, no free-form commands (NFR6); FastAPI with Server-Sent Events (brief); the run-log columns `date, run_id, model, method, data, metric, value, minutes, config_hash` (FR1.6); one metrics JSON line per logging step (FR2.3). Nothing is exposed outside this PC, so there is no external API.

## Q1. [Architect] How should the shared run files handle format changes?

`results/runs.csv` and `results/finalists.json` are committed and grow over weeks of runs, so a format change meets old rows.

A. Versioned and append-only: run-log columns are only ever added at the end and old rows stay valid with empty new cells; every metrics line, lock, queue entry and run-folder `config.json` carries `"v": 1`; a breaking change needs a dated `inception/changes.md` line and a small migration command
B. No versioning: change the formats freely and rewrite old files by hand if needed
X. Other (please specify)

[Answer]: A. Versioned and append-only

## Q2. [Architect] How should the `gsm8k` commands report how a run ended to the worker?

The worker launches `gsm8k evaluate` and `gsm8k train` as separate processes. The domain-design review (R-02) asked what happens when a terminal run takes the lock between the worker's check and the launched process.

A. Fixed exit codes plus a final status file: 0 finished, 1 failed (reason in `outputs/<run_id>/status.json`), 2 invalid configuration, 3 lock held, 130 stopped. On exit code 3 the worker puts the queue entry back at the head and waits for the lock; it removes an entry from the queue only once its process holds the lock
B. Only zero or non-zero; the worker reads the reason from the end of the log
X. Other (please specify)

[Answer]: A. Fixed exit codes plus a final status file; on exit code 3 the entry goes back to the head of the queue

## Q3. [Architect] How should live metrics reach the training page?

New metrics lines must show on the page within 5 seconds (NFR10), and the page must recover after a dropped connection (AC4.5.3).

A. Server-Sent Events: one `metric` event per complete metrics line with the line number as the event id, so a reconnect with `Last-Event-ID` resumes without gaps; plus `status` and `queue` events when either changes; the browser reconnects on its own after 3 s
B. Polling: the page asks for new lines after the last line number every 2 seconds
X. Other (please specify)

[Answer]: A. Server-Sent Events with line-number ids and resume, plus status and queue events

## Q4. [Architect] What conventions should the HTTP API follow?

The website and the service always ship together from the same `main`, on one PC.

A. Paths under `/api/v1`; JSON bodies with snake_case fields matching the run files; errors as `{"error": <code>, "message": <text>, "field" or "file": <name>}` with 4xx for your input and 5xx for the service's own failures; no backward compatibility beyond v1 since both sides change together
B. No version prefix and plain-text error messages
X. Other (please specify)

[Answer]: A. `/api/v1`, snake_case JSON, error objects, no compatibility beyond v1

## Consolidated Summary Confirmation

- The shared run files are versioned and append-only: run-log columns are only ever added at the end and old rows stay valid; metrics lines, the lock, queue entries and each run's `config.json` carry `"v": 1`; a breaking change needs a dated `inception/changes.md` line and a small migration command.
- The `gsm8k` commands end with fixed exit codes: 0 finished, 1 failed (reason in `outputs/<run_id>/status.json`), 2 invalid configuration, 3 lock held, 130 stopped. The worker removes a queue entry only once its process holds the lock, and on exit code 3 puts it back at the head and waits.
- Live metrics reach the training page over Server-Sent Events: one `metric` event per complete metrics line with the line number as its id, so a reconnect resumes without gaps; `status` and `queue` events when either changes; the browser reconnects after 3 seconds.
- The HTTP API lives under `/api/v1` on 127.0.0.1, with snake_case JSON matching the run files and errors as `{"error", "message", "field" or "file"}`: 4xx for bad input, 5xx for the service's own failures. There is no compatibility beyond v1, because the website and the service always ship together.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct

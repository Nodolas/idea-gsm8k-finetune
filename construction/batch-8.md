# batch-8: the worker waits while another project's run holds the GPU (u4-run-service)

Branch `wip/batch-8`. Spec: approved commit 37fb5a4 plus the `spec(` commits since, the last being `spec(u4-run-service): the worker waits while another project's run holds the GPU` (`inception/changes.md`, last line). `test_command`: `scripts/check.sh`, on the CPU through `scripts/in-env.sh`.

Why now: charter rule 3 (factory `7a3fadf`, refreshed here in `chore(charter)`) lets several projects build at the same time, with one GPU run at a time across projects. `scripts/run-detached.sh` (factory template, `chore(skill)`) refuses to start a run while another long run or GPU process is on this PC, and `--check` runs only that check. The worker (`gsm8k worker`) launched queued runs with only this project's lock in view, so it could start a run next to another project's run on the 8 GB GPU. Nico, 2026-11-08, in the factory session: "address the gap". Built and reviewed in the factory session (a clone of this repo; reviewer PASS after fixes), then replayed here as this batch. A training run (`q17-cotgen-train-1`) is using the GPU: nothing here touches it (CPU tests only).

## Criteria

AC3.7.7 (part W), in `S/inception/user-stories/stories.md` (`S` = `aidlc/spaces/default/intents/261030-gsm8k-finetune`), story US3.7.

## Parts

Part W, worker GPU check (AC3.7.7). Owns `src/gsm8k/run_control/worker.py`. Tests: new `test_AC3_7_7_*` tests appended to `tests/test_u4_queue_worker.py`.
- `run_gpu_check() -> (code, text)` runs `scripts/run-detached.sh --check` (cwd ROOT, 30 s timeout): 0 free, 3 busy (its `busy:` lines), 4 nvidia-smi failed or the check timed out, -1 when it cannot run (missing script). `gpu_check` is the seam the tests stub (read at call time).
- `Worker.step()`: lock free and a queue head, then `_gpu_free()`, then the launch. On 3 or 4: no launch, the head and the order stay, the message is logged once until it changes, the next check comes at most every `GPU_RECHECK_SECONDS` (10). Any other code: logged once, the lock decides as before.

Lead, shared test helper: `tests/conftest.py` gains an autouse fixture that points `worker.gpu_check` at a free answer, so every other test is independent of this PC's GPU (the AC3.7.7 tests set their own stub).

## Rules

Tests named by criterion ID; no existing test line changed or deleted; tests committed before the code; CPU only; Ruff clean (line length 110).

#!/usr/bin/env bash
# run-detached: long runs (over about 10 minutes) go through the factory's GPU queue (/build 3.4, CHARTER rule 3).
# The contract is docs/gpu-queue.md in the factory repo.
#   scripts/run-detached.sh <attempt id> <tool> [args...]   submit: writes .gpu-jobs/<attempt id>.json (queued)
#   scripts/run-detached.sh --check                         only the GPU check below: exit 0 free, 3 busy, 4 failed
#   scripts/run-detached.sh --status <attempt id>           queued <n> of <m> | queued | running <pid> | ended <code>
#   scripts/run-detached.sh --cancel <attempt id>           deletes a queued job; a running one is not cancelled
# Submit: the attempt id is <base id>-<n>; <tool> must be a project tool (the list in scripts/in-env.sh); the
# command must carry --run-id <attempt id> (or --run-id=<attempt id>), so the run is seen as a long run and as
# alive from its first second. Any of these wrong, or a job with that id already there: exit 2. With a GPU
# orchestrator running (a fresh .gpu-jobs/orchestrator.json, heartbeat at most 30 s old, or a live
# gpu-orchestrator.py process) it prints "queued <id>" and the orchestrator starts the run when the GPU is free,
# in submit order across projects. With none running it starts the run itself if the GPU is free
# ("running <id> <pid> ..."), else the job stays queued until an orchestrator runs (exit 4 when nvidia-smi
# failed). A run gets the GPU and this folder's caches
# (scripts/in-env.sh --gpu), its own session (setsid), and its log at outputs/<attempt id>/run.log.
# --status prints one line (exit 1 and "unknown" with no job file); a running job whose process is gone is
# "ended unknown". --cancel: "cancelled <id>" (exit 0), else exit 1.
# GPU check: one GPU run at a time on this PC, across projects: busy while another long run or a GPU process is up.
# Every long run carries --run-id from its first second, while nvidia-smi lists a process only once it has opened
# the GPU, so both are checked. Exit 3: busy, each holder printed as "busy: <pid> <command>". Exit 4: nvidia-smi
# failed or gave no answer within 10 s. Project code that starts a GPU run itself (a queue worker) runs --check
# right before it and waits while it exits 3 or 4. --check reads processes and nvidia-smi only, never .gpu-jobs/.
set -u; ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
usage() { echo "usage: scripts/run-detached.sh <attempt id> <tool> [args...] | --check | --status <attempt id> | --cancel <attempt id>" >&2; exit 2; }
check_id() { [[ $1 =~ ^[a-z0-9][a-z0-9._-]*-[0-9]+$ ]] || { echo "run-detached: bad attempt id: $1" >&2; exit 2; }; }

# The GPU check (--check, and submit with no orchestrator running): returns 0 free, 3 busy, 4 nvidia-smi failed.
gpu_check() {
  local busy gpu p a
  # Long runs anywhere on this PC. Left out: this script and the shell that called it (they name run-detached.sh),
  # and `sh -c` shells that only mention --run-id (a session's command wrapper, a wait loop); no run starts that way.
  busy=$(pgrep -af -- '--run-id' | grep -vE -e 'run-detached\.sh' -e '^[0-9]+ ([^ ]*/)?(ba|da|z)?sh -c ' || true)
  gpu=$(timeout 10 nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null) || { echo "run-detached: nvidia-smi failed: $(timeout 10 nvidia-smi 2>&1 | head -n 3)" >&2; return 4; }
  while read -r p; do
    [[ $p =~ ^[0-9]+$ ]] && [ -e "/proc/$p" ] || continue   # a pid that ended meanwhile no longer counts
    a=$(ps -o args= -p "$p" 2>/dev/null) || a="(process not visible)"
    busy+=$'\n'"$p $a"
  done <<<"$gpu"
  busy=$(printf '%s\n' "$busy" | sed '/^[[:space:]]*$/d' | sort -u -k1,1n)
  if [ -n "$busy" ]; then sed 's/^/busy: /' <<<"$busy" >&2; return 3; fi
  return 0
}

# A live orchestrator process: python running gpu-orchestrator.py, not a one-tick (--once) or read-only (--status) call.
# It covers a project's first submit, before the orchestrator has written orchestrator.json into the new .gpu-jobs/.
orch_process() {
  pgrep -af -- 'gpu-orchestrator\.py' \
    | grep -E '^[0-9]+ ([^ ]*/)?python[0-9.]*( [^ ]+)* ([^ ]*/)?gpu-orchestrator\.py( |$)' \
    | grep -qvE ' --(once|status)( |$)'
}

# JSON through python3 -I (jq may be missing; -I imports no project module). Its own command line never holds
# --run-id, so the GPU check elsewhere never counts it; a job's argv comes on stdin. Exit 1 on errors.
read -r -d '' PY <<'PYEOF'
import datetime, json, os, sys

UTC = datetime.timezone.utc
VIEW = os.path.join(".gpu-jobs", "orchestrator.json")


def now():
    return datetime.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def job_path(jid):
    return os.path.join(".gpu-jobs", jid + ".json")


def write_atomic(path, obj, new=False):
    tmp = "%s.tmp.%d" % (path, os.getpid())
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        if new:
            os.link(tmp, path)  # never replaces an existing job file
        else:
            os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def load(path):
    with open(path, encoding="utf-8") as f:
        job = json.load(f)
    if not isinstance(job, dict) or job.get("state") not in ("queued", "running", "ended"):
        raise ValueError("%s is not a job file" % path)
    return job


def fresh_view():
    try:
        with open(VIEW, encoding="utf-8") as f:
            view = json.load(f)
        hb = datetime.datetime.fromisoformat(view["heartbeat"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if hb.tzinfo is None:
        hb = hb.replace(tzinfo=UTC)
    return view if (datetime.datetime.now(UTC) - hb).total_seconds() <= 30 else None


def alive(pid, jid):
    if type(pid) is not int or pid <= 0:
        return False
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as f:
            cmd = f.read()
    except OSError:
        return False
    return jid.encode() in cmd.replace(b"\0", b" ")


def effective(job, jid):
    state = job["state"]
    if state == "running":
        return "running %d" % job["pid"] if alive(job.get("pid"), jid) else "ended unknown"
    if state == "ended":
        code = job.get("exit_code")
        return "ended %s" % (code if type(code) is int else "unknown")
    return "queued"


def main(cmd, args):
    if cmd == "new":
        jid = args[0]
        argv = [os.fsdecode(a) for a in sys.stdin.buffer.read().split(b"\0")[:-1]]
        job = {"v": 1, "id": jid, "argv": argv, "submitted_at": now(), "state": "queued", "pid": None,
               "started_at": None, "started_by": None, "ended_at": None, "exit_code": None,
               "log": "outputs/%s/run.log" % jid}
        try:
            write_atomic(job_path(jid), job, new=True)
        except FileExistsError:
            print("run-detached: already submitted: %s" % job_path(jid), file=sys.stderr)
            return 2
        return 0
    if cmd == "fresh":
        return 0 if fresh_view() is not None else 1
    if cmd == "start":
        jid, pid = args
        job = load(job_path(jid))
        job.update(state="running", pid=int(pid), started_at=now(), started_by="run-detached")
        write_atomic(job_path(jid), job)
        return 0
    if cmd in ("status", "cancel"):
        jid = args[0]
        try:
            job = load(job_path(jid))
        except FileNotFoundError:
            print("unknown")
            return 1
        line = effective(job, jid)
        if cmd == "cancel":
            if line == "queued":
                os.unlink(job_path(jid))
                print("cancelled " + jid)
                return 0
            print(line + ": not cancelled")
            return 1
        project, orch_process = args[1], args[2] == "1"
        if line == "queued":
            view = fresh_view()
            if view is not None:
                queue = view.get("queue")
                queue = queue if isinstance(queue, list) else []
                for i, e in enumerate(queue, 1):
                    if isinstance(e, dict) and e.get("project") == project and e.get("id") == jid:
                        line = "queued %d of %d" % (i, len(queue))
                        break
            elif not orch_process:
                line += " (no GPU orchestrator running)"
        print(line)
        return 0
    raise ValueError("unknown command " + cmd)


try:
    sys.exit(main(sys.argv[1], sys.argv[2:]))
except Exception as e:
    print("run-detached: %s" % e, file=sys.stderr)
    sys.exit(1)
PYEOF
py() { python3 -I -c "$PY" "$@"; }

case "${1:-}" in
  --check) shift; [ $# -eq 0 ] || usage; gpu_check; exit $?;;
  --status) [ $# -eq 2 ] || usage; check_id "$2"; o=0; orch_process && o=1; py status "$2" "${ROOT##*/}" "$o"; exit $?;;
  --cancel) [ $# -eq 2 ] || usage; check_id "$2"; py cancel "$2"; exit $?;;
esac

# Submit.
[ $# -ge 2 ] || usage
id=$1; shift
check_id "$id"
case "$1" in
  .venv/bin/*|./.venv/bin/*|.tools/*|./.tools/*|python|python3|pip|uv|npm|npx|node) ;;
  *) echo "run-detached: not a project tool: $1" >&2; exit 2;;
esac
case "$1" in *..*) echo "run-detached: no .. in the tool path" >&2; exit 2;; esac
r=0; p=
for a in "$@"; do
  { [ "$p" = --run-id ] && [ "$a" = "$id" ]; } || [ "$a" = "--run-id=$id" ] && r=1
  p=$a
done
((r)) || { echo "run-detached: the command must carry --run-id $id" >&2; exit 2; }
mkdir -p .gpu-jobs || exit 1
printf '%s\0' "$@" | py new "$id" || exit
if py fresh || orch_process; then echo "queued $id"; exit 0; fi
# No orchestrator running: start the run here if the GPU is free, as before the queue existed.
gpu_check; rc=$?
queued="queued $id (no GPU orchestrator running; it starts once the orchestrator runs)"
[ "$rc" = 3 ] && { echo "$queued"; exit 0; }
[ "$rc" = 4 ] && { echo "$queued"; exit 4; }
mkdir -p "outputs/$id"
setsid nohup scripts/in-env.sh --gpu "$@" > "outputs/$id/run.log" 2>&1 < /dev/null &
pid=$!
py start "$id" "$pid"; marked=$?
sleep 1
kill -0 "$pid" 2>/dev/null || { wait "$pid"; rc=$?; [ "$rc" = 2 ] && { tail -n 3 "outputs/$id/run.log" >&2; exit 2; }; }
echo "running $id $pid (no GPU orchestrator running)"
exit $((marked != 0))

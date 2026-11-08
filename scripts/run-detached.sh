#!/usr/bin/env bash
# run-detached: start a long run (over about 10 minutes) so it outlives the session (/build 3.4).
#   scripts/run-detached.sh <attempt id> <tool> [args...]   prints the process id
#   scripts/run-detached.sh --check                         only the GPU check below: exit 0 free, 3 busy, 4 failed
# The run gets the GPU and this folder's caches (scripts/in-env.sh --gpu checks the tool), its own
# session (setsid), and its log at outputs/<attempt id>/run.log. The attempt id is <base id>-<n>.
# One GPU run at a time on this PC, across projects (CHARTER rule 3): it starts nothing while another long run
# or a GPU process is up. Every long run carries --run-id from its first second, while nvidia-smi lists a
# process only once it has opened the GPU, so both are checked. Exit 3: busy, each holder printed as
# "busy: <pid> <command>" (the run stays queued, /build 3.4). Exit 4: nvidia-smi failed. Project code that starts
# a GPU run itself (a queue worker) runs --check right before it and waits while it exits 3 or 4.
set -u; ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
usage() { echo "usage: scripts/run-detached.sh <attempt id> <tool> [args...] | --check" >&2; exit 2; }
check=0; [ "${1:-}" = --check ] && { check=1; shift; [ $# -eq 0 ] || usage; }
if ((!check)); then
  [ $# -ge 2 ] || usage
  id=$1; shift
  [[ $id =~ ^[a-z0-9][a-z0-9._-]*-[0-9]+$ ]] || { echo "run-detached: bad attempt id: $id" >&2; exit 2; }
fi
# Long runs anywhere on this PC. Left out: this script and the shell that called it (they name run-detached.sh),
# and `sh -c` shells that only mention --run-id (a session's command wrapper, a wait loop); no run starts that way.
busy=$(pgrep -af -- '--run-id' | grep -vE -e 'run-detached\.sh' -e '^[0-9]+ ([^ ]*/)?(ba|da|z)?sh -c ' || true)
gpu=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null) || { echo "run-detached: nvidia-smi failed: $(nvidia-smi 2>&1 | head -n 3)" >&2; exit 4; }
while read -r p; do
  [[ $p =~ ^[0-9]+$ ]] && [ -e "/proc/$p" ] || continue   # a pid that ended meanwhile no longer counts
  a=$(ps -o args= -p "$p" 2>/dev/null) || a="(process not visible)"
  busy+=$'\n'"$p $a"
done <<<"$gpu"
busy=$(printf '%s\n' "$busy" | sed '/^[[:space:]]*$/d' | sort -u -k1,1n)
if [ -n "$busy" ]; then sed 's/^/busy: /' <<<"$busy" >&2; exit 3; fi
((check)) && exit 0
mkdir -p "outputs/$id"
setsid nohup scripts/in-env.sh --gpu "$@" > "outputs/$id/run.log" 2>&1 < /dev/null &
pid=$!; sleep 1
kill -0 "$pid" 2>/dev/null || { wait "$pid"; rc=$?; [ "$rc" = 2 ] && { tail -n 3 "outputs/$id/run.log" >&2; exit 2; }; }
echo "$pid"

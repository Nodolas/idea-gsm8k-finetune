#!/usr/bin/env bash
# run-detached: start a long run (over about 10 minutes) so it outlives the session (/build 3.4).
#   scripts/run-detached.sh <attempt id> <tool> [args...]   prints the process id
# The run gets the GPU and this folder's caches (scripts/in-env.sh --gpu checks the tool), its own
# session (setsid), and its log at outputs/<attempt id>/run.log. The attempt id is <base id>-<n>.
set -u; ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
[ $# -ge 2 ] || { echo "usage: scripts/run-detached.sh <attempt id> <tool> [args...]" >&2; exit 2; }
id=$1; shift
[[ $id =~ ^[a-z0-9][a-z0-9._-]*-[0-9]+$ ]] || { echo "run-detached: bad attempt id: $id" >&2; exit 2; }
mkdir -p "outputs/$id"
setsid nohup scripts/in-env.sh --gpu "$@" > "outputs/$id/run.log" 2>&1 < /dev/null &
pid=$!; sleep 1
kill -0 "$pid" 2>/dev/null || { wait "$pid"; rc=$?; [ "$rc" = 2 ] && { tail -n 3 "outputs/$id/run.log" >&2; exit 2; }; }
echo "$pid"

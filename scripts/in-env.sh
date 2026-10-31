#!/usr/bin/env bash
# in-env: run one project tool with this folder's caches (CLAUDE.md, rule 8), on the CPU unless --gpu.
#   scripts/in-env.sh [--gpu] <tool> [args...]
# <tool> must be a project tool: .venv/bin/*, .tools/*, python, python3, pip, uv, npm, npx, node.
# Anything else exits 2, so the allow rule for this script never runs git, gh or other commands.
# Used for test_command, installs and builder runs; long runs go through scripts/run-detached.sh.
set -u; ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
gpu=0; [ "${1:-}" = --gpu ] && { gpu=1; shift; }
[ $# -ge 1 ] || { echo "usage: scripts/in-env.sh [--gpu] <tool> [args...]" >&2; exit 2; }
case "$1" in
  .venv/bin/*|./.venv/bin/*|.tools/*|./.tools/*|python|python3|pip|uv|npm|npx|node) ;;
  *) echo "in-env: not a project tool: $1" >&2; exit 2;;
esac
case "$1" in *..*) echo "in-env: no .. in the tool path" >&2; exit 2;; esac
# No publishing, deploying, logins or installs outside this folder through here (rule 4, rule 8).
for a in "$@"; do case "$a" in
  publish|deploy|login|adduser|--user|--global|-g|--prefix|--prefix=*|--target|--target=*|--root|--root=*|--system)
    echo "in-env: refused argument: $a" >&2; exit 2;;
esac; done
export HF_HOME="$ROOT/.cache/huggingface" PIP_CACHE_DIR="$ROOT/.cache/pip" XDG_CACHE_HOME="$ROOT/.cache" \
  TRITON_CACHE_DIR="$ROOT/.cache/triton" TORCHINDUCTOR_CACHE_DIR="$ROOT/.cache/torchinductor" TORCH_HOME="$ROOT/.cache/torch" \
  npm_config_cache="$ROOT/.cache/npm"
[ -d "$ROOT/.tools/node/bin" ] && export PATH="$ROOT/.tools/node/bin:$PATH"
((gpu)) || export CUDA_VISIBLE_DEVICES=""
exec "$@"

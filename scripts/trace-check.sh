#!/usr/bin/env bash
# trace-check: spec <-> tests drift check. Prints "trace-check: PASS", or "trace-check: FAIL" and exits 1.
# Mode aidlc (STATE.md says engine: aidlc, or has a spec_path): AI-DLC 2.11.1 files under spec_path.
#   Criteria: the AC IDs (AC1.2.1) in stories.md, or the leaf FR IDs (FR1.2) when User Stories was skipped.
#   Each criterion is named by a test in tests/ (AC1_2_1 or AC1.2.1), or marked [manual] on its line, or
#   sits in a unit (story map) whose code-generation/code-summary.md does not exist yet.
#   Every AC, FR and NFR ID a test names exists; one FR line carries "(loop)" (charter rule 2).
#   AI-DLC's own traceability sensor runs too when aidlc is on PATH; its result is info only
#   (AIDLC_SENSOR=0 skips it).
# Mode sdd (else): inception/requirements.md criteria R<n>.<m>, construction/tasks.md slices, tests.
# Both modes: STATE.md track: learning (quoted or not) skips the (loop) check and prints an info line
#   (CHARTER "Learning projects"); every other check stays. No track line, or any other value, is a product.
# A test names an ID only in its test name, in both modes: Python (.py) "def test_AC1_2_1_x(" (async too),
#   JS/TS (.js .jsx .ts .tsx .mjs .cjs .mts .cts) the title string of it("AC1.2.1 x", or test(, also
#   .only and .concurrent, title on the same or the next line. IDs in comments, docstrings, test bodies,
#   data files, describe(), .skip, .todo and .each do not count.
# --spec-files prints every spec file path (from the repo root), existing or not, so git diff, git status
#   and git log also see a deleted one. git add and git restore fail on a path git does not know, so filter
#   the list first. git add takes "git ls-files --cached --others --exclude-standard -- <list>" (new files
#   too). git restore takes only tracked paths: "git ls-files --cached -- <list>", or --modified --deleted.
#   A restore leaves a new untracked spec file; "git ls-files --others --exclude-standard -- <list>" lists it.
# Needs bash, grep, sed, awk, sort, find, coreutils.
set -u; cd "$(dirname "$0")/.."
TESTS=${TESTS_DIR:-tests}
fail=0; err(){ echo "FAIL: $*"; fail=1; }
fm(){ [ -f STATE.md ] || return 0
  awk -v k="$1" 'NR==1{if($0!="---")exit; next} /^---[ \t]*$/{exit}
    index($0,k":")==1{sub(/^[^:]*:[ \t]*/,""); sub(/[ \t]+#.*$/,""); sub(/[ \t]+$/,""); print; exit}' STATE.md |
  sed -E "s/^[\"']//; s/[\"']\$//; s/^(null|~)\$//"; }
ENGINE=$(fm engine); SP=$(fm spec_path); SP=${SP%/}; TRACK=$(fm track)
no_loop_check(){ [ "$TRACK" = learning ] || return 1
  echo "info: track is learning, so no (loop) check (CHARTER \"Learning projects\")"; }
if [ "$ENGINE" = aidlc ] || [ -n "$SP" ]; then MODE=aidlc; else MODE=sdd; fi
SPEC_MD="requirements-analysis/requirements user-stories/stories user-stories/personas domain-design/components
  domain-design/decisions units-generation/unit-of-work units-generation/unit-of-work-dependency
  units-generation/unit-of-work-story-map contract-design/contract-summary"
case "${1:-}" in
  "") ;;
  --spec-files)
    if [ "$MODE" = sdd ]; then echo inception; echo construction/tasks.md; exit 0; fi
    [ -n "$SP" ] || { echo "trace-check: spec_path is empty in STATE.md" >&2; exit 1; }
    echo inception/brief.md; echo inception/changes.md
    for f in $SPEC_MD; do echo "$SP/inception/$f.md"; done
    exit 0;;
  *) echo "usage: scripts/trace-check.sh [--spec-files]" >&2; exit 2;;
esac

# test_names: one test name per line, from the test definitions under $TESTS (see the header).
test_names(){ [ -e "$TESTS" ] || return 0
  find "$TESTS" -type f \( -name '*.py' -o -name '*.[jt]s' -o -name '*.[jt]sx' -o -name '*.[cm][jt]s' \) \
    -not -path '*/node_modules/*' -exec awk -v sq="'" '
  function title(r,  q, i) { sub(/^[ \t]*/, "", r); q = substr(r, 1, 1)
    if (q != "\"" && q != sq && q != "`") return ""
    r = substr(r, 2); i = index(r, q); return i ? substr(r, 1, i - 1) : r }
  FNR == 1 { py = (FILENAME ~ /\.py$/); nl = 0 }
  py { if (match($0, /^[ \t]*(async[ \t]+)?def[ \t]+test_[A-Za-z0-9_]*/)) {
         s = substr($0, RSTART, RLENGTH); sub(/.*def[ \t]+/, "", s); print s }; next }
  nl { if ($0 ~ /^[ \t]*$/) next; nl = 0; t = title($0); if (t != "") print t; next }
  match($0, /^[ \t]*(await[ \t]+)?(it|test)(\.(only|concurrent))?[ \t]*\(/) {
    r = substr($0, RSTART + RLENGTH); if (r ~ /^[ \t]*$/) { nl = 1; next }
    t = title(r); if (t != "") print t }' {} + 2>/dev/null; }

check_sdd(){
REQ=inception/requirements.md; TASKS=construction/tasks.md
ids(){ grep -oE 'R[0-9]+[._][0-9]+' | tr _ . | sort -u; }
live=$(grep -E '^- R[0-9]+\.[0-9]+ ' "$REQ" | ids)
manual=$(grep -E '^- R[0-9]+\.[0-9]+ \[manual\]' "$REQ" | ids)
tested=$(test_names | ids)
# slices: "## S<n> <title> [open|doing|done ...|blocked]" followed by "covers: R1.1, R1.2" (S0 may say "covers: setup")
no_loop_check || grep -qE '^### R[0-9]+ .*\(loop\)' "$REQ" || err "no requirement tagged (loop): charter rule 2"
open_cov=""; done_cov=""
while IFS='|' read -r slice status cov; do
  [ "$cov" = NOCOVERS ] && { err "$slice has no covers: line"; continue; }
  c=$(echo "$cov" | ids)
  [ -z "$c" ] && { echo "$cov" | grep -q 'setup' || err "$slice cites no criterion"; continue; }
  for id in $c; do echo "$live" | grep -qx "$id" || err "$slice cites $id, which is not a live criterion"; done
  case "$status" in done*) done_cov+=$'\n'"$c";; *) open_cov+=$'\n'"$c";; esac
done < <(awk '/^## S[0-9]+/{if(s!=""&&!c)print s"|"st"|NOCOVERS"; s=$2; c=0; st=$0; sub(/.*\[/,"",st); sub(/\].*/,"",st)}
  /^covers:/{if(s!=""){print s"|"st"|"$0; c=1}} END{if(s!=""&&!c)print s"|"st"|NOCOVERS"}' "$TASKS")
for id in $tested; do echo "$live" | grep -qx "$id" || err "tests reference $id, which is not a live criterion"; done
for id in $live; do
  echo "$manual" | grep -qx "$id" && continue
  echo "$tested" | grep -qx "$id" && continue
  echo "$open_cov" | grep -qx "$id" && continue
  echo "$done_cov" | grep -qx "$id" && err "$id is in a done slice but has no test" || err "$id has no test and no open slice"
done
n_live=$(echo "$live" | grep -c R); n_test=$(echo "$tested" | grep -c R)
echo "criteria: $n_live live, $n_test tested, $(echo "$manual" | grep -c R) manual"
}

ids_ac(){ grep -oE '(^|[^A-Za-z])AC[0-9]+[._][0-9]+[._][0-9]+' | sed -E 's/^[^A]*//' | tr _ . | sort -u; }
ids_fr(){ grep -oE '(^|[^A-Za-z])FR[0-9]+([._][0-9]+)?' | sed -E 's/^[^F]*//' | tr _ . | sort -u; }
ids_nfr(){ grep -oE '(^|[^A-Za-z])NFR[0-9]+' | sed -E 's/^[^N]*//' | sort -u; }
unstruck(){ sed -E 's/~~[^~]*~~//g' "$@"; }
has(){ printf '%s\n' "$1" | grep -qxF "$2"; }
units_of(){ [ -f "$MAP" ] || return 0; local k=${1//./\\.}
  grep -E "^[[:space:]]*\|[[:space:]]*(\*\*)?$k([^.0-9]|\$)" "$MAP" |
  grep -oE '(^|[^a-z0-9-])u[0-9]+-[a-z0-9-]+' | sed -E 's/^[^u]*//' | sort -u; }

check_aidlc(){
[ -n "$SP" ] || { err "spec_path is empty in STATE.md: set it to the AI-DLC intent folder"; return; }
REQ=$SP/inception/requirements-analysis/requirements.md; STO=$SP/inception/user-stories/stories.md
MAP=$SP/inception/units-generation/unit-of-work-story-map.md
[ -f "$REQ" ] || { err "no $REQ"; return; }
fr_all=$(unstruck "$REQ" | ids_fr); nfr_all=$(unstruck "$REQ" | ids_nfr)
no_loop_check || unstruck "$REQ" | grep -E '(^|[^A-Za-z])FR[0-9]+' | grep -qF '(loop)' ||
  err "no functional requirement tagged (loop) in requirements.md: charter rule 2"
if [ -f "$STO" ]; then
  kind=AC; ac_all=$(unstruck "$STO" | ids_ac); crit=$ac_all
  manual=$(unstruck "$STO" | grep -F '[manual]' | ids_ac)
else
  kind=FR; ac_all=""; manual=$(unstruck "$REQ" | grep -F '[manual]' | ids_fr)
  crit=$(for id in $fr_all; do case $id in *.*) echo "$id";; *) echo "$fr_all" | grep -q "^$id\." || echo "$id";; esac; done)
fi
[ -n "$crit" ] || err "no $kind IDs found (stories.md or requirements.md)"
tx=$(test_names)
t_ac=$(printf '%s\n' "$tx" | ids_ac); t_fr=$(printf '%s\n' "$tx" | ids_fr); t_nfr=$(printf '%s\n' "$tx" | ids_nfr)
for id in $t_ac; do has "$ac_all" "$id" || err "tests name $id, which is not a live criterion in stories.md"; done
for id in $t_fr; do has "$fr_all" "$id" || err "tests name $id, which is not in requirements.md"; done
for id in $t_nfr; do has "$nfr_all" "$id" || err "tests name $id, which is not in requirements.md"; done
[ $kind = AC ] && tested=$t_ac || tested=$t_fr
n_crit=0; n_test=0; n_man=0; n_open=0
for id in $crit; do
  n_crit=$((n_crit+1))
  has "$manual" "$id" && { n_man=$((n_man+1)); continue; }
  has "$tested" "$id" && { n_test=$((n_test+1)); continue; }
  if [ -f "$SP/construction/code-generation/code-summary.md" ]; then err "$id has no test, and code generation is done"; continue; fi
  if [ $kind = AC ]; then key=US${id#AC}; key=${key%.*}; else key=$id; fi
  units=$(units_of "$key"); [ -z "$units" ] && [ $kind = FR ] && units=$(units_of "${key%%.*}")
  [ -n "$units" ] || { err "$id has no test, and no unit in the story map covers $key"; continue; }
  built=1; for u in $units; do [ -f "$SP/construction/$u/code-generation/code-summary.md" ] || built=0; done
  [ $built = 1 ] && err "$id has no test, and its unit $(echo $units) is built" || n_open=$((n_open+1))
done
echo "criteria: $n_crit $kind, $n_test tested, $n_man manual, $n_open in units not built yet"
}

# AIDLC_SESSION_OVERRIDE_SOURCE=payload keeps the call read-only: without it, the first call in a Claude
# session writes a chat binding under aidlc/.aidlc-sessions/. Cache path 0: no bun cache in ~/.bun.
sensor(){ AIDLC_SESSION_OVERRIDE_SOURCE=payload BUN_RUNTIME_TRANSPILER_CACHE_PATH=${BUN_RUNTIME_TRANSPILER_CACHE_PATH:-0} \
  aidlc engine sensor-traceability "$@" </dev/null 2>&1; }
verdict(){ case "$1" in
  *'"pass":true'*|*'"pass": true'*) echo pass;;
  *'"pass":false'*|*'"pass": false'*) echo "fail: $(printf '%s' "$1" | tr '\n' ' ' | head -c 300)";;
  *) echo "no result: $(printf '%s' "$1" | head -1 | head -c 200)";; esac; }
aidlc_sensor(){
[ "${AIDLC_SENSOR:-1}" != 0 ] || { echo "info: aidlc sensor skipped (AIDLC_SENSOR=0)"; return; }
command -v aidlc >/dev/null 2>&1 || { echo "info: aidlc sensor skipped (aidlc not on PATH)"; return; }
[ -f .claude/tools/data/harness.json ] || { echo "info: aidlc sensor skipped (AI-DLC not configured here)"; return; }
local t st cg=0
for t in $(find "$SP" -name traceability.json -not -path '*/.aidlc-*' 2>/dev/null | sort); do
  st=$(basename "$(dirname "$t")"); [ "$st" = code-generation ] && cg=1
  echo "info: aidlc sensor $st ${t#"$SP"/}: $(verdict "$(sensor --stage "$st" --output-path "$t")")"
done
[ $cg = 1 ] && [ "${n_open:-1}" = 0 ] && echo "info: aidlc sensor build-and-test: $(verdict "$(sensor --stage build-and-test)")"
echo "info: aidlc sensor results are advisory; the verdict below does not depend on them"
}

if [ "$MODE" = aidlc ]; then check_aidlc; [ -n "$SP" ] && [ -d "$SP" ] && aidlc_sensor; else check_sdd; fi
[ $fail -eq 0 ] && echo "trace-check: PASS" || { echo "trace-check: FAIL"; exit 1; }

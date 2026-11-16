#!/usr/bin/env bash
# Watch every open factory assignment in ONE Monitor: runs one pr-watch.sh per assignment and
# prefixes each of its lines with the assignment's label, and (with --tick) prints a board tick.
# One Monitor instead of one per pull request plus a board-tick Monitor means one expiry notice
# per 30-minute window for the whole team, and that expiry doubles as a board tick.
#
# Usage: team-watch.sh <repo-clone-dir> [--reviewer <login>] [--rerequest] [--interval <seconds>]
#                      [--tick <minutes>] [--fresh] "<label>|<title prefix>|<assigned_at>" ...
#   <label>         how lines are tagged, e.g. "Ada a1-3". Letters, digits, spaces, '.', '-', '(' and ')'.
#   <title prefix>  as for pr-watch.sh, e.g. "task 30, 31".
#   <assigned_at>   the assignment's assigned_at from the registry (pr-watch.sh --since).
#   --reviewer, --rerequest, --interval   passed to every pr-watch.sh.
#   --tick          also print "board-tick" every <minutes> (1-60) while any assignment is watched;
#                   pass it only when the run has a factory board. Default: no ticks.
#   --fresh         print every assignment's current state on start. Without it, the last state each
#                   assignment printed is kept in <clone>/.git/factory-team-watch/ and a restart (expiry
#                   re-arm, an added assignment, the tick turned on or off) prints only real changes.
#                   Pass it after a session restart, when the manager no longer knows the state.
#
# Lines:
#   <time> [<label>] <any pr-watch.sh line>   -- see pr-watch.sh; "done: PR #<n> ..." ends that label
#   <time> board-tick                          -- read the factory board mailbox now
#   <time> team-watch-done                     -- every pr-watch.sh exited; exit 0
# Restart it (TaskStop, then a new Monitor) when an assignment is added; one that ends drops out
# by itself. Works with macOS bash 3.2.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
dir=${1:?repo clone directory}
shift
pass=()
tick=0
fresh=0
specs=()
while [ $# -gt 0 ]; do
  case "$1" in
    --reviewer|--interval) pass+=("$1" "${2:?$1 needs a value}"); shift 2 ;;
    --rerequest) pass+=("$1"); shift ;;
    --tick) tick=${2:?--tick needs minutes}; shift 2 ;;
    --fresh) fresh=1; shift ;;
    --*) echo "unknown argument: $1"; exit 2 ;;
    *) specs+=("$1"); shift ;;
  esac
done

for ((i = 0; i < ${#pass[@]}; i++)); do
  if [ "${pass[$i]}" = --interval ]; then
    case "${pass[$((i + 1))]}" in ''|*[!0-9]*) echo "--interval must be whole seconds"; exit 2 ;; esac
  fi
done
[ "${#specs[@]}" -gt 0 ] || { echo "give at least one \"<label>|<title prefix>|<assigned_at>\""; exit 2; }
case "$tick" in ''|*[!0-9]*) echo "--tick must be whole minutes"; exit 2 ;; esac
if [ "$tick" -gt 60 ]; then echo "--tick must be 0-60"; exit 2; fi

gitdir=$(cd "$dir" 2>/dev/null && git rev-parse --absolute-git-dir 2>/dev/null) || { echo "$dir is not a git clone"; exit 2; }
statedir="$gitdir/factory-team-watch"
mkdir -p "$statedir" || { echo "cannot create $statedir"; exit 2; }

pids=()
cleanup() {
  for p in "${pids[@]:-}" ${tick_pid:-}; do
    [ -n "$p" ] || continue
    pkill -P "$p" 2>/dev/null
    kill "$p" 2>/dev/null
  done
}
trap cleanup EXIT
trap 'exit 143' TERM INT

for spec in "${specs[@]}"; do
  label=${spec%%|*}
  rest=${spec#*|}
  prefix=${rest%%|*}
  since=${rest#*|}
  if [ "$label" = "$spec" ] || [ "$prefix" = "$rest" ] || [ -z "$since" ]; then
    echo "bad assignment \"$spec\": use \"<label>|<title prefix>|<assigned_at>\""; exit 2
  fi
  case "$label" in
    ''|*[!A-Za-z0-9\ .\(\)-]*) echo "label may contain only letters, digits, spaces, '.', '-', '(' and ')'"; exit 2 ;;
  esac
  # One state file per assignment (label, prefix and time), so a new assignment starts clean.
  sf="$statedir/$(printf '%s|%s|%s' "$label" "$prefix" "$since" | cksum | awk '{print $1}')"
  [ "$fresh" = 1 ] && rm -f "$sf"
  # pr-watch.sh validates the prefix and --since itself and exits 2 with a message.
  (
    "$here/pr-watch.sh" "$dir" "$prefix" --since "$since" --state "$sf" --parent $$ ${pass[@]+"${pass[@]}"} 2>&1 \
      | while IFS= read -r line; do
          t=${line%% *}
          printf '%s [%s] %s\n' "$t" "$label" "${line#* }"
        done
  ) &
  pids+=($!)
done

tick_pid=""
if [ "$tick" -gt 0 ]; then
  ( while sleep $((tick * 60)); do kill -0 $$ 2>/dev/null || exit 0; echo "$(date -u +%H:%M:%SZ) board-tick"; done ) &
  tick_pid=$!
fi

for p in "${pids[@]}"; do wait "$p"; done
echo "$(date -u +%H:%M:%SZ) team-watch-done"
exit 0

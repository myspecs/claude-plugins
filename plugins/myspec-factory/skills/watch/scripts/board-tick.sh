#!/usr/bin/env bash
# Wake the manager at a fixed interval so it reads the factory board's mailbox.
# Workers write to the board with ArtifactData, which wakes no session, and a bash
# Monitor cannot call ArtifactData itself; each line printed here is the manager's
# cue to read the board (the board skill).
#
# Usage: board-tick.sh [interval-minutes] [ticks]
#   interval-minutes  whole minutes between ticks (default 5, 1-60)
#   ticks             exit after this many ticks (default 6, one Monitor window at 5 minutes);
#                     the Monitor window (30 min at most) may end first: re-arm on either
#
# Lines:
#   <time> board-tick <n>/<ticks>   -- read the board mailbox now
#   <time> board-tick-done          -- the last tick was printed; exit 0
# Stop it (TaskStop) as soon as no worker is running. Works with macOS bash 3.2.
set -uo pipefail

minutes=${1:-5}
ticks=${2:-6}

case "$minutes" in ''|*[!0-9]*) echo "interval-minutes must be a whole number"; exit 2 ;; esac
case "$ticks" in ''|*[!0-9]*) echo "ticks must be a whole number"; exit 2 ;; esac
if [ "$minutes" -lt 1 ] || [ "$minutes" -gt 60 ]; then echo "interval-minutes must be 1-60"; exit 2; fi
if [ "$ticks" -lt 1 ]; then echo "ticks must be at least 1"; exit 2; fi

n=0
while [ "$n" -lt "$ticks" ]; do
  sleep $((minutes * 60))
  n=$((n + 1))
  echo "$(date -u +%H:%M:%SZ) board-tick $n/$ticks"
done
echo "$(date -u +%H:%M:%SZ) board-tick-done"
exit 0

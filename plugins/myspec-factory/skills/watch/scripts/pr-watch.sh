#!/usr/bin/env bash
# Watch one factory pull request: the worker's new branch, the PR, its checks
# and review state. Prints one line when the state changes, nothing otherwise.
# Exits when the PR is merged or closed.
#
# Usage: pr-watch.sh <repo-clone-dir> "<title prefix>" [--since <ISO-8601 time>] [--interval <seconds>]
#   <title prefix>  how the PR title starts, e.g. "task 38", "task 30, 31", "lane 2".
#                   Letters, digits, spaces and commas only. A PR matches when its title
#                   starts with the prefix and the next character is not a digit, so
#                   "task 3" never matches "task 30".
#   --since         ignore PRs created before this time. Pass the session's `started_at`
#                   from the registry so an older PR with the same title (another bundle,
#                   or the PR of a redispatched worker) is never picked up.
#
# Lines:
#   <time> branches=[<branches new since this watch started>] PR #<n> state=<OPEN|MERGED|CLOSED> draft=<bool> head=<sha> review=<decision|NONE> failing=[<checks>] pending=<n>
#   <time> github-unreachable (<what failed>)   -- a gh/git call failed; the state is UNKNOWN, not empty
#   <time> done: PR #<n> state=<MERGED|CLOSED>  -- terminal; exits 0
# Works with macOS bash 3.2.
set -uo pipefail
export GIT_TERMINAL_PROMPT=0

dir=${1:?repo clone directory}
prefix=${2:?title prefix, e.g. "task 38"}
shift 2
since=""
interval=90
while [ $# -gt 0 ]; do
  case "$1" in
    --since) since=${2:?--since needs a time}; shift 2 ;;
    --interval) interval=${2:?--interval needs seconds}; shift 2 ;;
    *) echo "unknown argument: $1"; exit 2 ;;
  esac
done

case "$prefix" in
  *[!A-Za-z0-9\ ,]*) echo "title prefix may contain only letters, digits, spaces and commas"; exit 2 ;;
esac

cd "$dir" || { echo "cannot cd to $dir"; exit 2; }

list_branches() {
  git ls-remote --heads origin 'claude/*' 'factory/*' 2>/dev/null
}

# Branches that existed when the watch started are not shown as new. Retry the
# snapshot: an empty baseline would report every existing branch as the worker's.
baseline=""
for attempt in 1 2 3 4 5; do
  if baseline=$(list_branches); then break; fi
  echo "$(date -u +%H:%M:%SZ) github-unreachable (git ls-remote at start, attempt $attempt)"
  [ "$attempt" = 5 ] && { echo "cannot read branches; not starting"; exit 2; }
  sleep 10
done
baseline_names=" $(printf '%s\n' "$baseline" | awk '{print $2}' | sed 's#refs/heads/##' | tr '\n' ' ') "

# The PR: title starts with the prefix (next character not a digit), created at or
# after --since, open PRs first, then the newest.
jq_pr='[.[] | select(.title | test("^'"$prefix"'([^0-9]|$)"; "i")) | select("'"$since"'" == "" or .createdAt >= "'"$since"'")]
  | sort_by([(if .state == "OPEN" then 1 else 0 end), .createdAt]) | reverse | .[0] // empty
  | "PR #\(.number) state=\(.state) draft=\(.isDraft) head=\(.headRefOid[0:8]) review=\(if (.reviewDecision // "") == "" then "NONE" else .reviewDecision end) failing=[\([.statusCheckRollup[]? | select((.conclusion // .state) as $c | ["FAILURE","TIMED_OUT","ERROR","STARTUP_FAILURE","ACTION_REQUIRED"] | index($c)) | (.name // .context)] | join(","))] pending=\([.statusCheckRollup[]? | select(((.status // "COMPLETED") != "COMPLETED") or ((.state // "") as $s | ["PENDING","EXPECTED","QUEUED","IN_PROGRESS"] | index($s)))] | length)"'

snap() {
  local out sha ref name new="" pr
  if ! out=$(list_branches); then
    echo "github-unreachable (git ls-remote)"
    return
  fi
  while read -r sha ref; do
    [ -z "${ref:-}" ] && continue
    name=${ref#refs/heads/}
    case "$baseline_names" in *" $name "*) continue ;; esac
    new="$new$name@$(printf '%s' "$sha" | cut -c1-8) "
  done <<EOF
$out
EOF
  if ! pr=$(gh pr list --state all --limit 30 --search "$prefix in:title" \
      --json number,title,state,isDraft,createdAt,headRefOid,reviewDecision,statusCheckRollup --jq "$jq_pr" 2>/dev/null); then
    echo "github-unreachable (gh pr list)"
    return
  fi
  echo "branches=[${new% }] ${pr:-no PR yet}"
}

prev=""
while true; do
  cur=$(snap)
  if [ "$cur" != "$prev" ]; then
    echo "$(date -u +%H:%M:%SZ) $cur"
    prev="$cur"
  fi
  case "$cur" in
    *" state=MERGED "*|*" state=CLOSED "*)
      echo "$(date -u +%H:%M:%SZ) done: $(printf '%s' "$cur" | grep -oE 'PR #[0-9]+ state=(MERGED|CLOSED)')"
      exit 0 ;;
  esac
  sleep "$interval"
done

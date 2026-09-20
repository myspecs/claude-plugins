#!/usr/bin/env bash
# Watch one factory pull request: the worker's new branch, the PR, its checks
# and review state. Prints one line when the state changes, nothing otherwise.
# Exits when the PR is merged or closed.
#
# Usage: pr-watch.sh <repo-clone-dir> "<title prefix>" [--since <ISO-8601 time>] [--interval <seconds>]
#                    [--reviewer <login>] [--rerequest]
#   <title prefix>  how the PR title starts, e.g. "task 38", "task 30, 31", "lane 2".
#                   Letters, digits, spaces and commas only. A PR matches when its title
#                   starts with the prefix and the next character is not a digit, so
#                   "task 3" never matches "task 30".
#   --since         ignore PRs created before this time. Pass the session's `started_at`
#                   from the registry so an older PR with the same title (another bundle,
#                   or the PR of a redispatched worker) is never picked up. Also selects the
#                   branches shown: every origin claude/* or factory/* branch whose tip commit
#                   is at or after this time (read with `git fetch` + `git for-each-ref`), so a
#                   watch re-armed after the worker pushed still shows the worker's branch.
#                   Without --since, branches are those that appeared after the watch started.
#   --reviewer      the reviewer's GitHub login (the registry's `policy.reviewer`).
#                   approved_head then counts that login's reviews only; default: any reviewer.
#   --rerequest     needs --reviewer. When the reviewer has reviewed an older head of an open,
#                   non-draft PR and has no pending review request, run
#                   `gh pr edit <n> --add-reviewer <reviewer>` once for the current head.
#
# Lines:
#   <time> branches=[<branch@sha8 ...>] PR #<n> state=<OPEN|MERGED|CLOSED> draft=<bool> head=<sha> review=<decision|NONE> approved_head=<yes|no|none> failing=[<checks>] pending=<n>
#            approved_head: yes = the latest APPROVED review is on the current head; no = that
#            approval is on an older commit (the head changed after it); none = no approval.
#   <time> re-requested review from <reviewer> on <head8>   -- only with --rerequest
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
reviewer=""
rerequest=0
while [ $# -gt 0 ]; do
  case "$1" in
    --since) since=${2:?--since needs a time}; shift 2 ;;
    --interval) interval=${2:?--interval needs seconds}; shift 2 ;;
    --reviewer) reviewer=${2:?--reviewer needs a login}; shift 2 ;;
    --rerequest) rerequest=1; shift ;;
    *) echo "unknown argument: $1"; exit 2 ;;
  esac
done

case "$prefix" in
  *[!A-Za-z0-9\ ,]*) echo "title prefix may contain only letters, digits, spaces and commas"; exit 2 ;;
esac
case "$reviewer" in
  *[!A-Za-z0-9_\[\]-]*) echo "reviewer login may contain only letters, digits, '-', '_' and '[]'"; exit 2 ;;
esac
if [ "$rerequest" = 1 ] && [ -z "$reviewer" ]; then
  echo "--rerequest needs --reviewer"; exit 2
fi

cd "$dir" || { echo "cannot cd to $dir"; exit 2; }

# --since as Unix seconds (for branch tips) and as UTC "...Z" (for PR createdAt, which
# GitHub reports in that form, so the jq string comparison below is exact).
since_epoch=""
if [ -n "$since" ]; then
  s=$(printf '%s' "$since" | sed -E 's/\.[0-9]+//; s/([+-][0-9][0-9]):([0-9][0-9])$/\1\2/')
  since_epoch=$(date -u -d "$since" +%s 2>/dev/null \
    || date -j -u -f '%Y-%m-%dT%H:%M:%SZ' "$s" +%s 2>/dev/null \
    || date -j -u -f '%Y-%m-%dT%H:%M:%S%z' "$s" +%s 2>/dev/null) \
    || { echo "cannot parse --since $since (use ISO-8601, e.g. 2026-09-19T08:43:27Z)"; exit 2; }
  since=$(date -u -d "@$since_epoch" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -r "$since_epoch" +%Y-%m-%dT%H:%M:%SZ)
fi

list_branches() {
  git ls-remote --heads origin 'claude/*' 'factory/*' 2>/dev/null
}

# Worker branches whose tip commit is at or after --since, as "name@sha8 ...".
branches_since() {
  git fetch --prune -q origin '+refs/heads/claude/*:refs/remotes/origin/claude/*' \
    '+refs/heads/factory/*:refs/remotes/origin/factory/*' 2>/dev/null || return 1
  git for-each-ref --format='%(refname:short) %(committerdate:unix) %(objectname)' \
      refs/remotes/origin/claude refs/remotes/origin/factory 2>/dev/null \
    | awk -v since="$since_epoch" '$2 >= since { sub(/^origin\//, "", $1); printf "%s@%s ", $1, substr($3, 1, 8) }'
}

# Without --since: branches that existed when the watch started are not shown as new.
# Retry the snapshot: an empty baseline would report every existing branch as the worker's.
baseline_names=""
if [ -z "$since" ]; then
  baseline=""
  for attempt in 1 2 3 4 5; do
    if baseline=$(list_branches); then break; fi
    echo "$(date -u +%H:%M:%SZ) github-unreachable (git ls-remote at start, attempt $attempt)"
    [ "$attempt" = 5 ] && { echo "cannot read branches; not starting"; exit 2; }
    sleep 10
  done
  baseline_names=" $(printf '%s\n' "$baseline" | awk '{print $2}' | sed 's#refs/heads/##' | tr '\n' ' ') "
fi

# The PR: title starts with the prefix (next character not a digit), created at or
# after --since, open PRs first, then the newest. Fields are separated by \u001f
# (not a tab: bash would merge empty tab-separated fields).
jq_pr='[.[] | select(.title | test("^'"$prefix"'([^0-9]|$)"; "i")) | select("'"$since"'" == "" or .createdAt >= "'"$since"'")]
  | sort_by([(if .state == "OPEN" then 1 else 0 end), .createdAt]) | reverse | .[0] // empty
  | [(.number | tostring), .headRefOid, .state, (.isDraft | tostring),
     (if (.reviewDecision // "") == "" then "NONE" else .reviewDecision end),
     ([.statusCheckRollup[]? | select((.conclusion // .state) as $c | ["FAILURE","TIMED_OUT","ERROR","STARTUP_FAILURE","ACTION_REQUIRED"] | index($c)) | (.name // .context)] | join(",")),
     ([.statusCheckRollup[]? | select(((.status // "COMPLETED") != "COMPLETED") or ((.state // "") as $s | ["PENDING","EXPECTED","QUEUED","IN_PROGRESS"] | index($s)))] | length | tostring)]
  | join("\u001f")'

repo=""          # owner/name, read once
pr_num="" pr_head="" pr_state="" pr_draft=""
last_review_commit=""   # commit of --reviewer's latest submitted review
cur=""

# Sets $cur (the status line) and the pr_* fields. Runs in the main shell, not $(...),
# so the fields survive for the re-request step.
snap() {
  local new="" pr sha ref name reviews approved f_review f_fail f_pend
  pr_num="" pr_head="" pr_state="" pr_draft="" last_review_commit=""
  if [ -n "$since" ]; then
    if ! new=$(branches_since); then
      cur="github-unreachable (git fetch)"
      return
    fi
  else
    local out
    if ! out=$(list_branches); then
      cur="github-unreachable (git ls-remote)"
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
  fi
  if ! pr=$(gh pr list --state all --limit 30 --search "$prefix in:title" \
      --json number,title,state,isDraft,createdAt,headRefOid,reviewDecision,statusCheckRollup --jq "$jq_pr" 2>/dev/null); then
    cur="github-unreachable (gh pr list)"
    return
  fi
  if [ -z "$pr" ]; then
    cur="branches=[${new% }] no PR yet"
    return
  fi
  IFS=$'\037' read -r pr_num pr_head pr_state pr_draft f_review f_fail f_pend <<EOF
$pr
EOF
  if [ -z "$repo" ] && ! repo=$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null); then
    repo=""
    cur="github-unreachable (gh repo view)"
    return
  fi
  # One line per submitted review, oldest first: "<login> <STATE> <commit>".
  if ! reviews=$(gh api --paginate "repos/$repo/pulls/$pr_num/reviews?per_page=100" \
      --jq '.[] | "\(.user.login) \(.state) \(.commit_id)"' 2>/dev/null); then
    cur="github-unreachable (gh api reviews)"
    return
  fi
  approved=$(printf '%s\n' "$reviews" | awk -v who="$reviewer" -v head="$pr_head" '
    NF == 3 && (who == "" || tolower($1) == tolower(who)) && $2 == "APPROVED" { last = $3 }
    END { print (last == "" ? "none" : (last == head ? "yes" : "no")) }')
  if [ -n "$reviewer" ]; then
    last_review_commit=$(printf '%s\n' "$reviews" | awk -v who="$reviewer" '
      NF == 3 && tolower($1) == tolower(who) && $2 != "PENDING" { c = $3 } END { print c }')
  fi
  cur="branches=[${new% }] PR #$pr_num state=$pr_state draft=$pr_draft head=$(printf '%s' "$pr_head" | cut -c1-8) review=$f_review approved_head=$approved failing=[$f_fail] pending=$f_pend"
}

# --rerequest: once per head, when the reviewer reviewed an older head and has no
# pending request. Prints a line only when something happened or failed.
rerequested_head=""
rr_msg=""
rerequest_review() {
  local requested msg=""
  [ "$rerequest" = 1 ] || return 0
  [ "$pr_state" = "OPEN" ] && [ "$pr_draft" = "false" ] || return 0
  [ -n "$pr_head" ] && [ -n "$last_review_commit" ] || return 0
  [ "$last_review_commit" != "$pr_head" ] && [ "$rerequested_head" != "$pr_head" ] || return 0
  if ! requested=$(gh pr view "$pr_num" --json reviewRequests \
      --jq '[.reviewRequests[] | (.login // .slug // .name // "")] | join(" ")' 2>/dev/null); then
    msg="github-unreachable (gh pr view reviewRequests)"
  else
    case " $(printf '%s' "$requested" | tr 'A-Z' 'a-z') " in
      *" $(printf '%s' "$reviewer" | tr 'A-Z' 'a-z') "*) rerequested_head=$pr_head; return 0 ;;
    esac
    if gh pr edit "$pr_num" --add-reviewer "$reviewer" >/dev/null 2>&1; then
      rerequested_head=$pr_head
      msg="re-requested review from $reviewer on $(printf '%s' "$pr_head" | cut -c1-8)"
    else
      msg="github-unreachable (gh pr edit --add-reviewer $reviewer)"
    fi
  fi
  # A failure is retried on the next poll but printed only once in a row.
  if [ "$msg" != "$rr_msg" ]; then
    echo "$(date -u +%H:%M:%SZ) $msg"
  fi
  case "$msg" in re-requested*) rr_msg="" ;; *) rr_msg=$msg ;; esac
}

prev=""
while true; do
  snap
  if [ "$cur" != "$prev" ]; then
    echo "$(date -u +%H:%M:%SZ) $cur"
    prev="$cur"
  fi
  case "$cur" in
    *" state=MERGED "*|*" state=CLOSED "*)
      echo "$(date -u +%H:%M:%SZ) done: $(printf '%s' "$cur" | grep -oE 'PR #[0-9]+ state=(MERGED|CLOSED)')"
      exit 0 ;;
    github-unreachable*) ;;
    *) rerequest_review ;;
  esac
  sleep "$interval"
done

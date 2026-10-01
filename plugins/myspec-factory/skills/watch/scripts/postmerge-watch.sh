#!/usr/bin/env bash
# Watch the default-branch workflow runs triggered by one merge commit.
# Prints one line when the runs change, and exits when every run is finished.
#
# Usage: postmerge-watch.sh <repo-clone-dir> <merge-sha> [base-branch] [interval-seconds]
#
# Lines:
#   <time> <workflow>=<queued|in_progress|success|failure|...> ...
#   <time> github-unreachable (gh run list)   -- the state is UNKNOWN, not empty; keeps polling
#   <time> no runs yet for <sha>               -- GitHub listed no run for this commit (yet)
#   <time> post-merge-complete: <all runs>     -- the same finished set was seen on two polls in a row;
#                                                 exit 0 when every run succeeded or was skipped, 1 otherwise
#   <time> post-merge-watch-timeout: <last>    -- gave up after 60 polls; exit 3. A commit that triggers no
#                                                 push workflow ends here after "no runs yet".
# Runs counted: `push` and `workflow_run` runs on <base> whose head is the merge commit. Ignored:
# Dependabot and other `dynamic` runs, `schedule` and `workflow_dispatch` runs that happen to start
# on the same commit, and runs for tags pushed later at that commit (their head branch is the tag).
# Limit: a deploy chained with `workflow_run` after another workflow may not carry the merge
# commit as its head; check it with `gh run list` when it matters.
# Works with macOS bash 3.2.
set -uo pipefail

dir=${1:?repo clone directory}
sha=${2:?merge commit sha (short or full)}
base=${3:-main}
interval=${4:-60}

case "$sha" in *[!0-9a-fA-F]*) echo "merge sha must be hex"; exit 2 ;; esac
case "$base" in *[!A-Za-z0-9._/-]*) echo "base branch may contain only letters, digits, '.', '_', '/' and '-'"; exit 2 ;; esac
cd "$dir" || { echo "cannot cd to $dir"; exit 2; }

# `gh run list --commit` needs the full sha and is not cut off by newer runs on the branch.
# Resolve a short sha locally; when that fails, fall back to the newest runs on the branch.
full=""
if [ "${#sha}" = 40 ]; then
  full=$sha
else
  git fetch -q origin "$base" 2>/dev/null
  full=$(git rev-parse --verify -q "$sha^{commit}" 2>/dev/null) || full=""
fi

# One entry per run, "name=state", joined with ";" because workflow names contain
# spaces. GitHub reports status in lowercase and the conclusion only once completed.
jq_runs="[.[] | select(.headSha | startswith(\"$sha\")) | select(.headBranch == \"$base\")
  | select(.event == \"push\" or .event == \"workflow_run\")]
  | sort_by(.name) | map(\"\(.name)=\(if .status == \"completed\" then .conclusion else .status end)\") | join(\";\")"

list_runs() {
  if [ -n "$full" ]; then
    gh run list --commit "$full" --limit 100 --json name,status,conclusion,headSha,headBranch,event --jq "$jq_runs"
  else
    gh run list --branch "$base" --limit 50 --json name,status,conclusion,headSha,headBranch,event --jq "$jq_runs"
  fi
}

prev=""
stable=0
for _ in $(seq 1 60); do
  if ! runs=$(list_runs 2>/dev/null); then
    cur="github-unreachable (gh run list)"
  elif [ -z "$runs" ]; then
    cur="no runs yet for $sha"
  else
    cur=$(printf '%s' "$runs" | sed 's/;/  /g')
  fi
  if [ "$cur" != "$prev" ]; then
    echo "$(date -u +%H:%M:%SZ) $cur"
    prev="$cur"
    stable=0
  else
    stable=$((stable + 1))
  fi
  case "$cur" in
    github-unreachable*|"no runs yet"*) ;;
    *=queued*|*=in_progress*|*=requested*|*=waiting*|*=pending*) ;;
    *)
      # Finished: wait for one more identical poll so a run that registers late is not missed.
      if [ "$stable" -ge 1 ]; then
        echo "$(date -u +%H:%M:%SZ) post-merge-complete: $cur"
        # No `grep -q` here: with pipefail an early exit could SIGPIPE `tr` and flip the result.
        failed=$(printf '%s\n' "$runs" | tr ';' '\n' | grep -vE '=(success|skipped|neutral)$' || true)
        if [ -n "$failed" ]; then
          echo "$(date -u +%H:%M:%SZ) failed: $(printf '%s' "$failed" | tr '\n' ' ')"
          exit 1
        fi
        exit 0
      fi ;;
  esac
  sleep "$interval"
done
echo "$(date -u +%H:%M:%SZ) post-merge-watch-timeout: $prev"
exit 3

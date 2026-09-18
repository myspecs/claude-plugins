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
# Limit: only runs whose head is the merge commit are seen. A deploy chained with `workflow_run`
# after another workflow may not carry that head; check it with `gh run list` when it matters.
# Works with macOS bash 3.2.
set -uo pipefail

dir=${1:?repo clone directory}
sha=${2:?merge commit sha (short or full)}
base=${3:-main}
interval=${4:-60}

case "$sha" in *[!0-9a-fA-F]*) echo "merge sha must be hex"; exit 2 ;; esac
cd "$dir" || { echo "cannot cd to $dir"; exit 2; }

# One entry per run, "name=state", joined with ";" because workflow names contain
# spaces. GitHub reports status in lowercase and the conclusion only once completed.
jq_runs="[.[] | select(.headSha | startswith(\"$sha\"))] | sort_by(.name) | map(\"\(.name)=\(if .status == \"completed\" then .conclusion else .status end)\") | join(\";\")"

prev=""
stable=0
for _ in $(seq 1 60); do
  if ! runs=$(gh run list --branch "$base" --limit 30 --json name,status,conclusion,headSha --jq "$jq_runs" 2>/dev/null); then
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

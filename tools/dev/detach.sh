#!/usr/bin/env bash
# Start a command in the background, detached from the terminal and the ssh session (nohup, own
# session), with its output in LOG and, once it has finished, its exit status in LOG.status:
#
#   tools/dev/detach.sh LOG CMD [ARGS...]
#
# For runs longer than an ssh call should last, e.g. on a cluster node (the command keeps the
# caller's working directory and environment, here the work tree and the project environment):
#   tools/dev/cluster_run.sh gpu01 -- tools/dev/detach.sh /share/home/USER/runs/ab.log \
#       python3 tools/run/guard.py --exclusive --timeout 2700 -- results/portable-vs-native/reproduce.sh run
# Poll with `cat LOG.status` (absent while running). A later cluster_run.sh with the same work tree
# name checks out another commit in that tree: give concurrent work its own HS_CLUSTER_NAME.
set -euo pipefail
[ $# -ge 2 ] || { sed -n '2,13p' "$0" >&2; exit 2; }
log="$1"
shift
mkdir -p "$(dirname "$log")"
rm -f "$log.status"
# shellcheck disable=SC2016
nohup setsid bash -c '"$@" > "$0" 2>&1; echo $? > "$0.status"' "$log" "$@" < /dev/null > /dev/null 2>&1 &
echo "detach: pid $! - output $log, exit status in $log.status when done"

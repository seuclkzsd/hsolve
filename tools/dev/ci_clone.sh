#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 seuclkzsd and the hsolve contributors
# Run tools/dev/ci.sh the way a CI runner does: in a fresh clone of the current commit - no build
# tree, no data/ link, an empty MUMPS cache - so that nothing of the work tree leaks into the result.
#
#   tools/dev/ci_clone.sh [--detach] DIR [STEP...]
#
# DIR (absolute; removed and recreated): DIR/src the clone, DIR/mumps-cache the MUMPS build,
# DIR/ci.log the output, DIR/ci.status the exit status once finished. STEPs are passed to ci.sh
# (default: all). --detach returns at once and leaves the run in the background (nohup, own
# session), e.g. on a cluster node:
#     tools/dev/cluster_run.sh gpu01 -- tools/dev/ci_clone.sh --detach /share/home/USER/ci-run
# The environment variables of ci.sh (CI_CTEST_EXCLUDE, CI_PACKAGE_ARGS, HS_JOBS, ...) pass through.
set -euo pipefail
detach=0
if [ "${1:-}" = "--detach" ]; then
  detach=1
  shift
fi
[ $# -ge 1 ] && [[ "$1" == /* ]] || { sed -n '4,14p' "$0" >&2; exit 2; }
dir="${1%/}"
shift
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
case "$dir" in
  ""|"$HOME"|"$repo"|"$repo"/*|"$(dirname "$repo")") echo "ci_clone: refusing to recreate '$dir'" >&2; exit 2 ;;
esac
if [ "$detach" = 1 ]; then
  mkdir -p "$dir"
  nohup setsid "$0" "$dir" "$@" > "$dir.launch.log" 2>&1 < /dev/null &
  echo "ci_clone: running in the background (pid $!); output $dir/ci.log, exit status $dir/ci.status"
  exit 0
fi
sha="$(cd "$repo" && git rev-parse HEAD)"  # no git -C: CentOS 7 has git 1.8.3
rm -rf "$dir"
mkdir -p "$dir"
git clone -q --no-checkout "$repo" "$dir/src"
(cd "$dir/src" && git checkout -q "$sha")
rc=0
(cd "$dir/src" && HS_MUMPS_CACHE="$dir/mumps-cache" tools/dev/ci.sh "$@") > "$dir/ci.log" 2>&1 || rc=$?
echo "$rc" > "$dir/ci.status"
echo "ci_clone: commit $sha, exit status $rc; output $dir/ci.log"
exit "$rc"

#!/usr/bin/env bash
# Resource tiers of docs/INSTALL.md §5: how this directory's table was made (scripts/resource_tiers.py).
# Run from the repository root inside the project environment; on the cluster through
# tools/dev/cluster_run.sh (docs/DESIGN.md §6), timings in the measurement slot, e.g.
#     tools/dev/cluster_run.sh c003 -- results/resource-tiers/reproduce.sh generate
#     tools/dev/cluster_run.sh c003 -- python3 tools/run/guard.py --exclusive --timeout 2700 -- \
#         results/resource-tiers/reproduce.sh run
#     tools/dev/cluster_run.sh c003 -- python3 tools/run/guard.py --exclusive --timeout 2700 -- \
#         results/resource-tiers/reproduce.sh run-capped
#     tools/dev/cluster_run.sh c003 -- results/resource-tiers/reproduce.sh table pack
#
#   reproduce.sh STAGE...
#     generate    the six cases (yee-pec-box-1e4/1e5/1e6, wg-square-1e4/1e5/1e6) into $TIERS/data
#     run         every case at 16 and 4 threads, RAM cap 32 GiB, 3 repetitions -> $TIERS/tiers-<host>
#     run-capped  the 1e6 cases at 16 and 4 threads with RAM caps of 8 and 4 GiB, once each
#     table       tiers.md / tiers.json and tiers-summary.md (docs/INSTALL.md §5) here
#     pack        that run directory (no eigenvectors, home as $HOME) as raw-tiers-<host>.tar.gz here
#     retable     the table again from the committed raw-tiers-*.tar.gz
# TIERS defaults to $HOME/hsolve-tiers; TIERS_HOST (default: this host) names the measured node;
# HSOLVE (default build/release/hsolve) the executable. Cores of each run (scripts/resource_tiers.py):
# the first 16 / 4 of the measurement slot HS_MEASURE_CORES where the node defines one (cluster
# nodes: 16-31), else the first 16 / 4 physical cores this process may use; HS_TIER_FIRST_CORE=N
# starts from CPU N.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../.." && pwd)"
cd "$root"
TIERS="${TIERS:-$HOME/hsolve-tiers}"
host="${TIERS_HOST:-$(hostname -s)}"
hsolve="${HSOLVE:-build/release/hsolve}"
tiers=(python3 scripts/resource_tiers.py)

for stage in "$@"; do
  case "$stage" in
    generate) "${tiers[@]}" generate --root "$TIERS/data" ;;
    run)
      "${tiers[@]}" run --root "$TIERS/data" --out "$TIERS/tiers-$host" --hsolve "$hsolve" \
          --threads 16,4 --mem-gb 32 --reps 3 ;;
    run-capped)
      "${tiers[@]}" run --root "$TIERS/data" --out "$TIERS/tiers-$host" --hsolve "$hsolve" \
          --cases yee-pec-box-1e6,wg-square-1e6 --threads 16,4 --mem-gb 8,4 --reps 1 ;;
    table) "${tiers[@]}" table "$TIERS/tiers-$host" --md "$here/tiers.md" --json "$here/tiers.json" --summary-md "$here/tiers-summary.md" ;;
    pack) python3 scripts/pack_raw.py "$TIERS/tiers-$host" "$here/raw-tiers-$host.tar.gz" ;;
    retable)
      tmp="$(mktemp -d)"
      trap 'rm -rf "$tmp"' EXIT
      for t in "$here"/raw-tiers-*.tar.gz; do tar -xzf "$t" -C "$tmp"; done
      "${tiers[@]}" table "$tmp"/tiers-* --md "$here/tiers.md" --json "$here/tiers.json" --summary-md "$here/tiers-summary.md" ;;
    *) sed -n '2,23p' "$0" >&2; exit 2 ;;
  esac
done

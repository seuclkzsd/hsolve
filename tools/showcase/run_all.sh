#!/usr/bin/env bash
# The showcase evidence step by step, exactly as run on the cluster (docs/showcase/*.md quote it).
#
#   tools/showcase/run_all.sh STEP [ARGS...]        from the repository root, in the project env
#                                                   (tools/dev/cluster_run.sh HOST -- tools/showcase/run_all.sh STEP)
# Steps:
#   prepare [IDS...]        build/test lane: campaign data root (cases, references, resolved targets)
#   profiles                merged tuned SLEPc profiles -> results/showcase/slepc_tuned_profiles.json
#   probe                   build/test lane: SLEPc's own error for a complex Hermitian interval
#   campaign IDS...         measurement slot, one guard --exclusive call (<= 2700 s): these scenarios
#   campaign-complex IDS... the same with the complex-scalar SLEPc build (complex cases)
#   physics                 build/test lane: PEC cavity and square waveguide against closed forms
#   tables                  results/showcase/scenarios.{json,md} and the generated page sections
#   slot1 | slot2 | slot3 | slot4   the campaign's four slot calls (the scenario groups below)
#   slots-real              slot1, slot2 and slot3 one after the other (the real-scalar SLEPc build)
#   detach STEP [ARGS...]   run a step with nohup setsid; log in $SHOWCASE_HOME/logs/
# Figures need matplotlib, which the project env does not ship: run
#   python3 -m tools.showcase.figures all       with any Python that has numpy + matplotlib.
#
# Placement (docs/DESIGN.md §6): builds, references and physics runs in the build/test lane (8 cores,
# <= 12 GiB); every timed run in the measurement slot (16 cores 16-31, 32 GiB, guard --exclusive).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
SHOWCASE_HOME="${SHOWCASE_HOME:-$HOME/rb-evidence}"
ROOT="$SHOWCASE_HOME/data"
EXTRA_DATA="${HS_SHOWCASE_EXTRA_DATA:-$HOME/p7_p7-membudget/data}"   # the 1e6 cases
REF_COMPLEX="${HS_REF_COMPLEX_ENV:-/tmp/os2026-p28/ref-complex}"     # complex-scalar SLEPc (gpu02)
lane=(python3 tools/run/guard.py --skip-busy-check --timeout 3600 --mem-gb 12 --)
slot=(python3 tools/run/guard.py --exclusive --timeout 2700 --mem-gb 32 --)

SLOT1=(multiplet-cube te-tm-pairs-box sigma-on-eigenvalue sigma-1e-13 lowfreq-null-space zero-cluster)
SLOT2=(waveguide-square waveguide-slab interval-box ss-2cubes-sphere ss-qa8fk ss-tem27623 ss-tem152078)
SLOT3=(pec-box-1e6 waveguide-1e6)
SLOT4=(bloch-1e4 bloch-1e5 bloch-interval)

step="${1:-}"
[ -n "$step" ] || { awk 'NR > 1 && /^#/ { print; next } NR > 1 { exit }' "$0" >&2; exit 2; }
shift
case "$step" in
  prepare)
    "${lane[@]}" python -m tools.showcase.scenarios prepare --root "$ROOT" \
      --source-root data --source-root "$EXTRA_DATA" ${1:+--only "$@"} ;;
  profiles)
    python -m tools.showcase.campaign profiles ;;
  probe)
    read -r lo hi < <(python -c "import json,sys; s=json.load(open(sys.argv[1]))['scenarios']['bloch-interval']['target']; print(s['lower'], s['upper'])" "$ROOT/showcase-scenarios.json")
    "${lane[@]}" env "LD_LIBRARY_PATH=$REF_COMPLEX/lib" "$REF_COMPLEX/bin/python" -m tools.showcase.slepc_probe \
      --case yee-bloch-1e4 --root "$ROOT" --lower "$lo" --upper "$hi" --out results/showcase/raw/slepc-probe.json ;;
  campaign)
    "${slot[@]}" python -m tools.showcase.campaign run --root "$ROOT" --scenario "$@" ;;
  campaign-complex)
    "${slot[@]}" python -m tools.showcase.campaign run --root "$ROOT" --slepc-env "$REF_COMPLEX" \
      --slepc-ld-path "$REF_COMPLEX/lib" --scenario "$@" ;;
  slot1) "$0" campaign "${SLOT1[@]}" ;;
  slot2) "$0" campaign "${SLOT2[@]}" ;;
  slot3) "$0" campaign "${SLOT3[@]}" ;;
  slot4) "$0" campaign-complex "${SLOT4[@]}" ;;
  slots-real)   # slot1-3 back to back (separate slot calls; a failed call does not stop the next)
    rc=0
    for s in slot1 slot2 slot3; do "$0" "$s" || rc=$?; done
    exit "$rc" ;;
  physics)
    "${lane[@]}" python -m tools.showcase.physics run --root "$ROOT" --source-root data ;;
  tables)
    python -m tools.showcase.tables ;;
  detach)
    mkdir -p "$SHOWCASE_HOME/logs"
    log="$SHOWCASE_HOME/logs/$(date +%Y%m%d-%H%M%S)-${1:-step}.log"
    nohup setsid "$0" "$@" > "$log" 2>&1 < /dev/null &
    echo "started pid $! log $log" ;;
  *) echo "run_all.sh: unknown step '$step'" >&2; exit 2 ;;
esac

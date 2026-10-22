#!/usr/bin/env bash
# The showcase evidence step by step (docs/showcase/*.md quote it, section 复现).
#
#   tools/showcase/run_all.sh STEP [ARGS...]        from the repository root, in the project env
#                                                   (on the cluster: tools/dev/cluster_run.sh HOST -- tools/showcase/run_all.sh STEP)
# Steps:
#   data [IDS...]           build/test lane: generate the source cases of these scenarios (all by default)
#                           that data/ lacks (tools/gen presets and recorded command lines; SuiteSparse
#                           matrices are downloaded, which needs internet)
#   prepare [IDS...]        build/test lane: campaign data root (cases, references, resolved targets)
#   tune IDS...             measurement slot, one guard --exclusive call: tools/bench/tune_slepc.py on
#                           these scenarios' cases (16 cores) -> results/showcase/tuning/<scenario>.json;
#                           a scenario whose tuned configuration failed at random in its raw record is
#                           tuned as a randomly failing case (20 confirmation runs per candidate)
#   tune-complex IDS...     the same with the complex-scalar SLEPc build (complex cases)
#   tunes [IDS...]          `tune` once per scenario (default: TUNE_IDS below), then `profiles` and
#                           `tuning-report`
#   profiles                case profiles of the tuning records -> results/showcase/slepc_tuned_showcase.json,
#                           merged with the other profile sources -> results/showcase/slepc_tuned_profiles.json
#   tuning-report           results/showcase/slepc_tuning.json (condensed records, every trial's verdict)
#                           and the tuner's own report results/showcase/slepc_tuning.md
#   probe                   build/test lane: SLEPc's own error for a complex Hermitian interval
#   campaign IDS...         measurement slot, one guard --exclusive call (<= 2700 s): these scenarios
#   campaign-complex IDS... the same with the complex-scalar SLEPc build (complex cases)
#   physics                 build/test lane: PEC cavity and square waveguide against closed forms
#   tables                  results/showcase/scenarios.{json,md} and the generated page sections
#   figures [NAMES...]      docs/images/*.png|svg (all by default) with $HS_FIGURE_PYTHON
#   slot1 | slot2 | slot3 | slot4   the campaign's four slot calls (the scenario groups below)
#   slots-real              slot1, slot2 and slot3 one after the other (the real-scalar SLEPc build)
#   steps STEP...           these steps one after the other (each its own call; a failure does not
#                           stop the next; exit status of the last failure)
#   detach STEP [ARGS...]   run a step with nohup setsid; log in $SHOWCASE_HOME/logs/
# Environment:
#   SHOWCASE_HOME           work area: campaign data root, run directories, logs (default $HOME/rb-evidence)
#   HS_SHOWCASE_EXTRA_DATA  a further source data root searched after data/ (optional; the cluster
#                           campaign read yee-pec-box-1e6 from one, ~/p7_p7-membudget/data)
#   HS_REF_COMPLEX_ENV      prefix of the complex-scalar SLEPc environment, required by tune-complex,
#                           campaign-complex, slot4 and probe (os2026-ref with the complex builds of
#                           petsc/slepc/petsc4py/slepc4py 3.26.0; docs/showcase/困难场景对比.md, 复现)
#   HS_FIGURE_PYTHON        a Python with numpy + matplotlib >= 3.5 for `figures` (the project env has no
#                           matplotlib; the committed figures: matplotlib 3.8.4)
#
# Placement (docs/DESIGN.md §6): builds, data, references and physics runs in the build/test lane
# (8 cores, <= 12 GiB); every timed run in the measurement slot (16 cores 16-31, 32 GiB, guard --exclusive).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
SHOWCASE_HOME="${SHOWCASE_HOME:-$HOME/rb-evidence}"
ROOT="$SHOWCASE_HOME/data"
SOURCES=(--source-root data)
[ -z "${HS_SHOWCASE_EXTRA_DATA:-}" ] || SOURCES+=(--source-root "$HS_SHOWCASE_EXTRA_DATA")
lane=(python3 tools/run/guard.py --skip-busy-check --timeout 3600 --mem-gb 12 --)
slot=(python3 tools/run/guard.py --exclusive --timeout 2700 --mem-gb 32 --)

SLOT1=(multiplet-cube te-tm-pairs-box sigma-on-eigenvalue sigma-1e-13 lowfreq-null-space zero-cluster)
SLOT2=(waveguide-square waveguide-slab interval-box ss-2cubes-sphere ss-qa8fk ss-tem27623 ss-tem152078)
SLOT3=(pec-box-1e6 waveguide-1e6)
SLOT4=(bloch-1e4 bloch-1e5 bloch-interval)
# Scenarios whose case had no tuned profile at 16 cores, tuned by this campaign (the complex one with
# tune-complex).
TUNE_IDS=(multiplet-cube sigma-on-eigenvalue sigma-1e-13 lowfreq-null-space zero-cluster waveguide-slab
          ss-2cubes-sphere ss-tem27623 ss-tem152078)
TUNE_COMPLEX_IDS=(bloch-1e5)

complex_env() {   # the complex-scalar SLEPc environment, or a clear error
  local env="${HS_REF_COMPLEX_ENV:-}"
  if [ -z "$env" ] || [ ! -x "$env/bin/python" ]; then
    echo "run_all.sh: step '$step' needs the complex-scalar SLEPc environment: set HS_REF_COMPLEX_ENV to the" \
         "prefix of a conda env with the complex builds of petsc/slepc/petsc4py/slepc4py 3.26.0" \
         "(docs/showcase/困难场景对比.md, 复现)${env:+; '$env/bin/python' is missing}" >&2
    exit 2
  fi
  REF_COMPLEX="$env"
}

step="${1:-}"
[ -n "$step" ] || { awk 'NR > 1 && /^#/ { print; next } NR > 1 { exit }' "$0" >&2; exit 2; }
shift
case "$step" in
  data)
    "${lane[@]}" python -m tools.showcase.scenarios data --root data ${1:+--only "$@"} ;;
  prepare)
    "${lane[@]}" python -m tools.showcase.scenarios prepare --root "$ROOT" "${SOURCES[@]}" ${1:+--only "$@"} ;;
  profiles)
    python -m tools.showcase.campaign profiles ;;
  tune)
    "${slot[@]}" python -m tools.showcase.campaign tune --root "$ROOT" --scenario "$@" ;;
  tune-complex)
    complex_env
    "${slot[@]}" python -m tools.showcase.campaign tune --root "$ROOT" --slepc-env "$REF_COMPLEX" \
      --slepc-ld-path "$REF_COMPLEX/lib" --scenario "$@" ;;
  tunes)   # one slot call per scenario (a tuning takes 5-30 min)
    rc=0
    [ $# -gt 0 ] || set -- "${TUNE_IDS[@]}"
    for s in "$@"; do "$0" tune "$s" || rc=$?; done
    "$0" profiles
    "$0" tuning-report
    exit "$rc" ;;
  tuning-report)   # condensed records and the tuner's own report of every showcase tuning
    python -m tools.showcase.campaign tuning-summary
    { printf '# SLEPc per-case tuning of the showcase scenarios\n\n'
      printf 'Written by `tools/showcase/run_all.sh tuning-report` (`tools/bench/tune_slepc.py --report`) from the\n'
      printf 'tuning records `results/showcase/tuning/<scenario>.json` (every trial: configuration, solver time,\n'
      printf 'verdict of the independent evaluation; 16 cores of one socket, measurement slot). Condensed in\n'
      printf '`slepc_tuning.json`; the profiles derived from them in `slepc_tuned_showcase.json`.\n\n'
      python tools/bench/tune_slepc.py --report results/showcase/tuning/*.json
    } > results/showcase/slepc_tuning.md ;;
  probe)
    complex_env
    read -r lo hi < <(python -c "import json,sys; s=json.load(open(sys.argv[1]))['scenarios']['bloch-interval']['target']; print(s['lower'], s['upper'])" "$ROOT/showcase-scenarios.json")
    "${lane[@]}" env "LD_LIBRARY_PATH=$REF_COMPLEX/lib" "$REF_COMPLEX/bin/python" -m tools.showcase.slepc_probe \
      --case yee-bloch-1e4 --root "$ROOT" --lower "$lo" --upper "$hi" --out results/showcase/raw/slepc-probe.json ;;
  campaign)
    "${slot[@]}" python -m tools.showcase.campaign run --root "$ROOT" --scenario "$@" ;;
  campaign-complex)
    complex_env
    "${slot[@]}" python -m tools.showcase.campaign run --root "$ROOT" --slepc-env "$REF_COMPLEX" \
      --slepc-ld-path "$REF_COMPLEX/lib" --scenario "$@" ;;
  slot1) "$0" campaign "${SLOT1[@]}" ;;
  slot2) "$0" campaign "${SLOT2[@]}" ;;
  slot3) "$0" campaign "${SLOT3[@]}" ;;
  slot4) "$0" campaign-complex "${SLOT4[@]}" ;;
  slots-real) "$0" steps slot1 slot2 slot3 ;;
  steps)
    rc=0
    for s in "$@"; do echo "[run_all] step $s"; "$0" "$s" || rc=$?; done
    exit "$rc" ;;
  physics)
    "${lane[@]}" python -m tools.showcase.physics run --root "$ROOT" --source-root data ;;
  tables)
    python -m tools.showcase.tables ;;
  figures)
    [ $# -gt 0 ] || set -- all
    "${lane[@]}" "${HS_FIGURE_PYTHON:-python3}" -m tools.showcase.figures "$@" ;;
  detach)
    mkdir -p "$SHOWCASE_HOME/logs"
    log="$SHOWCASE_HOME/logs/$(date +%Y%m%d-%H%M%S)-${1:-step}.log"
    nohup setsid "$0" "$@" > "$log" 2>&1 < /dev/null &
    echo "started pid $! log $log" ;;
  *) echo "run_all.sh: unknown step '$step'" >&2; exit 2 ;;
esac

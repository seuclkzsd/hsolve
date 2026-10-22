#!/usr/bin/env bash
# The continuous-integration pipeline as one script. .github/workflows/ci.yml runs its steps on
# GitHub's ubuntu-latest runners (environment from env/environment.yml via setup-micromamba); the
# same script runs unchanged on a developer machine or a cluster node, e.g.
#     tools/dev/cluster_run.sh gpu01 -- tools/dev/ci.sh
#
#   tools/dev/ci.sh [STEP...]          default: every step, in this order
#     deps         MUMPS 5.8.2 from third_party/mumps with the project's patches
#                  (tools/dev/mumps_cache.sh; installed under $HS_MUMPS_CACHE, default build/deps)
#     build        the release preset (portable x86-64) with -Werror: no compiler warning passes
#     portability  tools/release/check_isa.py: no AVX-class instruction outside the CPUID dispatch
#     ctest        the C++ tests (ctest --preset release); CI_CTEST_EXCLUDE: a regex of tests to skip
#     pytest       the Python tests (tests/py)
#     examples     examples/SHA256SUMS: the committed example files are intact
#     demo         scripts/demo.sh --quick: two examples solved and checked independently by
#                  tools/eval, plus the Python module's API (results in build/ci-demo)
#     package      tools/release/package.sh --skip-build: the relocatable tarball of the build
#                  (glibc <= 2.17 check, solve from a moved copy with an empty environment) in
#                  build/ci-package; CI_PACKAGE_ARGS: further options of tools/release/package.py,
#                  e.g. --allow-missing-legal on a branch without LICENSE / NOTICE
#
# Resources: every step runs under tools/run/guard.py (env/activate.sh sets HS_CORES = the CPUs this
# shell may use unless env/hosts/<host>.sh says otherwise; HS_JOBS = build and ctest parallelism,
# default 4; HS_TEST_MEM_GB = RSS limit of a test step, default 8 GiB).
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"
# shellcheck disable=SC1091
source env/activate.sh
jobs="${HS_JOBS:-4}"
guard=(python3 tools/run/guard.py --skip-busy-check --mem-gb "${HS_TEST_MEM_GB:-8}" --timeout 3600 --)
all=(deps build portability ctest pytest examples demo package)
steps=("$@")
[ ${#steps[@]} -gt 0 ] || steps=("${all[@]}")

step() {
  local name="$1" t0=$SECONDS
  shift
  if [ -n "${GITHUB_ACTIONS:-}" ]; then echo "::group::ci: $name"; else echo "== ci: $name"; fi
  "$@"
  [ -z "${GITHUB_ACTIONS:-}" ] || echo "::endgroup::"
  echo "ci: $name passed in $((SECONDS - t0)) s"
}

for s in "${steps[@]}"; do
  case "$s" in
    deps) step deps "${guard[@]}" tools/dev/mumps_cache.sh ensure ;;
    build) step build env HS_CMAKE_ARGS="-DHSOLVE_WERROR=ON ${HS_CMAKE_ARGS:-}" tools/dev/build.sh release ;;
    portability) step portability python3 tools/release/check_isa.py build/release ;;
    ctest)
      args=(--preset release --no-tests=error -j "$jobs")
      [ -z "${CI_CTEST_EXCLUDE:-}" ] || args+=(-E "$CI_CTEST_EXCLUDE")
      step ctest "${guard[@]}" ctest "${args[@]}" ;;
    pytest) step pytest "${guard[@]}" python3 -m pytest -q tests/py ;;
    examples) step examples bash -c 'cd examples && sha256sum -c --quiet SHA256SUMS' ;;
    demo) step demo "${guard[@]}" scripts/demo.sh --quick --threads 2 --out build/ci-demo ;;
    package)
      read -r -a extra <<< "${CI_PACKAGE_ARGS:-}"
      step package "${guard[@]}" tools/release/package.sh --skip-build --out build/ci-package ${extra[@]+"${extra[@]}"} ;;
    *) echo "ci.sh: unknown step '$s' (${all[*]})" >&2; exit 2 ;;
  esac
done
echo "ci: all steps passed (${steps[*]})"

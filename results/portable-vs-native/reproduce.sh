#!/usr/bin/env bash
# Portable (default) vs -march=native build of hsolve: how this directory's tables were made.
# Run from the repository root inside the project environment; on the cluster through
# tools/dev/cluster_run.sh (docs/DESIGN.md §6: build, eval and table in the build lane, timings in
# the measurement slot), e.g.
#     tools/dev/cluster_run.sh gpu01 -- results/portable-vs-native/reproduce.sh build
#     tools/dev/cluster_run.sh gpu01 -- python3 tools/run/guard.py --exclusive --timeout 2700 -- \
#         results/portable-vs-native/reproduce.sh run
#     tools/dev/cluster_run.sh gpu01 -- results/portable-vs-native/reproduce.sh evaluate table pack
#
#   reproduce.sh STAGE...
#     build   tools/dev/build.sh release (portable) and native; copies both executables to $AB/bin
#             (plus hsolve_avx2: the portable executable with the AVX-512 code paths masked, i.e.
#             as on a CPU with AVX2 but without AVX-512 - HS_KERNELS_NO_AVX512, HS_BLAS_NO_AVX512,
#             OPENBLAS_CORETYPE=Haswell) and records versions and checksums in $AB/binaries.txt
#     run     tools/bench/ab_cases.py run, 5 interleaved repetitions (ABBA order), 16 threads:
#             native vs portable -> $AB/ab-<host>, portable vs avx2 -> $AB/ab-<host>-avx2
#             (inside the measurement slot: guard.py --exclusive)
#     evaluate tools/eval/sweep.py on both run directories (residuals, completeness, verdicts)
#     table   tools/bench/ab_cases.py table -> ab-table.{md,json}, ab-table-avx2.{md,json} here
#     pack    the run directories without eigenvectors, home paths as $HOME, into
#             raw-ab-<host>.tar.gz / raw-ab-<host>-avx2.tar.gz here
#     retable the tables again from the committed raw-*.tar.gz (no solver run needed)
# $AB defaults to $HOME/hsolve-ab/portable-vs-native; HS_DATA_ROOT (default data/) holds the cases;
# AB_HOST (default: this host) names the node whose runs eval / table / pack use.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../.." && pwd)"
cd "$root"
AB="${AB:-$HOME/hsolve-ab/portable-vs-native}"
host="${AB_HOST:-$(hostname -s)}"
cases=(yee-pec-box-1e5 syn-mem27-46 wg-square-1e5 cav2d-rect-pert-1e5 ss-qa8fk-qa8fm syn-near-singular-complex-1e5)
lane=(python3 tools/run/guard.py --skip-busy-check --mem-gb 12 --timeout 3600 --)

table() {  # RUN_DIR... -> ab-table<suffix>.{md,json} with the given base/new labels
  local suffix="$1" base="$2" new="$3"
  shift 3
  python3 tools/bench/ab_cases.py table --base "$base" --new "$new" \
      --md "$here/ab-table$suffix.md" --json "$here/ab-table$suffix.json" "$@"
}

for stage in "$@"; do
  case "$stage" in
    build)
      tools/dev/build.sh release
      tools/dev/build.sh native
      mkdir -p "$AB/bin"
      cp build/release/hsolve "$AB/bin/hsolve_portable"
      cp build/native/hsolve "$AB/bin/hsolve_native"
      cat > "$AB/bin/hsolve_avx2" <<'EOF'
#!/bin/sh
# The portable executable as on an AVX2 CPU without AVX-512: hsolve's kernels and OpenBLAS.
HS_KERNELS_NO_AVX512=1 HS_BLAS_NO_AVX512=1 OPENBLAS_CORETYPE=Haswell exec "$(dirname "$0")/hsolve_portable" "$@"
EOF
      chmod +x "$AB/bin/hsolve_avx2"
      { for b in portable native; do
          echo "== $b"
          "$AB/bin/hsolve_$b" --A unused.npz --version | head -1
          (cd "$AB/bin" && sha256sum "hsolve_$b")
        done
        echo "commit $(git rev-parse HEAD)"; } > "$AB/binaries.txt"
      cat "$AB/binaries.txt" ;;
    run)
      [ "${HS_SLOT_HELD:-}" ] || echo "reproduce.sh: not inside the measurement slot - these times are no measurements" >&2
      python3 tools/bench/ab_cases.py run --bin native="$AB/bin/hsolve_native" --bin portable="$AB/bin/hsolve_portable" \
          --reps 0,1,2,3,4 --threads 16 --run-dir "$AB/ab-$host" "${cases[@]}"
      python3 tools/bench/ab_cases.py run --bin portable="$AB/bin/hsolve_portable" --bin avx2="$AB/bin/hsolve_avx2" \
          --reps 0,1,2,3,4 --threads 16 --run-dir "$AB/ab-$host-avx2" "${cases[@]}" ;;
    evaluate)
      for d in "$AB/ab-$host" "$AB/ab-$host-avx2"; do
        "${lane[@]}" python3 -m tools.eval.sweep "$d" --out "$d/eval.md"
      done ;;
    table)
      table "" native portable "$AB/ab-$host"
      table "-avx2" portable avx2 "$AB/ab-$host-avx2"
      cp "$AB/binaries.txt" "$here/binaries.txt" ;;
    pack)
      for d in "ab-$host" "ab-$host-avx2"; do
        python3 "$here/pack_raw.py" "$AB/$d" "$here/raw-$d.tar.gz"
      done ;;
    retable)
      tmp="$(mktemp -d)"
      trap 'rm -rf "$tmp"' EXIT
      native=() avx2=()
      for t in "$here"/raw-ab-*.tar.gz; do
        tar -xzf "$t" -C "$tmp"
        d="$(basename "$t" .tar.gz)"
        d="$tmp/${d#raw-}"
        case "$d" in *-avx2) avx2+=("$d") ;; *) native+=("$d") ;; esac
      done
      table "" native portable "${native[@]}"
      table "-avx2" portable avx2 "${avx2[@]}" ;;
    *) sed -n '2,26p' "$0" >&2; exit 2 ;;
  esac
done

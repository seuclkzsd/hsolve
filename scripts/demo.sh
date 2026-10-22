#!/usr/bin/env bash
# hsolve demo: solve every example case (examples/), check each result independently and print a
# summary table - scripts/demo.py does the work (needs Python 3 with numpy and scipy).
#
#   scripts/demo.sh [--quick] [--threads N] [--cases a,b] [--out DIR] [--hsolve PATH]
#
# Without numpy / scipy it still runs every example with the hsolve executable and prints the
# solver's own summary (no independent evaluation) - e.g. a release package on a bare system.
# PYTHON selects the interpreter (default python3). Exit status 0 when everything passed.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(dirname "$here")"
py="${PYTHON:-python3}"
if command -v "$py" >/dev/null 2>&1 && "$py" -c "import numpy, scipy" >/dev/null 2>&1; then
  exec "$py" "$here/demo.py" "$@"
fi

echo "demo: no Python with numpy and scipy - running the solver only (no independent evaluation)" >&2
hsolve="${HSOLVE:-}"
threads="" out="" cases=""
while [ $# -gt 0 ]; do
  case "$1" in
    --hsolve) hsolve="$2"; shift 2 ;;
    --threads) threads="$2"; shift 2 ;;
    --out) out="$2"; shift 2 ;;
    --cases) cases="${2//,/ }"; shift 2 ;;
    --quick) cases="waveguide-50ghz near-singular-shift"; shift ;;
    --no-eval) shift ;;
    *) echo "demo: unknown option $1" >&2; exit 2 ;;
  esac
done
if [ -z "$hsolve" ]; then
  for cand in "$root/bin/hsolve" "$root/build/release/hsolve" "$(command -v hsolve || true)"; do
    if [ -n "$cand" ] && [ -x "$cand" ]; then hsolve="$cand"; break; fi
  done
fi
[ -n "$hsolve" ] && [ -x "$hsolve" ] || { echo "demo: no hsolve executable found (--hsolve PATH)" >&2; exit 2; }
if [ -z "$threads" ]; then
  threads="$(nproc 2>/dev/null || echo 4)"
  [ "$threads" -gt 16 ] && threads=16
fi
out="${out:-$(mktemp -d "${TMPDIR:-/tmp}/hsolve-demo-XXXXXX")}"
mkdir -p "$out"
if [ -z "$cases" ]; then
  cases="$(cd "$root/examples/cases" && ls)"
fi
export OMP_NUM_THREADS="$threads" OPENBLAS_NUM_THREADS="$threads"  # as tools/run/guard.py does
version="$("$hsolve" --A unused.npz --version 2>&1 || true)"  # the parser wants --A even here
echo "${version%%$'\n'*}"
failed=0
for name in $cases; do
  dir="$root/examples/cases/$name"
  [ -d "$dir" ] || { echo "demo: unknown example $name" >&2; exit 2; }
  args=(--A "$dir/A.npz" --config "$dir/config.json" --threads "$threads" --out "$out/$name")
  [ -f "$dir/B.npz" ] && args+=(--B "$dir/B.npz")
  echo
  echo "== $name"
  rc=0
  "$hsolve" "${args[@]}" > "$out/$name.log" 2>&1 || rc=$?
  grep -E "^n=|^certificate|^warning" "$out/$name.log" || true
  if [ "$rc" -ne 0 ]; then
    echo "   FAILED (exit $rc)"
    tail -3 "$out/$name.log"
    failed=1
  fi
done
echo
echo "results: $out (report.json per case; install numpy and scipy for the independent check)"
exit "$failed"

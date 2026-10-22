#!/usr/bin/env bash
set -uo pipefail
cd /tmp/os2026-p10-repair.9doyhO
python -u /tmp/os2026-p34/regress.py bounded > /tmp/os2026-p34/regression-bounded.log 2>&1
printf 'bounded regression exit: %s\n' "$?"
python -u /tmp/os2026-p34/regress.py boundednative > /tmp/os2026-p34/regression-boundednative.log 2>&1
printf 'boundednative regression exit: %s\n' "$?"
set -e
python -u /tmp/os2026-p34/compare.py --solvers hsolve-bounded,hsolve-boundednative --reps 1 --timeout 30 --cores 8-15 --mem-gb 12 --root /share/home/linzihan/os2026/data --tag p34-bounded-main --out-dir /tmp/os2026-p34 syn-zero-cluster-complex-1e4 syn-multiplicity-complex-1e4 syn-near-singular-complex-1e4 syn-wide-range-complex-1e4 syn-near-singular-complex-1e5 syn-ghep-zero-cluster-complex-1e4 yee-photonic-rods-1e4 yee-photonic-spheres-1e4 yee-bloch-1e4 > /tmp/os2026-p34/bounded-main.log 2>&1
python -u /tmp/os2026-p34/reference_checks.py > /tmp/os2026-p34/reference-checks.log 2>&1

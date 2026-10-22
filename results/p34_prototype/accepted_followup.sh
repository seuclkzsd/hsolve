#!/usr/bin/env bash
set -uo pipefail
cd /tmp/os2026-p10-repair.9doyhO
python -u /tmp/os2026-p34/regress.py accepted > /tmp/os2026-p34/regression-accepted.log 2>&1
printf 'accepted regression exit: %s\n' "$?"
python -u /tmp/os2026-p34/regress.py acceptednative > /tmp/os2026-p34/regression-acceptednative.log 2>&1
printf 'acceptednative regression exit: %s\n' "$?"
set -e
python -u /tmp/os2026-p34/compare.py --solvers hsolve-accepted,hsolve-acceptednative --reps 1 --timeout 30 --cores 8-15 --mem-gb 12 --root /share/home/linzihan/os2026/data --tag p34-accepted-main --out-dir /tmp/os2026-p34 syn-zero-cluster-complex-1e4 syn-multiplicity-complex-1e4 syn-near-singular-complex-1e4 syn-wide-range-complex-1e4 syn-near-singular-complex-1e5 syn-ghep-zero-cluster-complex-1e4 yee-photonic-rods-1e4 yee-photonic-spheres-1e4 yee-bloch-1e4 > /tmp/os2026-p34/accepted-main.log 2>&1

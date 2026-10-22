#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
python -u /tmp/os2026-p34/compare.py --solvers hsolve-base,hsolve-guarded,hsolve-projected,hsolve-projectednative,hsolve-projectedlu --reps 1 --timeout 120 --cores 8-15 --mem-gb 12 --root /share/home/linzihan/os2026/data --tag p34-main-diagnostic --out-dir /tmp/os2026-p34 syn-zero-cluster-complex-1e4 syn-multiplicity-complex-1e4 syn-near-singular-complex-1e4 syn-wide-range-complex-1e4 syn-near-singular-complex-1e5 syn-ghep-zero-cluster-complex-1e4

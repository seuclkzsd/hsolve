#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
python -u /tmp/os2026-p33/compare.py --solvers hsolve-base,hsolve-requested,hsolve-requestedlu --reps 1 --timeout 120 --cores 8-15 --mem-gb 12 --root ~/os2026/data --tag p33-diagnostic-v2 --out-dir /tmp/os2026-p33 syn-zero-cluster-complex-1e4 syn-multiplicity-complex-1e4 syn-near-singular-complex-1e4 syn-wide-range-complex-1e4 syn-near-singular-complex-1e5 syn-ghep-zero-cluster-complex-1e4

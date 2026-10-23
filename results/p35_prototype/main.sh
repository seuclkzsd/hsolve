#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
python -u /tmp/os2026-p35/compare.py --solvers hsolve-accepted,hsolve-packed,hsolve-acceptednative,hsolve-packednative --reps 1 --timeout 120 --cores 8-15 --mem-gb 12 --root ~/os2026/data --tag p35-main --out-dir /tmp/os2026-p35 syn-zero-cluster-complex-1e4 syn-multiplicity-complex-1e4 syn-near-singular-complex-1e4 syn-wide-range-complex-1e4 syn-near-singular-complex-1e5 syn-ghep-zero-cluster-complex-1e4 yee-photonic-rods-1e4 yee-photonic-spheres-1e4 yee-bloch-1e4

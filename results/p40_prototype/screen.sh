#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
python -u /tmp/os2026-p40/compare.py --solvers hsolve-dd-t1,hsolve-dd-t2,hsolve-dd-t4,hsolve-dd-t8,hsolve-dd-t16,hsolve-reuse-t1,hsolve-reuse-t2,hsolve-reuse-t4,hsolve-reuse-t8,hsolve-reuse-t16,slepc --reps 3 --timeout 120 --cores 16-31 --mem-gb 32 --root ~/os2026/data --slepc-profile best --slepc-profile-file /tmp/os2026-p34/slepc-profiles.json --tag p40-screen --out-dir /tmp/os2026-p40 syn-zero-cluster-complex-1e4 syn-multiplicity-complex-1e4 syn-near-singular-complex-1e4 syn-wide-range-complex-1e4 syn-near-singular-complex-1e5 syn-ghep-zero-cluster-complex-1e4 yee-photonic-rods-1e4 yee-photonic-spheres-1e4 yee-bloch-1e4

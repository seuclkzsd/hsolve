#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
python -u /tmp/os2026-p36/compare.py --solvers hsolve-base,hsolve-native,hsolve-control,hsolve-fused,hsolve-simd,slepc --reps 5 --timeout 120 --cores 16-31 --mem-gb 32 --root /share/home/linzihan/os2026/data --slepc-profile best --slepc-profile-file /tmp/os2026-p34/slepc-profiles.json --tag p36-screen --out-dir /tmp/os2026-p36 syn-zero-cluster-complex-1e4 syn-multiplicity-complex-1e4 syn-near-singular-complex-1e4 syn-wide-range-complex-1e4 syn-near-singular-complex-1e5 syn-ghep-zero-cluster-complex-1e4 yee-photonic-rods-1e4 yee-photonic-spheres-1e4 yee-bloch-1e4

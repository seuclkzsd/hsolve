#!/usr/bin/env bash
set -uo pipefail
cd /tmp/os2026-p10-repair.9doyhO
python -u /tmp/os2026-p34/regress.py carried > /tmp/os2026-p34/regression-carried.log 2>&1
printf 'carried regression exit: %s\n' "$?"
python -u /tmp/os2026-p34/regress.py carriednative > /tmp/os2026-p34/regression-carriednative.log 2>&1
printf 'carriednative regression exit: %s\n' "$?"
set -e
python -u /tmp/os2026-p34/prepare_fresh.py
python -u /tmp/os2026-p34/fresh_checks.py > /tmp/os2026-p34/fresh.log 2>&1
python -u /tmp/os2026-p34/compare.py --solvers hsolve-base,hsolve-carried,hsolve-carriednative,slepc --reps 1 --timeout 120 --cores 8-15 --mem-gb 12 --root /share/home/linzihan/os2026/data --slepc-profile best --slepc-profile-file /tmp/os2026-p28/slepc-complex-profiles.json --tag p34-carried-main --out-dir /tmp/os2026-p34 syn-zero-cluster-complex-1e4 syn-multiplicity-complex-1e4 syn-near-singular-complex-1e4 syn-wide-range-complex-1e4 syn-near-singular-complex-1e5 syn-ghep-zero-cluster-complex-1e4 yee-photonic-rods-1e4 yee-photonic-spheres-1e4 yee-bloch-1e4 > /tmp/os2026-p34/carried-main.log 2>&1

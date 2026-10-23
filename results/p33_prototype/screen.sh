#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
python -u /tmp/os2026-p33/compare.py --solvers hsolve-base,hsolve-counts,hsolve-lucached,hsolve-requested,hsolve-requestedlu,slepc --reps 5 --timeout 120 --cores 16-31 --mem-gb 32 --root ~/os2026/data --slepc-profile best --slepc-profile-file /tmp/os2026-p28/slepc-complex-profiles.json --tag p33-screen --out-dir /tmp/os2026-p33 syn-zero-cluster-complex-1e4 syn-multiplicity-complex-1e4 syn-near-singular-complex-1e4 syn-wide-range-complex-1e4 syn-near-singular-complex-1e5 syn-ghep-zero-cluster-complex-1e4

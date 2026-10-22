#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
python -u /tmp/os2026-p39/compare.py --solvers hsolve-base,hsolve-native,hsolve-control,hsolve-scalar,hsolve-dd,hsolve-direct,hsolve-reuse,slepc --reps 5 --timeout 120 --cores 16-31 --mem-gb 32 --root /share/home/linzihan/os2026/data --slepc-profile best --slepc-profile-file /tmp/os2026-p34/slepc-profiles.json --tag p39-recheck --out-dir /tmp/os2026-p39 syn-multiplicity-complex-1e4 syn-ghep-zero-cluster-complex-1e4 yee-bloch-1e4

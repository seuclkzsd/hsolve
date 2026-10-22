#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
python -u /tmp/os2026-p33/prepare_recovery.py
python -u /tmp/os2026-p33/recovery-only/build.py requested
python -u /tmp/os2026-p33/recovery-only/build.py requestedlu
python -u /tmp/os2026-p33/compare.py --solvers hsolve-recovery --reps 1 --timeout 120 --cores 8-15 --mem-gb 12 --root /share/home/linzihan/os2026/data --tag p33-recovery-error --out-dir /tmp/os2026-p33 syn-near-singular-complex-1e4
python -u /tmp/os2026-p33/compare.py --solvers hsolve-recoverylu --reps 1 --timeout 120 --cores 8-15 --mem-gb 12 --root /share/home/linzihan/os2026/data --tag p33-recovery-incomplete --out-dir /tmp/os2026-p33 syn-near-singular-complex-1e5
python -u /tmp/os2026-p33/verify_recovery.py

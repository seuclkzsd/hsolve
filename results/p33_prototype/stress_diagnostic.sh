#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
python -u /tmp/os2026-p33/compare_stress.py --solvers hsolve-base,hsolve-requested,hsolve-requestedlu,slepc --reps 1 --timeout 120 --cores 8-15 --mem-gb 12 --root /tmp/os2026-p33/accepted-data --tag p33-stress-block16 --out-dir /tmp/os2026-p33 accepted-hep-small accepted-hep-large accepted-ghep-small accepted-ghep-large

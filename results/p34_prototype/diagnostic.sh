#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
python -u /tmp/os2026-p34/compare.py --solvers hsolve-base,hsolve-guarded,hsolve-projected,hsolve-projectednative,hsolve-projectedlu --reps 1 --timeout 120 --cores 8-15 --mem-gb 12 --root /tmp/os2026-p33/accepted-data --tag p34-diagnostic --out-dir /tmp/os2026-p34 accepted-hep-small accepted-hep-large accepted-ghep-small accepted-ghep-large

#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
python -u /tmp/os2026-p33/prepare_contracts.py
python -u /tmp/os2026-p33/compare.py --solvers hsolve-base,hsolve-requested,hsolve-requestedlu --reps 1 --timeout 120 --cores 8-15 --mem-gb 12 --root /tmp/os2026-p33/contract-data-v2 --tag p33-contracts-v2 --out-dir /tmp/os2026-p33 exact-zero-hep exact-quarter-ghep new-cluster-hep new-near-hep new-cluster-ghep counter-fallback-memory counter-fallback-factor counter-fallback-allocation backend-result-recovery
python -u /tmp/os2026-p33/verify_contracts.py

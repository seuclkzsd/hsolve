#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
env/run.sh python tools/run/guard.py --skip-busy-check --cores 8-15 --mem-gb 12 --timeout 300 --summary /tmp/os2026-p39/budget-v2-guard.json -- python -u /tmp/os2026-p39/budget_check_v2.py > /tmp/os2026-p39/budget-v2.log 2>&1
env/run.sh python tools/run/guard.py --skip-busy-check --cores 8-15 --mem-gb 12 --timeout 300 --summary /tmp/os2026-p39/prepare-guard.json -- python -u /tmp/os2026-p39/prepare_cases.py > /tmp/os2026-p39/prepare.log 2>&1
env/run.sh python tools/run/guard.py --skip-busy-check --cores 8-15 --mem-gb 12 --timeout 1200 --summary /tmp/os2026-p39/diagnostic-guard.json -- python -u /tmp/os2026-p39/diagnostics.py > /tmp/os2026-p39/diagnostic.log 2>&1
env/run.sh python tools/run/guard.py --skip-busy-check --cores 8-15 --mem-gb 12 --timeout 1800 --summary /tmp/os2026-p39/full-guard.json -- bash -c 'python -u /tmp/os2026-p39/full_regression.py direct && python -u /tmp/os2026-p39/full_regression.py reuse' > /tmp/os2026-p39/full.log 2>&1

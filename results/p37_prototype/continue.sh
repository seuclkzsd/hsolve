#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
env/run.sh python tools/run/guard.py --skip-busy-check --cores 8-15 --mem-gb 12 --timeout 1200 --summary /tmp/os2026-p37/build-checks-guard.json -- bash /tmp/os2026-p37/build_checks.sh > /tmp/os2026-p37/build-checks.log 2>&1
env/run.sh python tools/run/guard.py --skip-busy-check --cores 8-15 --mem-gb 12 --timeout 1200 --summary /tmp/os2026-p37/diagnostic-guard.json -- python -u /tmp/os2026-p37/diagnostics.py > /tmp/os2026-p37/diagnostic.log 2>&1
env/run.sh python tools/run/guard.py --skip-busy-check --cores 8-15 --mem-gb 12 --timeout 1800 --summary /tmp/os2026-p37/full-guard.json -- bash /tmp/os2026-p37/full.sh > /tmp/os2026-p37/full.log 2>&1
env/run.sh python -u /tmp/os2026-p37/monitored_screen.py > /tmp/os2026-p37/monitor-driver.log 2>&1

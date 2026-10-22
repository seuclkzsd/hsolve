#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
while ! test -f /tmp/os2026-p35/full-guard.json; do sleep 5; done
env/run.sh python tools/run/guard.py --skip-busy-check --cores 8-15 --mem-gb 12 --timeout 1800 --summary /tmp/os2026-p35/budget-guard.json -- bash /tmp/os2026-p35/budget.sh > /tmp/os2026-p35/budget.log 2>&1
env/run.sh python tools/run/guard.py --skip-busy-check --cores 8-15 --mem-gb 12 --timeout 600 --summary /tmp/os2026-p35/main-guard.json -- bash /tmp/os2026-p35/main.sh > /tmp/os2026-p35/main.log 2>&1
env/run.sh python -u /tmp/os2026-p35/monitored_screen.py > /tmp/os2026-p35/monitor-driver.log 2>&1

#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
while ! test -f /tmp/os2026-p36/diagnostic-guard.json; do sleep 5; done
env/run.sh python -I /tmp/os2026-p36/gate.py diagnostic
env/run.sh python tools/run/guard.py --skip-busy-check --cores 8-15 --mem-gb 12 --timeout 1800 --summary /tmp/os2026-p36/full-guard.json -- bash /tmp/os2026-p36/full.sh > /tmp/os2026-p36/full.log 2>&1
env/run.sh python -I /tmp/os2026-p36/gate.py full
env/run.sh python -u /tmp/os2026-p36/monitored_screen.py > /tmp/os2026-p36/monitor-driver.log 2>&1

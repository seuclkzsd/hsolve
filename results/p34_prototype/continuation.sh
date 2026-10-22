#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
while ! test -f /tmp/os2026-p34/extended-guard.json; do sleep 5; done
env/run.sh python tools/run/guard.py --skip-busy-check --cores 8-15 --mem-gb 12 --timeout 1200 --summary /tmp/os2026-p34/bounded-guard.json -- bash /tmp/os2026-p34/bounded.sh > /tmp/os2026-p34/bounded.log 2>&1
env/run.sh python tools/run/guard.py --skip-busy-check --cores 8-15 --mem-gb 12 --timeout 600 --summary /tmp/os2026-p34/bounded-followup-guard.json -- bash /tmp/os2026-p34/bounded_followup.sh > /tmp/os2026-p34/bounded-followup.log 2>&1
env/run.sh python -u /tmp/os2026-p34/monitored_screen.py > /tmp/os2026-p34/monitor-driver.log 2>&1

#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
for attempt in $(seq 1 360); do
  if test -f /tmp/os2026-p35/screen-monitor-result.json; then break; fi
  sleep 5
done
test -f /tmp/os2026-p35/screen-monitor-result.json
env/run.sh python tools/run/guard.py --skip-busy-check --cores 8-15 --mem-gb 12 --timeout 900 --summary /tmp/os2026-p35/capped-guard.json -- bash /tmp/os2026-p35/capped.sh > /tmp/os2026-p35/capped.log 2>&1
if env/run.sh python -I /tmp/os2026-p35/capped_gate.py; then
  env/run.sh python tools/run/guard.py --skip-busy-check --cores 8-15 --mem-gb 12 --timeout 1800 --summary /tmp/os2026-p35/capped-validation-guard.json -- bash /tmp/os2026-p35/validate_capped.sh > /tmp/os2026-p35/capped-validation.log 2>&1
fi

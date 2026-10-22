#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
# The original checks_v2.sh owns the running regression. Do not restart it.
for attempt in $(seq 1 900); do
  if test -f /tmp/os2026-p39/full-guard.json; then break; fi
  sleep 1
done
env/run.sh python -I -c "import json; from pathlib import Path; p=Path('/tmp/os2026-p39'); assert json.loads((p/'full-guard.json').read_text())['returncode']==0; assert all(json.loads((p/('full-'+v)/'summary.json').read_text())['success'] for v in ['direct','reuse'])"
env/run.sh python tools/run/guard.py --skip-busy-check --cores 8-15 --mem-gb 12 --timeout 300 --summary /tmp/os2026-p39/extra-guard.json -- python -u /tmp/os2026-p39/extra_checks.py > /tmp/os2026-p39/extra.log 2>&1
env/run.sh python -I /tmp/os2026-p39/start_screen.py

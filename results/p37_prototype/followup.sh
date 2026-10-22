#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
while ! test -f /tmp/os2026-p37/full-guard.json; do sleep 5; done
env/run.sh python -I -c 'import json; from pathlib import Path; p=Path("/tmp/os2026-p37"); assert json.loads((p/"full-guard.json").read_text())["returncode"]==0; assert all(json.loads((p/("full-"+v)/"summary.json").read_text())["success"] for v in ["scalar","dd"])'
env/run.sh python tools/run/guard.py --skip-busy-check --cores 8-15 --mem-gb 12 --timeout 300 --summary /tmp/os2026-p37/boundary-guard.json -- python -u /tmp/os2026-p37/boundary.py > /tmp/os2026-p37/boundary.log 2>&1
env/run.sh python -u /tmp/os2026-p37/monitored_screen.py > /tmp/os2026-p37/monitor-driver.log 2>&1

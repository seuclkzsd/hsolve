#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
while ! test -f /tmp/os2026-p36/full-guard.json; do sleep 5; done
env/run.sh python -I -c 'import json; from pathlib import Path; p=Path("/tmp/os2026-p36"); assert json.loads((p/"full-guard.json").read_text())["returncode"]==0; assert all(json.loads((p/("full-"+v)/"summary.json").read_text())["success"] for v in ["fused","simd"])'
env/run.sh python tools/run/guard.py --skip-busy-check --cores 8-15 --mem-gb 12 --timeout 1800 --summary /tmp/os2026-p36/reuse-validation-guard.json -- bash /tmp/os2026-p36/reuse_validation.sh > /tmp/os2026-p36/reuse-validation.log 2>&1
env/run.sh python -u /tmp/os2026-p36/monitored_screen.py > /tmp/os2026-p36/monitor-driver.log 2>&1

#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
env/run.sh python -I -c 'import json; from pathlib import Path; p=Path("/tmp/os2026-p37"); assert json.loads((p/"residual-v2-guard.json").read_text())["returncode"]==0; assert all(len(json.loads((p/(v+"-check-results.json")).read_text()))==1540 for v in ["control","scalar","dd"])'
env/run.sh python tools/run/guard.py --skip-busy-check --cores 8-15 --mem-gb 12 --timeout 1200 --summary /tmp/os2026-p37/diagnostic-guard.json -- python -u /tmp/os2026-p37/diagnostics.py > /tmp/os2026-p37/diagnostic.log 2>&1
env/run.sh python tools/run/guard.py --skip-busy-check --cores 8-15 --mem-gb 12 --timeout 1800 --summary /tmp/os2026-p37/full-guard.json -- bash /tmp/os2026-p37/full.sh > /tmp/os2026-p37/full.log 2>&1

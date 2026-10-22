#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
env/run.sh python -I -c "import json; from pathlib import Path; p=Path('/tmp/os2026-p40/v3'); assert json.loads((p/'linear-guard.json').read_text())['returncode']==0; assert json.loads((p/'boundary-qualified.json').read_text())['qualified']"
env/run.sh python tools/run/guard.py --skip-busy-check --cores 8-15 --mem-gb 12 --timeout 1200 --summary /tmp/os2026-p40/v3/diagnostic-guard.json -- python -u /tmp/os2026-p40/v3/diagnostics.py > /tmp/os2026-p40/v3/diagnostic.log 2>&1
env/run.sh python tools/run/guard.py --skip-busy-check --cores 8-15 --mem-gb 12 --timeout 1800 --summary /tmp/os2026-p40/v3/full-guard.json -- bash -c 'python -u /tmp/os2026-p40/v3/full_regression.py control && python -u /tmp/os2026-p40/v3/full_regression.py enclosed' > /tmp/os2026-p40/v3/full.log 2>&1
env/run.sh python -I /tmp/os2026-p40/v3/verify_contracts.py

#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
python -u /tmp/os2026-p36/prepare_reuse.py
python -u /tmp/os2026-p36/build_reuse.py reuse
/tmp/os2026-p36/backend-check-reuse /tmp/os2026-p36/reuse-manifest.json > /tmp/os2026-p36/reuse-check.stdout 2> /tmp/os2026-p36/reuse-check.stderr
python -u /tmp/os2026-p36/verify.py reuse
python -u /tmp/os2026-p36/diagnostics_reuse.py
python -u /tmp/os2026-p36/verify_reuse.py
python -u /tmp/os2026-p36/full_regression_reuse.py reuse > /tmp/os2026-p36/full-reuse.log 2>&1

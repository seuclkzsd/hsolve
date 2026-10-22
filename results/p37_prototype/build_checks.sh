#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
python -u /tmp/os2026-p37/prepare_checks.py
for variant in control scalar dd; do
  python -u /tmp/os2026-p37/build.py "$variant"
  /tmp/os2026-p37/backend-check-"$variant" /tmp/os2026-p37/"$variant"-manifest.json > /tmp/os2026-p37/"$variant"-check.stdout 2> /tmp/os2026-p37/"$variant"-check.stderr
  python -u /tmp/os2026-p37/verify.py "$variant"
done
python -u /tmp/os2026-p37/verify_residual.py

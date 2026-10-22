#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
python -u /tmp/os2026-p33/prepare_checks.py
for variant in requested requestedlu; do
 python -u /tmp/os2026-p33/build.py "$variant"
 /tmp/os2026-p33/backend-check-"$variant" /tmp/os2026-p33/"$variant"-manifest.json > /tmp/os2026-p33/"$variant"-check.stdout 2> /tmp/os2026-p33/"$variant"-check.stderr
 python -u /tmp/os2026-p33/verify.py "$variant"
done

#!/usr/bin/env bash
set -uo pipefail
cd /tmp/os2026-p10-repair.9doyhO
python -u /tmp/os2026-p35/pressure_capped.py
bash /tmp/os2026-p35/main_capped.sh
for variant in capped cappednative; do
  python -u /tmp/os2026-p35/full_regression_capped.py "$variant" > "/tmp/os2026-p35/full-$variant.log" 2>&1
  printf '%s full regression exit: %s\n' "$variant" "$?"
done

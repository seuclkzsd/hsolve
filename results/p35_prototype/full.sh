#!/usr/bin/env bash
set -uo pipefail
cd /tmp/os2026-p10-repair.9doyhO
for variant in base packed packednative; do
  python -u /tmp/os2026-p35/full_regression.py "$variant" > "/tmp/os2026-p35/full-$variant.log" 2>&1
  printf '%s full regression exit: %s\n' "$variant" "$?"
done

#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
for variant in scalar dd; do
  python -u /tmp/os2026-p37/full_regression.py "$variant" > /tmp/os2026-p37/full-"$variant".log 2>&1
done

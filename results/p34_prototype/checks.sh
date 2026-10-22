#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
python -u /tmp/os2026-p34/holdouts.py
bash /tmp/os2026-p34/main_diagnostic.sh

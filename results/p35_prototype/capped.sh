#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
python -u /tmp/os2026-p35/build_capped.py
python -u /tmp/os2026-p35/capped_checks.py

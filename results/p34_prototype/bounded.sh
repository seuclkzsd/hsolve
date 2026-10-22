#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
python -u /tmp/os2026-p34/build_refined.py
python -u /tmp/os2026-p34/build_windowed.py
python -u /tmp/os2026-p34/build_bounded.py
python -u /tmp/os2026-p34/bounded_checks.py

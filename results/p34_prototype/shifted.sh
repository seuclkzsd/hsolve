#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
python -u /tmp/os2026-p34/build_shifted.py
python -u /tmp/os2026-p34/shifted_checks.py

#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
python -u /tmp/os2026-p35/prepare_large.py
python -u /tmp/os2026-p35/budget_checks.py

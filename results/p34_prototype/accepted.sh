#!/usr/bin/env bash
set -euo pipefail
cd /tmp/os2026-p10-repair.9doyhO
python -u /tmp/os2026-p34/build_accepted.py
python -u /tmp/os2026-p34/accepted_checks.py
python -u /tmp/os2026-p34/prepare_validation.py
python -u /tmp/os2026-p34/validation_checks.py
bash /tmp/os2026-p34/accepted_followup.sh

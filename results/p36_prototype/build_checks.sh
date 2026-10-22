#!/usr/bin/env bash
set -uo pipefail
cd /tmp/os2026-p10-repair.9doyhO
python -u /tmp/os2026-p36/prepare_checks.py || exit $?
for variant in control fused simd; do
 python -u /tmp/os2026-p36/build.py "$variant" || exit $?
 /tmp/os2026-p36/backend-check-"$variant" /tmp/os2026-p36/"$variant"-manifest.json > /tmp/os2026-p36/"$variant"-check.stdout 2> /tmp/os2026-p36/"$variant"-check.stderr
 printf '%s backend check exit: %s\n' "$variant" "$?"
 python -u /tmp/os2026-p36/verify.py "$variant"
 printf '%s independent residual verification exit: %s\n' "$variant" "$?"
done
python -u /tmp/os2026-p36/equivalence.py

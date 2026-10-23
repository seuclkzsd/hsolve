#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 seuclkzsd and the hsolve contributors
# Build the portable release preset and package it as a relocatable binary tarball
# (tools/release/package.py: layout, checks, licences):
#
#   tools/release/package.sh [--skip-build] [--out DIR] [--version VER] [--allow-missing-legal]
#
# Output: <out>/hsolve-<version>-linux-x86_64.tar.gz (+ .sha256), default out = build/package.
# Runs inside the project environment (env/activate.sh; on the cluster nodes through
# tools/dev/cluster_run.sh, which also applies the build lane's limits). The CI release workflow
# (.github/workflows/release.yml) runs the same script on tags v*.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"
skip_build=0
if [ "${1:-}" = "--skip-build" ]; then
  skip_build=1
  shift
fi
[ "$skip_build" = 1 ] || tools/dev/build.sh release
# shellcheck disable=SC1091
source env/activate.sh
exec python3 tools/release/package.py --build build/release "$@"

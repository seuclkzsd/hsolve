#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 seuclkzsd and the hsolve contributors
# Check a release tarball the way a user meets it: unpack it into a new directory away from the
# source tree, then - with whatever the machine offers, no build environment needed - print the
# version and run the self-check (scripts/demo.sh --quick: two examples; with Python 3 + numpy +
# scipy each result is also checked independently, without them the solver's own report is shown).
#
#   tools/release/verify_package.sh TARBALL [WORKDIR] [-- DEMO-OPTIONS...]
#
# TARBALL is verified against TARBALL.sha256 or a SHA256SUMS next to it when one exists. WORKDIR
# (default: a new temporary directory) receives the unpacked package and the demo output; the run
# uses a minimal environment (PATH=/usr/bin:/bin, no LD_LIBRARY_PATH, no conda). Used by
# .github/workflows/release.yml in plain distribution containers (CentOS 7 = glibc 2.17, Debian,
# Ubuntu) and on the cluster nodes (docs/INSTALL.md). Exit status 0 when everything passed.
set -euo pipefail
[ $# -ge 1 ] || { sed -n '4,15p' "$0" >&2; exit 2; }
tarball="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
shift
work=""
if [ $# -gt 0 ] && [ "$1" != "--" ]; then
  work="$1"
  shift
fi
[ "${1:-}" != "--" ] || shift
work="${work:-$(mktemp -d "${TMPDIR:-/tmp}/hsolve-verify-XXXXXX")}"
mkdir -p "$work"
work="$(cd "$work" && pwd)"

name="$(basename "$tarball" .tar.gz)"
dir="$(dirname "$tarball")"
if [ -f "$tarball.sha256" ]; then
  (cd "$dir" && sha256sum -c "$(basename "$tarball").sha256")
elif [ -f "$dir/SHA256SUMS" ]; then
  (cd "$dir" && grep " $(basename "$tarball")\$" SHA256SUMS | sha256sum -c -)
else
  echo "verify_package: no checksum file next to $tarball" >&2
fi
rm -rf "${work:?}/$name"
tar -xzf "$tarball" -C "$work"
pkg="$work/$name"
[ -x "$pkg/bin/hsolve" ] || { echo "verify_package: $pkg/bin/hsolve missing" >&2; exit 1; }

echo "== $(uname -sm), $(ldd --version 2>&1 | head -1)"
bare=(env -i PATH=/usr/bin:/bin HOME="$work" TMPDIR="$work" LANG=C)
"${bare[@]}" "$pkg/bin/hsolve" --version | head -1
if "${bare[@]}" ldd "$pkg/bin/hsolve" | grep -q "not found"; then
  "${bare[@]}" ldd "$pkg/bin/hsolve" >&2
  echo "verify_package: unresolved libraries" >&2
  exit 1
fi
"${bare[@]}" "$pkg/scripts/demo.sh" --quick --threads 2 --out "$work/demo" "$@"
echo "verify_package: $name passed in $pkg"

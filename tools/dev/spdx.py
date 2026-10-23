#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 seuclkzsd and the hsolve contributors
"""Check or add the SPDX licence header of hsolve's own source files.

Every source file of the project carries two comment lines at the top (after a shebang and a Python
encoding line, if any):

    // SPDX-License-Identifier: Apache-2.0
    // SPDX-FileCopyrightText: 2026 seuclkzsd and the hsolve contributors

Files with code adapted from third-party sources name both licences (MIXED below; the original
notices stay in the file and in THIRD_PARTY_NOTICES). Not covered: third_party/ (upstream sources and
our MUMPS patches, CeCILL-C), results/ (dated engineering records and research prototypes),
tools/release/licenses/ (licence texts), data files and documentation (licensed as a whole by LICENSE).

    python3 tools/dev/spdx.py --check     exit 1 and list every file whose header is missing or wrong
    python3 tools/dev/spdx.py --fix       add the missing headers (idempotent)
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

LICENSE = "Apache-2.0"
COPYRIGHT = "2026 seuclkzsd and the hsolve contributors"
# Code adapted from OpenBLAS 0.3.34 (BSD-3-Clause; THIRD_PARTY_NOTICES part 1).
MIXED = {
    "src/blas/narrow_kernels.cpp": "Apache-2.0 AND BSD-3-Clause",
    "src/blas/simd_kernels.hpp": "Apache-2.0 AND BSD-3-Clause",
}
ROOTS = ("src/", "include/", "apps/", "python/", "tests/", "tools/", "bench/", "scripts/", "examples/",
         "env/", "cmake/")
EXCLUDE = ("third_party/", "results/", "tools/release/licenses/")
SLASH = (".c", ".h", ".cc", ".cpp", ".hpp", ".cu")
HASH = (".py", ".sh", ".cmake")
HASH_NAMES = ("CMakeLists.txt", "Dockerfile")
ENCODING = re.compile(r"^#.*coding[:=]")
DOCKER_DIRECTIVE = re.compile(r"^#\s*(syntax|escape|check)\s*=", re.IGNORECASE)  # must stay first in a Dockerfile


def comment_prefix(path: str) -> str | None:
    name = path.rsplit("/", 1)[-1]
    if path.endswith(SLASH):
        return "//"
    if path.endswith(HASH) or name in HASH_NAMES:
        return "#"
    return None


def covered(path: str) -> bool:
    if path.startswith(EXCLUDE) or comment_prefix(path) is None:
        return False
    return path.startswith(ROOTS) or "/" not in path


def expected(path: str) -> list[str]:
    c = comment_prefix(path)
    return [f"{c} SPDX-License-Identifier: {MIXED.get(path, LICENSE)}",
            f"{c} SPDX-FileCopyrightText: {COPYRIGHT}"]


def header_start(lines: list[str]) -> int:
    """Index where the header belongs: after a shebang, a Python encoding line or Dockerfile parser
    directives."""
    i = 0
    if lines and lines[0].startswith("#!"):
        i = 1
    if len(lines) > i and ENCODING.match(lines[i]):
        i += 1
    while len(lines) > i and DOCKER_DIRECTIVE.match(lines[i]):
        i += 1
    return i


def tracked_files(root: Path) -> list[str]:
    out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], check=True, capture_output=True).stdout
    return sorted(p for p in out.decode().split("\0") if p and covered(p) and (root / p).is_file()
                  and not (root / p).is_symlink())


def check_file(root: Path, path: str) -> str | None:
    """None when the header is right, else what is wrong."""
    lines = (root / path).read_text(encoding="utf-8").splitlines()
    i = header_start(lines)
    want = expected(path)
    have = lines[i:i + 2]
    if have == want:
        return None
    if any("SPDX-License-Identifier" in line for line in lines[:12]):
        return "SPDX header present but not as expected at line %d" % (i + 1)
    return "no SPDX header"


def fix_file(root: Path, path: str) -> bool:
    """Add the header if no SPDX line is there yet; True when the file changed."""
    p = root / path
    text = p.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    if any("SPDX-License-Identifier" in line for line in lines[:12]):
        return False
    i = header_start([line.rstrip("\n") for line in lines])
    if i and not lines[i - 1].endswith("\n"):
        lines[i - 1] += "\n"
    head = "".join(line + "\n" for line in expected(path))
    p.write_text("".join(lines[:i]) + head + "".join(lines[i:]), encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="report files whose header is missing or wrong")
    mode.add_argument("--fix", action="store_true", help="add missing headers")
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = ap.parse_args(argv)
    files = tracked_files(args.root)
    if args.fix:
        changed = [f for f in files if fix_file(args.root, f)]
        print(f"spdx: {len(changed)} of {len(files)} files given a header")
    bad = [(f, why) for f in files if (why := check_file(args.root, f))]
    for f, why in bad:
        print(f"{f}: {why}", file=sys.stderr)
    if not args.fix:
        print(f"spdx: {len(files) - len(bad)} of {len(files)} files have the header")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

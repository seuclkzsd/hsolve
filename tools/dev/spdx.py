#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 seuclkzsd and the hsolve contributors
"""Check or add the SPDX licence header of hsolve's own source files.

Every source file of the project carries two comment lines at the top (after a shebang and a Python
encoding line, if any):

    // SPDX-License-Identifier: Apache-2.0
    // SPDX-FileCopyrightText: 2026 seuclkzsd and the hsolve contributors

Source files are recognised by their extension, by name (CMakeLists.txt, Dockerfile) or, without an
extension, by a "#!" first line (scripts such as apps/hsolve-mpirun). Files with code adapted from
third-party sources name both licences (MIXED below; the original notices stay in the file and in
THIRD_PARTY_NOTICES). Not covered: third_party/ (the upstream MUMPS source tarball and its licence) and
patches/ (our MUMPS patches; both CeCILL-C), results/ (dated engineering records and research prototypes),
tools/release/licenses/ (licence texts), data files and documentation (licensed as a whole by LICENSE).

The files checked are those git tracks; outside a git work tree (e.g. an unpacked source archive) the
covered directories are walked instead, skipping hidden and __pycache__ directories.

    python3 tools/dev/spdx.py --check     exit 1 and list every file whose header is missing or wrong
    python3 tools/dev/spdx.py --fix       add the missing headers (idempotent)
"""
from __future__ import annotations

import argparse
import os
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


def is_script(file: Path) -> bool:
    """A file starting with '#!' (an executable script whatever its name)."""
    try:
        with open(file, "rb") as f:
            return f.read(2) == b"#!"
    except OSError:
        return False


def comment_prefix(path: str, root: Path | None = None) -> str | None:
    """The comment marker of a covered file type, None for other files. Files without an extension
    are scripts when their first line is a shebang (root: where to read them; None: not read)."""
    name = path.rsplit("/", 1)[-1]
    if path.endswith(SLASH):
        return "//"
    if path.endswith(HASH) or name in HASH_NAMES:
        return "#"
    if root is not None and "." not in name and is_script(root / path):
        return "#"
    return None


def covered(path: str, root: Path | None = None) -> bool:
    if path.startswith(EXCLUDE) or comment_prefix(path, root) is None:
        return False
    return path.startswith(ROOTS) or "/" not in path


def expected(path: str, root: Path | None = None) -> list[str]:
    c = comment_prefix(path, root)
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


def git_top(root: Path) -> Path | None:
    """The top of the git work tree holding root, None outside one (or without git). cwd rather
    than git -C: the cluster nodes' git 1.8.3 predates -C."""
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root, check=True, capture_output=True,
                             text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return Path(top).resolve() if top else None


def walked_files(root: Path) -> list[str]:
    """Every file of the covered roots and the top directory, for a tree without git."""
    out = [p.name for p in root.iterdir() if p.is_file()]
    for top in ROOTS:
        for dirpath, dirnames, filenames in os.walk(root / top):
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "__pycache__"]
            rel = Path(dirpath).relative_to(root).as_posix()
            out += [f"{rel}/{f}" for f in filenames]
    return out


def tracked_files(root: Path) -> list[str]:
    """The covered files of root: those git tracks when root is the top of a git work tree, else
    (an unpacked source archive) the files found by walking the covered roots."""
    if git_top(root) == root.resolve():
        out = subprocess.run(["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True).stdout
        paths = out.decode().split("\0")
    else:
        paths = walked_files(root)
    return sorted(p for p in paths if p and (root / p).is_file() and not (root / p).is_symlink()
                  and covered(p, root))


def check_file(root: Path, path: str) -> str | None:
    """None when the header is right, else what is wrong."""
    lines = (root / path).read_text(encoding="utf-8").splitlines()
    i = header_start(lines)
    want = expected(path, root)
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
    head = "".join(line + "\n" for line in expected(path, root))
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

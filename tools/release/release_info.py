#!/usr/bin/env python3
"""Version checks and release notes for .github/workflows/release.yml (standard library only).

    release_info.py version REF_TYPE REF_NAME SHA
        prints "version=<v>" (for $GITHUB_OUTPUT). For a tag (REF_TYPE "tag") REF_NAME must be
        v<X.Y.Z>[-<pre>] with X.Y.Z = the CMake project version, and CHANGELOG.md (when present)
        must hold a section "## [<v>] - <YYYY-MM-DD>" without placeholders; <v> is REF_NAME without
        the "v". Any other ref (a dry run from a branch) gives "<X.Y.Z>-dev.<SHA[:7]>".
    release_info.py notes VERSION [--image IMAGE] [--repo URL]
        prints the release notes: the CHANGELOG.md section of VERSION (when present) and how to get
        the container image and the binary package.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TAG = re.compile(r"v(\d+\.\d+\.\d+)(-[0-9A-Za-z.-]+)?")
PLACEHOLDER = re.compile(r"\{\{|TODO|TBD")


def cmake_version(root: Path = ROOT) -> str:
    m = re.search(r"^project\(\s*hsolve\s+VERSION\s+(\d+\.\d+\.\d+)", (root / "CMakeLists.txt").read_text(), re.M)
    if not m:
        raise SystemExit("release_info: no 'project(hsolve VERSION X.Y.Z' in CMakeLists.txt")
    return m.group(1)


def changelog_section(version: str, root: Path = ROOT) -> tuple[str, str] | None:
    """(heading, body) of the section '## [version] ...' of CHANGELOG.md, None without one."""
    path = root / "CHANGELOG.md"
    if not path.is_file():
        return None
    text = path.read_text()
    m = re.search(rf"^## \[{re.escape(version)}\][^\n]*$", text, re.M)
    if not m:
        return None
    rest = text[m.end():]
    end = re.search(r"^## \[", rest, re.M)
    return m.group(0), rest[:end.start() if end else len(rest)].strip("\n")


def version_for(ref_type: str, ref_name: str, sha: str, root: Path = ROOT) -> str:
    base = cmake_version(root)
    if ref_type != "tag":
        return f"{base}-dev.{sha[:7]}"
    m = TAG.fullmatch(ref_name)
    if not m:
        raise SystemExit(f"release_info: tag '{ref_name}' is not v<X.Y.Z>[-<pre>]")
    if m.group(1) != base:
        raise SystemExit(f"release_info: tag {ref_name} but CMakeLists.txt says version {base}")
    version = ref_name[1:]
    if (root / "CHANGELOG.md").is_file():
        section = changelog_section(version, root)
        if section is None:
            raise SystemExit(f"release_info: CHANGELOG.md has no section '## [{version}]'")
        heading, body = section
        if not re.search(r"\d{4}-\d{2}-\d{2}", heading) or PLACEHOLDER.search(heading + body):
            raise SystemExit(f"release_info: CHANGELOG.md section {heading!r} needs a date and no placeholders")
    return version


def notes(version: str, image: str, repo: str, root: Path = ROOT) -> str:
    tarball = f"hsolve-{version}-linux-x86_64.tar.gz"
    section = changelog_section(version, root)
    lines = [section[1], ""] if section else []
    lines += [
        "## 获取 / Get it",
        "",
        "容器镜像 / container image:",
        "",
        "```bash",
        f"docker run --rm {image}:{version} demo",
        "```",
        "",
        "二进制包（x86-64 Linux，glibc ≥ 2.17，解压即用）/ binary package (x86-64 Linux, glibc >= 2.17, relocatable):",
        "",
        "```bash",
        f"curl -LO {repo}/releases/download/v{version}/{tarball}",
        f"curl -LO {repo}/releases/download/v{version}/SHA256SUMS",
        "sha256sum -c SHA256SUMS --ignore-missing",
        f"tar -xzf {tarball} && hsolve-{version}-linux-x86_64/scripts/demo.sh --quick",
        "```",
        "",
        f"安装方式与资源需求见 / installation and resource needs: {repo}/blob/v{version}/docs/INSTALL.md",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("version")
    v.add_argument("ref_type")
    v.add_argument("ref_name")
    v.add_argument("sha")
    n = sub.add_parser("notes")
    n.add_argument("version")
    n.add_argument("--image", default="ghcr.io/seuclkzsd/hsolve")
    n.add_argument("--repo", default="https://github.com/seuclkzsd/hsolve")
    ns = ap.parse_args(argv)
    if ns.cmd == "version":
        print(f"version={version_for(ns.ref_type, ns.ref_name, ns.sha)}")
    else:
        sys.stdout.write(notes(ns.version, ns.image, ns.repo))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

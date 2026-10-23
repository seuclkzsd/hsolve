#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 seuclkzsd and the hsolve contributors
"""Assemble the relocatable binary package hsolve-<version>-linux-x86_64.tar.gz from a build tree.

Run through tools/release/package.sh (it builds the release preset first). Layout of the package:

    bin/hsolve                 command line, RPATH $ORIGIN/../lib
    lib/                       every shared library hsolve needs beyond glibc: MUMPS 5.8.2 (patched,
                               third_party/mumps), OpenBLAS, METIS, SCOTCH, zlib, the GCC runtime;
                               RPATH $ORIGIN where a library has one
    python/hsolve/             the Python module (CPython of the build, numpy >= 1.24), RPATH
                               $ORIGIN/../../lib
    examples/ scripts/ tools/  the example cases, the demo (scripts/demo.sh) and the independent
                               evaluator it uses (tools/eval, tools/case.py)
    licenses/                  MUMPS' licence and the licence files of every bundled conda package,
                               with THIRD_PARTY_BINARIES.md (library -> package, version, licence)
    LICENSE NOTICE THIRD_PARTY_NOTICES README.md BUILD-INFO.txt

Checks before the archive is written (any failure stops the packaging):
  * the build is portable (HSOLVE_NATIVE=OFF and tools/release/check_isa.py passes);
  * no ELF file needs a glibc symbol newer than --glibc-max (default 2.17: CentOS 7 and newer);
  * from a scratch copy, with an empty environment (no conda, no LD_LIBRARY_PATH), bin/hsolve
    resolves every library inside the package and solves examples/waveguide-50ghz.
Packaging the same build twice gives the same bytes: sorted members, owner 0:0, fixed mtime
(SOURCE_DATE_EPOCH, default: the commit time), gzip without a time stamp, and BUILD-INFO.txt
records only what every packaging of the build gives (the smoke solve's time and memory are
printed, not stored).
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# glibc's own libraries: present on every Linux system with glibc, never bundled.
SYSTEM_LIBS = {"linux-vdso.so.1", "ld-linux-x86-64.so.2", "libc.so.6", "libm.so.6", "libdl.so.2", "libpthread.so.0",
               "librt.so.1", "libutil.so.1", "libresolv.so.2", "libnsl.so.1", "libcrypt.so.1", "libmvec.so.1"}
LEGAL = ("LICENSE", "NOTICE", "THIRD_PARTY_NOTICES")
# conda-forge packages of GCC's runtime libraries: their licence texts come from tools/release/licenses.
GCC_RUNTIME = {"libgcc", "libgcc-ng", "libstdcxx", "libstdcxx-ng", "libgfortran5", "libgfortran", "libgfortran-ng",
               "libgomp", "libquadmath"}


def run(cmd: list[str], **kw) -> str:
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw).stdout


def default_version(project_version: str, root: Path = ROOT) -> str:
    """The package version when --version is not given: the tag's for a tagged commit (v1.0.0 ->
    1.0.0; a later commit 1.0.0-3-gabc1234), else "<CMake project version>-dev.<sha7>" like
    tools/release/release_info.py's for an untagged build ("-dirty" appended with local changes);
    the CMake version alone outside a git work tree. cwd, not git -C (git 1.8.3 on CentOS 7)."""
    try:
        return run(["git", "describe", "--tags", "--dirty"], cwd=root).strip().lstrip("v")
    except (OSError, subprocess.CalledProcessError):
        pass  # no tag (or no git)
    try:
        sha = run(["git", "describe", "--always", "--dirty", "--abbrev=7"], cwd=root).strip()
    except (OSError, subprocess.CalledProcessError):
        return project_version
    return f"{project_version}-dev.{sha}"


def cmake_cache(build: Path) -> dict[str, str]:
    out = {}
    for line in (build / "CMakeCache.txt").read_text().splitlines():
        m = re.match(r"^([A-Za-z0-9_]+)(:[A-Z]+)?=(.*)$", line)
        if m:
            out[m.group(1)] = m.group(3)
    return out


def resolved_libs(elf: Path, env: dict[str, str] | None = None) -> dict[str, str | None]:
    """soname -> path as the dynamic loader resolves it (LD_TRACE_LOADED_OBJECTS = ldd)."""
    run_env = dict(env or os.environ)
    run_env.pop("LD_LIBRARY_PATH", None)  # what the RPATHs resolve, not a user's library path
    if elf.suffix == ".so":
        cmd = ["ldd", str(elf)]  # a script run by the shell: tracing its environment would trace the shell
    else:
        cmd = [str(elf)]
        run_env["LD_TRACE_LOADED_OBJECTS"] = "1"
    return parse_ldd(subprocess.run(cmd, env=run_env, capture_output=True, text=True).stdout)


def parse_ldd(text: str) -> dict[str, str | None]:
    """soname -> path (None: not found) from ldd / LD_TRACE_LOADED_OBJECTS output. The vDSO has no
    file and is left out: glibc 2.17 prints it as "linux-vdso.so.1 =>  (0x...)", newer glibc as
    "linux-vdso.so.1 (0x...)"; the loader's own line is "/lib64/ld-linux-x86-64.so.2 (0x...)"."""
    libs: dict[str, str | None] = {}
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^(\S+) => (not found|(\S+) \(0x[0-9a-f]+\))$", line)
        if m:
            libs[m.group(1)] = m.group(3)
            continue
        m = re.match(r"^(/\S+) \(0x[0-9a-f]+\)$", line)
        if m:
            libs[Path(m.group(1)).name] = m.group(1)
    return libs


def rpath_of(elf: Path) -> tuple[str | None, str | None]:
    """(tag, value) of the DT_RPATH / DT_RUNPATH entry, (None, None) without one."""
    for line in run([os.environ.get("READELF") or "readelf", "-d", str(elf)]).splitlines():
        m = re.search(r"\((RPATH|RUNPATH)\)\s+Library r(?:un)?path: \[(.*)\]", line)
        if m:
            return m.group(1), m.group(2)
    return None, None


def set_rpath(elf: Path, rpath: str) -> None:
    """Rewrite the RPATH / RUNPATH in place (CMake's ELF editor: no patchelf needed; the new value
    must not be longer than the old one, which holds for the $ORIGIN forms used here)."""
    script = f'file(RPATH_SET FILE "{elf}" NEW_RPATH "{rpath}")\n'
    with tempfile.NamedTemporaryFile("w", suffix=".cmake", delete=False) as f:
        f.write(script)
    try:
        run(["cmake", "-P", f.name])
    finally:
        os.unlink(f.name)


def strip(elf: Path) -> None:
    """Drop symbol tables and debug sections (the dynamic symbols stay): a smaller download."""
    run([os.environ.get("STRIP") or "strip", "--strip-unneeded", str(elf)])


def glibc_needed(elf: Path) -> tuple[int, ...]:
    best = (0,)
    for v in re.findall(r"GLIBC_([0-9.]+)", run([os.environ.get("OBJDUMP") or "objdump", "-T", str(elf)])):
        best = max(best, tuple(int(x) for x in v.split(".")))
    return best


def conda_owners(prefix: Path) -> dict[str, dict]:
    """lib file name -> conda-meta record of the package that installed it (prefix/conda-meta)."""
    owners: dict[str, dict] = {}
    for meta in sorted((prefix / "conda-meta").glob("*.json")):
        try:
            rec = json.loads(meta.read_text())
        except (OSError, ValueError):
            continue
        for f in rec.get("files", []):
            if f.startswith("lib/") and ".so" in f:
                owners.setdefault(Path(f).name, rec)
    return owners


def copy_tree_files(src: Path, dst: Path, pattern: str = "*") -> None:
    for p in sorted(src.rglob(pattern)):
        if p.is_file() and "__pycache__" not in p.parts:
            q = dst / p.relative_to(src)
            q.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, q)


def stage(build: Path, stage_dir: Path, version: str, allow_missing_legal: bool) -> list[str]:
    """Copy everything into stage_dir; returns notes for BUILD-INFO.txt."""
    notes = []
    (stage_dir / "bin").mkdir(parents=True)
    (stage_dir / "lib").mkdir()
    exe = stage_dir / "bin" / "hsolve"
    shutil.copy2(build / "hsolve", exe)
    module = sorted((build / "python" / "hsolve").glob("_hsolve*.so"))
    if not module:
        raise SystemExit(f"package: no compiled Python module in {build}/python/hsolve (needs pybind11 at configure time)")
    pydir = stage_dir / "python" / "hsolve"
    pydir.mkdir(parents=True)
    for p in sorted((build / "python" / "hsolve").glob("*.py")) + module:
        shutil.copy2(p, pydir / p.name)

    # Libraries: the closure of bin/hsolve and the module as resolved in the build environment.
    conda_prefix = Path(os.environ.get("CONDA_PREFIX", "/nonexistent"))
    owners = conda_owners(conda_prefix)
    bundled: dict[str, Path] = {}
    for elf in [build / "hsolve"] + module:
        for soname, path in resolved_libs(elf).items():
            if soname in SYSTEM_LIBS:
                continue
            if path is None:
                raise SystemExit(f"package: {elf.name} needs {soname}, which the loader does not find")
            bundled.setdefault(soname, Path(path).resolve())
    rows = []
    for soname, src in sorted(bundled.items()):
        dst = stage_dir / "lib" / soname
        shutil.copy2(src, dst)
        os.chmod(dst, 0o755)
        rec = owners.get(src.name) or owners.get(soname)  # the file's own package (libgomp.so.1 -> libomp.so)
        mumps_root = cmake_cache(build).get("HSOLVE_MUMPS_ROOT", "")
        if mumps_root and str(src).startswith(str(Path(mumps_root).resolve())):
            rows.append((soname, "MUMPS 5.8.2 (third_party/mumps, patched: patches/mumps-5.8.2-*.patch)",
                         "CeCILL-C", "licenses/mumps/"))
        elif rec:
            lic_dir = Path(rec.get("extracted_package_dir", "")) / "info" / "licenses"
            target = stage_dir / "licenses" / rec["name"]
            if rec["name"] in GCC_RUNTIME:  # conda-forge ships no licence files with these
                lic_dir = Path(__file__).with_name("licenses") / "gcc-runtime"
                target = stage_dir / "licenses" / "gcc-runtime"
            if lic_dir.is_dir() and not target.exists():
                copy_tree_files(lic_dir, target)
            rows.append((soname, f"conda-forge {rec['name']} {rec['version']} ({rec.get('build', '')})",
                         rec.get("license", "?"), f"licenses/{target.name}/" if target.exists() else "-"))
        else:
            rows.append((soname, str(src), "?", "-"))
        strip(dst)
        kind, _ = rpath_of(dst)
        if kind:
            set_rpath(dst, "$ORIGIN")
    strip(exe)
    set_rpath(exe, "$ORIGIN/../lib")
    for m in module:
        strip(pydir / m.name)
        set_rpath(pydir / m.name, "$ORIGIN/../../lib")
    mumps_lic = stage_dir / "licenses" / "mumps"
    mumps_lic.mkdir(parents=True, exist_ok=True)
    for f in ("LICENSE", "CeCILL-C_V1-en.txt", "README.md"):
        shutil.copy2(ROOT / "third_party" / "mumps" / f, mumps_lic / f)
    table = ["# Third-party shared libraries in lib/", "",
             "| library | from | licence | licence files |", "|---|---|---|---|"]
    table += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows]
    (stage_dir / "licenses" / "THIRD_PARTY_BINARIES.md").write_text("\n".join(table) + "\n")
    unknown = [r[0] for r in rows if r[2] == "?"]
    if unknown:
        raise SystemExit(f"package: no licence information for {unknown}")

    # Examples, demo, evaluator.
    for f in ("manifest.json", "SHA256SUMS", "README.md"):
        if (ROOT / "examples" / f).is_file():
            (stage_dir / "examples").mkdir(exist_ok=True)
            shutil.copy2(ROOT / "examples" / f, stage_dir / "examples" / f)
    for sub in ("cases", "refs"):
        copy_tree_files(ROOT / "examples" / sub, stage_dir / "examples" / sub)
    (stage_dir / "scripts").mkdir()
    for f in ("demo.sh", "demo.py"):
        shutil.copy2(ROOT / "scripts" / f, stage_dir / "scripts" / f)
    (stage_dir / "tools" / "eval").mkdir(parents=True)
    for f in ("__init__.py", "case.py"):
        shutil.copy2(ROOT / "tools" / f, stage_dir / "tools" / f)
    copy_tree_files(ROOT / "tools" / "eval", stage_dir / "tools" / "eval", "*.py")

    missing = [f for f in LEGAL[:2] if not (ROOT / f).is_file()]
    if missing and not allow_missing_legal:
        raise SystemExit(f"package: {missing} missing in the repository (--allow-missing-legal for a test package)")
    for f in LEGAL:
        if (ROOT / f).is_file():
            shutil.copy2(ROOT / f, stage_dir / f)
    notes += [f"missing in this test package: {f}" for f in missing]
    shutil.copy2(Path(__file__).with_name("PACKAGE_README.md"), stage_dir / "README.md")
    return notes


def check_glibc(stage_dir: Path, limit: tuple[int, ...]) -> str:
    worst, worst_file = (0,), ""
    for p in sorted(stage_dir.rglob("*")):
        if p.is_file() and not p.is_symlink() and p.read_bytes()[:4] == b"\x7fELF":
            v = glibc_needed(p)
            if v > worst:
                worst, worst_file = v, str(p.relative_to(stage_dir))
    if worst > limit:
        raise SystemExit(f"package: {worst_file} needs GLIBC_{'.'.join(map(str, worst))} > {'.'.join(map(str, limit))}")
    return f"GLIBC_{'.'.join(map(str, worst))} ({worst_file})"


SMOKE_CASE = "waveguide-50ghz"


def smoke(stage_dir: Path) -> tuple[str, str]:
    """From a copy elsewhere, with an empty environment: every library resolves inside the package,
    and the SMOKE_CASE example solves. Returns (smoke_result() of its report, the solver's summary
    line with time and peak memory)."""
    with tempfile.TemporaryDirectory(prefix="hsolve-package-smoke-") as tmp:
        copy = Path(tmp) / "moved"
        shutil.copytree(stage_dir, copy, symlinks=True)
        bare = {"PATH": "/usr/bin:/bin", "HOME": tmp, "OMP_NUM_THREADS": "2"}
        libs = resolved_libs(copy / "bin" / "hsolve", bare)
        outside = {k: v for k, v in libs.items() if k not in SYSTEM_LIBS and not str(v).startswith(str(copy))}
        if outside:
            raise SystemExit(f"package: bin/hsolve resolves libraries outside the package: {outside}")
        case = copy / "examples" / "cases" / SMOKE_CASE
        out = Path(tmp) / "out"
        proc = subprocess.run([str(copy / "bin" / "hsolve"), "--A", str(case / "A.npz"), "--B", str(case / "B.npz"),
                               "--config", str(case / "config.json"), "--threads", "2", "--out", str(out)],
                              env=bare, capture_output=True, text=True, cwd=tmp)
        if proc.returncode != 0:
            raise SystemExit(f"package: smoke solve failed ({proc.returncode}):\n{proc.stdout}\n{proc.stderr}")
        report = json.loads((out / "report.json").read_text())
        return smoke_result(report), (proc.stdout.splitlines()[0] if proc.stdout else "")


def smoke_result(report: dict) -> str:
    """The smoke solve as BUILD-INFO.txt records it: fields that every run of the build gives the
    same (no time, no memory)."""
    return (f"examples/{SMOKE_CASE}: n={report.get('n')} problem={report.get('problem')} "
            f"eigenvalues={len(report.get('pairs') or [])} success={'yes' if report.get('success') else 'no'}")


def build_info(name: str, commit: str, build: str, glibc_max: str, glibc: str, smoke_line: str,
               notes: list[str]) -> str:
    """BUILD-INFO.txt of the package."""
    return "\n".join([
        f"package: {name}", f"commit: {commit}", f"build: {build}",
        f"needs: x86-64 Linux with glibc >= {glibc_max} (newest symbol used: {glibc})",
        f"smoke test from a moved copy, empty environment: {smoke_line}", *notes]) + "\n"


def write_tar(stage_dir: Path, out: Path, mtime: int) -> None:
    """Reproducible .tar.gz: sorted members, 0:0 owners, fixed mtime, gzip without a time stamp."""
    buf = io.BytesIO()
    base = stage_dir.name
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT) as tar:
        paths = [stage_dir] + sorted(stage_dir.rglob("*"))
        for p in paths:
            info = tar.gettarinfo(str(p), arcname=str(Path(base) / p.relative_to(stage_dir)) if p != stage_dir else base)
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = mtime
            if info.isfile():
                with open(p, "rb") as f:
                    tar.addfile(info, f)
            else:
                tar.addfile(info)
    with open(out, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as gz:
        gz.write(buf.getvalue())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--build", type=Path, default=ROOT / "build" / "release")
    ap.add_argument("--out", type=Path, default=ROOT / "build" / "package")
    ap.add_argument("--version", help="package version (default: the tag's version for a tagged commit, else "
                                      "<CMake project version>-dev.<commit>)")
    ap.add_argument("--glibc-max", default="2.17")
    ap.add_argument("--allow-missing-legal", action="store_true", help="test packages without LICENSE / NOTICE")
    ns = ap.parse_args(argv)
    build = ns.build.resolve()
    cache = cmake_cache(build)
    if cache.get("HSOLVE_NATIVE", "OFF").upper() in ("ON", "1", "TRUE", "YES"):
        raise SystemExit(f"package: {build} is a -march=native build; package the release preset")
    if subprocess.run([sys.executable, str(ROOT / "tools/release/check_isa.py"), str(build)]).returncode != 0:
        raise SystemExit("package: the build is not portable (tools/release/check_isa.py)")
    version = ns.version or default_version(cache.get("CMAKE_PROJECT_VERSION", "0.0.0"))
    name = f"hsolve-{version}-linux-x86_64"
    ns.out.mkdir(parents=True, exist_ok=True)
    stage_dir = ns.out / name
    shutil.rmtree(stage_dir, ignore_errors=True)
    notes = stage(build, stage_dir, version, ns.allow_missing_legal)
    glibc = check_glibc(stage_dir, tuple(int(x) for x in ns.glibc_max.split(".")))
    info = subprocess.run([str(stage_dir / "bin" / "hsolve"), "--version"], capture_output=True,
                          text=True, env={"PATH": "/usr/bin:/bin"}).stdout.strip()
    solved, timing = smoke(stage_dir)
    # HSOLVE_COMMIT / SOURCE_DATE_EPOCH come from the caller where the tree has no .git (container builds).
    try:
        commit = os.environ.get("HSOLVE_COMMIT") or run(["git", "rev-parse", "HEAD"], cwd=ROOT).strip()
        epoch = int(os.environ.get("SOURCE_DATE_EPOCH") or run(["git", "log", "-1", "--format=%ct"], cwd=ROOT))
    except (OSError, subprocess.CalledProcessError, ValueError):
        commit = os.environ.get("HSOLVE_COMMIT") or "unknown"
        epoch = int(os.environ.get("SOURCE_DATE_EPOCH") or 0)
    (stage_dir / "BUILD-INFO.txt").write_text(build_info(name, commit, info, ns.glibc_max, glibc, solved, notes))
    tarball = ns.out / f"{name}.tar.gz"
    write_tar(stage_dir, tarball, epoch)
    digest = hashlib.sha256(tarball.read_bytes()).hexdigest()
    (ns.out / f"{name}.tar.gz.sha256").write_text(f"{digest}  {tarball.name}\n")
    size = tarball.stat().st_size / 2**20
    print(f"{tarball} ({size:.1f} MiB, sha256 {digest})\n  {glibc}; smoke: {solved}\n  smoke run: {timing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

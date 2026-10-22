#!/usr/bin/env python3
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
The archive is reproducible for a given tree: sorted members, owner 0:0, fixed mtime
(SOURCE_DATE_EPOCH, default: the commit time).
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


def run(cmd: list[str], **kw) -> str:
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw).stdout


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
    text = subprocess.run(cmd, env=run_env, capture_output=True, text=True).stdout
    libs: dict[str, str | None] = {}
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^(\S+) => (not found|(\S+) \(0x[0-9a-f]+\))$", line)
        if m:
            libs[m.group(1)] = m.group(3)
        else:
            m = re.match(r"^(\S+) \(0x[0-9a-f]+\)$", line)
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
        rec = owners.get(soname) or owners.get(src.name)
        mumps_root = cmake_cache(build).get("HSOLVE_MUMPS_ROOT", "")
        if mumps_root and str(src).startswith(str(Path(mumps_root).resolve())):
            rows.append((soname, "MUMPS 5.8.2 (third_party/mumps, patched: patches/mumps-5.8.2-*.patch)",
                         "CeCILL-C", "licenses/mumps/"))
        elif rec:
            lic_dir = Path(rec.get("extracted_package_dir", "")) / "info" / "licenses"
            target = stage_dir / "licenses" / rec["name"]
            if lic_dir.is_dir() and not target.exists():
                copy_tree_files(lic_dir, target)
            rows.append((soname, f"{rec['name']} {rec['version']} (conda-forge, {rec.get('url', '')})",
                         rec.get("license", "?"), f"licenses/{rec['name']}/" if target.exists() else "-"))
        else:
            rows.append((soname, str(src), "?", "-"))
        kind, _ = rpath_of(dst)
        if kind:
            set_rpath(dst, "$ORIGIN")
    set_rpath(exe, "$ORIGIN/../lib")
    for m in module:
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


def smoke(stage_dir: Path) -> str:
    """From a copy elsewhere, with an empty environment: every library resolves inside the package,
    and the waveguide example solves."""
    with tempfile.TemporaryDirectory(prefix="hsolve-package-smoke-") as tmp:
        copy = Path(tmp) / "moved"
        shutil.copytree(stage_dir, copy, symlinks=True)
        bare = {"PATH": "/usr/bin:/bin", "HOME": tmp, "OMP_NUM_THREADS": "2"}
        libs = resolved_libs(copy / "bin" / "hsolve", bare)
        outside = {k: v for k, v in libs.items() if k not in SYSTEM_LIBS and not str(v).startswith(str(copy))}
        if outside:
            raise SystemExit(f"package: bin/hsolve resolves libraries outside the package: {outside}")
        case = copy / "examples" / "cases" / "waveguide-50ghz"
        proc = subprocess.run([str(copy / "bin" / "hsolve"), "--A", str(case / "A.npz"), "--B", str(case / "B.npz"),
                               "--config", str(case / "config.json"), "--threads", "2", "--out", str(Path(tmp) / "out")],
                              env=bare, capture_output=True, text=True, cwd=tmp)
        if proc.returncode != 0:
            raise SystemExit(f"package: smoke solve failed ({proc.returncode}):\n{proc.stdout}\n{proc.stderr}")
        return proc.stdout.splitlines()[0] if proc.stdout else ""


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
    ap.add_argument("--version", help="package version (default: git describe, else the CMake project version)")
    ap.add_argument("--glibc-max", default="2.17")
    ap.add_argument("--allow-missing-legal", action="store_true", help="test packages without LICENSE / NOTICE")
    ns = ap.parse_args(argv)
    build = ns.build.resolve()
    cache = cmake_cache(build)
    if cache.get("HSOLVE_NATIVE", "OFF").upper() in ("ON", "1", "TRUE", "YES"):
        raise SystemExit(f"package: {build} is a -march=native build; package the release preset")
    if subprocess.run([sys.executable, str(ROOT / "tools/release/check_isa.py"), str(build)]).returncode != 0:
        raise SystemExit("package: the build is not portable (tools/release/check_isa.py)")
    version = ns.version
    if not version:
        try:
            version = run(["git", "describe", "--tags", "--always", "--dirty"], cwd=ROOT).strip().lstrip("v")
        except (OSError, subprocess.CalledProcessError):
            version = cache.get("CMAKE_PROJECT_VERSION", "0.0.0")
    name = f"hsolve-{version}-linux-x86_64"
    ns.out.mkdir(parents=True, exist_ok=True)
    stage_dir = ns.out / name
    shutil.rmtree(stage_dir, ignore_errors=True)
    notes = stage(build, stage_dir, version, ns.allow_missing_legal)
    glibc = check_glibc(stage_dir, tuple(int(x) for x in ns.glibc_max.split(".")))
    info = subprocess.run([str(stage_dir / "bin" / "hsolve"), "--A", "unused.npz", "--version"], capture_output=True,
                          text=True, env={"PATH": "/usr/bin:/bin"}).stdout.strip()
    solved = smoke(stage_dir)
    try:
        commit = run(["git", "rev-parse", "HEAD"], cwd=ROOT).strip()
        epoch = int(os.environ.get("SOURCE_DATE_EPOCH") or run(["git", "log", "-1", "--format=%ct"], cwd=ROOT))
    except (OSError, subprocess.CalledProcessError, ValueError):
        commit, epoch = "unknown", int(os.environ.get("SOURCE_DATE_EPOCH", "0"))
    (stage_dir / "BUILD-INFO.txt").write_text("\n".join([
        f"package: {name}", f"commit: {commit}", f"build: {info}",
        f"needs: x86-64 Linux with glibc >= {ns.glibc_max} (newest symbol used: {glibc})",
        f"smoke test from a moved copy, empty environment: {solved}", *notes]) + "\n")
    tarball = ns.out / f"{name}.tar.gz"
    write_tar(stage_dir, tarball, epoch)
    digest = hashlib.sha256(tarball.read_bytes()).hexdigest()
    (ns.out / f"{name}.tar.gz.sha256").write_text(f"{digest}  {tarball.name}\n")
    size = tarball.stat().st_size / 2**20
    print(f"{tarball} ({size:.1f} MiB, sha256 {digest})\n  {glibc}; smoke: {solved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

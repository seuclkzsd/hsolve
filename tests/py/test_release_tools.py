# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 seuclkzsd and the hsolve contributors
"""The reproducibility tooling: example files, the demo, the portability check, the package
archive, the CI and release workflows and the container build (examples/, scripts/, tools/release/,
tools/dev/ci.sh, .github/workflows/, Dockerfile; docs/INSTALL.md).

Build directory: $HSOLVE_BUILD_DIR, default build/release; the tests that run hsolve skip without it.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"
BUILD = Path(os.environ.get("HSOLVE_BUILD_DIR", ROOT / "build" / "release"))
HSOLVE = BUILD / "hsolve"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cache_value(name: str) -> str | None:
    cache = BUILD / "CMakeCache.txt"
    if not cache.is_file():
        return None
    for line in cache.read_text().splitlines():
        if line.startswith(name + ":") or line.startswith(name + "="):
            return line.split("=", 1)[1]
    return None


needs_build = pytest.mark.skipif(not HSOLVE.is_file(), reason=f"{HSOLVE} not built (tools/dev/build.sh release)")


# ------------------------------------------------------------------------------- examples

def test_example_files_match_sha256sums_and_manifest():
    sums = dict(reversed(line.split("  ", 1)) for line in (EXAMPLES / "SHA256SUMS").read_text().splitlines())
    for rel, digest in sums.items():
        assert hashlib.sha256((EXAMPLES / rel).read_bytes()).hexdigest() == digest, rel
    manifest = json.loads((EXAMPLES / "manifest.json").read_text())
    listed = {f for e in manifest["examples"] for f in e["files"]}
    on_disk = {str(p.relative_to(EXAMPLES)) for sub in ("cases", "refs") for p in (EXAMPLES / sub).rglob("*")
               if p.is_file()}
    assert listed == set(sums) == on_disk


def test_example_configs_are_the_manifest_targets_and_references_are_separate():
    manifest = json.loads((EXAMPLES / "manifest.json").read_text())
    assert len(manifest["examples"]) == 6
    for e in manifest["examples"]:
        case = EXAMPLES / "cases" / e["name"]
        config = json.loads((case / "config.json").read_text())
        assert config["target"] == e["target"]
        assert config["tol"] == 1e-10
        assert (EXAMPLES / "refs" / e["name"] / "eigenvalues.npy").is_file()
        assert not any(p.suffix == ".npy" for p in case.iterdir()), "reference data inside a case directory"
        if e["target"]["mode"] == "interval":
            assert e["target"]["lower"] < e["target"]["upper"]


# ------------------------------------------------------------------------------- package archive

def test_package_archive_is_reproducible_and_owned_by_root(tmp_path):
    pkg = load("hsolve_package", ROOT / "tools" / "release" / "package.py")
    stage = tmp_path / "hsolve-0.0.0-linux-x86_64"
    (stage / "bin").mkdir(parents=True)
    (stage / "bin" / "tool").write_text("#!/bin/sh\necho hi\n")
    os.chmod(stage / "bin" / "tool", 0o755)
    (stage / "README.md").write_text("x\n")
    a, b = tmp_path / "a.tar.gz", tmp_path / "b.tar.gz"
    pkg.write_tar(stage, a, 1700000000)
    os.utime(stage / "README.md", (1, 1))  # file times must not matter
    pkg.write_tar(stage, b, 1700000000)
    assert a.read_bytes() == b.read_bytes()
    with tarfile.open(a) as tar:
        members = tar.getmembers()
    assert [m.name for m in members] == ["hsolve-0.0.0-linux-x86_64", "hsolve-0.0.0-linux-x86_64/README.md",
                                         "hsolve-0.0.0-linux-x86_64/bin", "hsolve-0.0.0-linux-x86_64/bin/tool"]
    assert all(m.uid == 0 and m.gid == 0 and m.mtime == 1700000000 for m in members)
    assert members[-1].mode & 0o111


def test_build_info_records_the_smoke_solve_without_time_or_memory():
    pkg = load("hsolve_package", ROOT / "tools" / "release" / "package.py")
    report = {"n": 289, "problem": "generalized_indefinite", "pairs": [{}] * 18, "success": True,
              "time_total_s": 0.028, "peak_rss_bytes": 75_000_000}
    line = pkg.smoke_result(report)
    assert line == "examples/waveguide-50ghz: n=289 problem=generalized_indefinite eigenvalues=18 success=yes"
    text = pkg.build_info("hsolve-1.0.0-linux-x86_64", "0" * 40, "hsolve 1.0.0", "2.17", "GLIBC_2.17 (bin/hsolve)",
                          line, [])
    assert "time" not in text and "rss" not in text


@needs_build
@pytest.mark.skipif(not all(shutil.which(t) for t in ("cmake", "strip", "readelf", "ldd",
                                                      os.environ.get("OBJDUMP") or "objdump")),
                    reason="needs cmake, binutils and ldd")
@pytest.mark.skipif(not os.environ.get("CONDA_PREFIX"), reason="needs the build environment (licence records)")
def test_packaging_a_build_twice_gives_the_same_archive(tmp_path):
    if (cache_value("HSOLVE_NATIVE") or "OFF").upper() in ("ON", "1", "TRUE", "YES"):
        pytest.skip("a -march=native build is not packaged")
    archives = []
    for run in ("a", "b"):
        proc = subprocess.run([sys.executable, str(ROOT / "tools" / "release" / "package.py"), "--build", str(BUILD),
                               "--out", str(tmp_path / run), "--version", "0.0.0-test", "--allow-missing-legal"],
                              capture_output=True, text=True, timeout=900)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        archives.append(tmp_path / run / "hsolve-0.0.0-test-linux-x86_64.tar.gz")
    assert archives[0].read_bytes() == archives[1].read_bytes()
    with tarfile.open(archives[0]) as tar:
        info = tar.extractfile("hsolve-0.0.0-test-linux-x86_64/BUILD-INFO.txt").read().decode()
    assert "examples/waveguide-50ghz: n=289 problem=generalized_indefinite" in info
    assert "success=yes" in info and "time" not in info


@pytest.mark.skipif(shutil.which("ldd") is None, reason="needs ldd")
def test_package_resolves_libraries_like_the_loader():
    pkg = load("hsolve_package", ROOT / "tools" / "release" / "package.py")
    libs = pkg.resolved_libs(Path(sys.executable).resolve())
    assert libs, "no libraries resolved for the Python interpreter"
    assert all(v is None or Path(v).is_absolute() for v in libs.values())


# ------------------------------------------------------------------------------- built hsolve

@needs_build
@pytest.mark.skipif(shutil.which(os.environ.get("OBJDUMP") or "objdump") is None, reason="needs objdump")
def test_portable_build_has_no_avx_outside_the_dispatch():
    proc = subprocess.run([sys.executable, str(ROOT / "tools" / "release" / "check_isa.py"), str(BUILD)],
                          capture_output=True, text=True)
    native = (cache_value("HSOLVE_NATIVE") or "OFF").upper() in ("ON", "1", "TRUE", "YES")
    assert proc.returncode == (1 if native else 0), proc.stdout + proc.stderr
    assert "dispatched SIMD function" in proc.stdout


@needs_build
def test_demo_quick_solves_and_checks_independently(tmp_path):
    out = tmp_path / "demo"
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "demo.py"), "--hsolve", str(HSOLVE), "--quick",
                           "--threads", "2", "--out", str(out)], capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    summary = json.loads((out / "summary.json").read_text())
    assert summary["success"]
    assert [c["case"] for c in summary["cases"]] == ["waveguide-50ghz", "near-singular-shift"]
    for c in summary["cases"]:
        assert c["evaluation"]["verdict"] == "pass"
        assert c["evaluation"]["completeness"] == "complete"
        assert (out / c["case"] / "evaluation.json").is_file()


@needs_build
def test_demo_sh_without_numpy_runs_the_solver_only(tmp_path):
    env = dict(os.environ, PYTHON=str(tmp_path / "no-such-python"))
    proc = subprocess.run([str(ROOT / "scripts" / "demo.sh"), "--hsolve", str(HSOLVE), "--quick", "--threads", "2",
                           "--out", str(tmp_path / "out")], capture_output=True, text=True, env=env, timeout=600)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "no independent evaluation" in proc.stderr
    assert proc.stdout.count("success=yes") == 2


# ------------------------------------------------------------------------------- CI, release, container

WORKFLOWS = ROOT / ".github" / "workflows"


def test_workflow_actions_are_pinned_to_exact_versions():
    """A commit SHA with its release tag as a comment (or at least an exact vX.Y.Z tag)."""
    uses = [(f.name, m.group(1).strip()) for f in sorted(WORKFLOWS.glob("*.yml"))
            for m in re.finditer(r"^\s*(?:-\s*)?uses:\s*(.+)$", f.read_text(), re.M)]
    assert uses
    action = r"[\w.-]+/[\w.-]+(/[\w./-]+)?"
    for name, ref in uses:
        assert re.fullmatch(rf"{action}@([0-9a-f]{{40}} # v\d+\.\d+\.\d+|v\d+\.\d+\.\d+)", ref), \
            f"{name}: '{ref}' is neither a commit SHA with its tag nor an exact tag"


def test_ci_workflow_runs_exactly_the_steps_of_ci_sh():
    text = (ROOT / "tools" / "dev" / "ci.sh").read_text()
    known = set(re.search(r"^all=\(([^)]*)\)", text, re.M).group(1).split())
    used = {s for line in re.findall(r"tools/dev/ci\.sh ([a-z0-9 -]+)$", (WORKFLOWS / "ci.yml").read_text(), re.M)
            for s in line.split()}
    assert used == known, f"ci.yml runs {sorted(used)}, ci.sh has {sorted(known)}"


def test_docker_context_holds_what_the_image_build_reads():
    rules = [line.strip() for line in (ROOT / ".dockerignore").read_text().splitlines()
             if line.strip() and not line.startswith("#")]
    assert rules[0] == "*", "the context is an allow-list"
    allowed = {r[1:] for r in rules if r.startswith("!")}
    copied = re.findall(r"^COPY (?!--from)(?:--\S+ )*(\S+) ", (ROOT / "Dockerfile").read_text(), re.M)
    # Read by the build stage: the COPY sources, the build scripts and tools/release/package.py's inputs.
    needed = [c for c in copied if c != "."] + [
        "CMakeLists.txt", "CMakePresets.json", "LICENSE", "NOTICE", "THIRD_PARTY_NOTICES", "apps", "include",
        "python", "src", "patches", "env/activate.sh", "third_party/mumps/MUMPS_5.8.2.tar.gz",
        "examples/manifest.json", "scripts/demo.sh", "tools/eval/evaluate.py", "tools/release/package.py"]
    for path in needed:
        assert path.split("/")[0] in allowed, f"{path} is outside the Docker build context"
    assert os.access(ROOT / "scripts" / "docker-entrypoint.sh", os.X_OK)


def test_install_guide_quotes_the_generated_tier_tables():
    """docs/INSTALL.md §5 holds results/resource-tiers/tiers-summary.md verbatim (regenerate both together)."""
    generated = (ROOT / "results" / "resource-tiers" / "tiers-summary.md").read_text()
    assert generated.strip() in (ROOT / "docs" / "INSTALL.md").read_text()


def test_release_version_must_match_cmake_and_a_dated_changelog_section(tmp_path):
    info = load("hsolve_release_info", ROOT / "tools" / "release" / "release_info.py")
    (tmp_path / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.20)\n"
                                             "project(hsolve VERSION 1.2.3 LANGUAGES C CXX)\n")
    assert info.version_for("branch", "main", "0123456789abcdef", tmp_path) == "1.2.3-dev.0123456"
    assert info.version_for("tag", "v1.2.3", "0" * 40, tmp_path) == "1.2.3"  # no CHANGELOG.md: no check
    assert info.version_for("tag", "v1.2.3-rc1", "0" * 40, tmp_path) == "1.2.3-rc1"
    for bad in ("v1.2.4", "1.2.3", "v1.2"):
        with pytest.raises(SystemExit):
            info.version_for("tag", bad, "0" * 40, tmp_path)
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# 更新日志\n\n## [未发布]\n\n## [1.2.3] - {{TODO:日期}}\n\n- a\n\n## [1.2.2] - 2026-01-01\n")
    with pytest.raises(SystemExit):
        info.version_for("tag", "v1.2.3", "0" * 40, tmp_path)
    changelog.write_text("# 更新日志\n\n## [1.2.3] - 2026-11-01\n\n### 新增\n\n- 新功能\n\n## [1.2.2] - 2026-01-01\n\n- old\n")
    assert info.version_for("tag", "v1.2.3", "0" * 40, tmp_path) == "1.2.3"
    notes = info.notes("1.2.3", "ghcr.io/x/hsolve", "https://example.org/hsolve", tmp_path)
    assert notes.startswith("### 新增\n\n- 新功能\n")
    assert "old" not in notes
    assert "docker run --rm ghcr.io/x/hsolve:1.2.3 demo" in notes
    assert "releases/download/v1.2.3/hsolve-1.2.3-linux-x86_64.tar.gz" in notes


@pytest.mark.skipif(shutil.which("sha256sum") is None, reason="needs sha256sum")
def test_download_check_runs_as_written_with_old_coreutils(tmp_path):
    """The checksum command of the release notes and docs/INSTALL.md §2, in a directory with the
    downloaded package and SHA256SUMS as release.yml writes it; no option newer than coreutils 8.22
    (CentOS 7: no --ignore-missing, so SHA256SUMS lists the package alone)."""
    info = load("hsolve_release_info", ROOT / "tools" / "release" / "release_info.py")
    notes = info.notes("1.2.3", "ghcr.io/x/hsolve", "https://example.org/hsolve", tmp_path)
    check = [line for line in notes.splitlines() if line.startswith("sha256sum")]
    assert check == ["sha256sum -c SHA256SUMS"]
    assert f"`{check[0]}`" in (ROOT / "docs" / "INSTALL.md").read_text()
    writes = re.findall(r"^\s*sha256sum (.+) > SHA256SUMS$", (WORKFLOWS / "release.yml").read_text(), re.M)
    assert writes == ['"hsolve-${{ steps.version.outputs.version }}-linux-x86_64.tar.gz"']
    tarball = tmp_path / "hsolve-1.2.3-linux-x86_64.tar.gz"
    tarball.write_bytes(b"package bytes")
    sums = subprocess.run(["sha256sum", tarball.name], cwd=tmp_path, capture_output=True, text=True, check=True)
    (tmp_path / "SHA256SUMS").write_text(sums.stdout)
    assert subprocess.run(check[0].split(), cwd=tmp_path, capture_output=True).returncode == 0
    tarball.write_bytes(b"tampered bytes")
    assert subprocess.run(check[0].split(), cwd=tmp_path, capture_output=True).returncode != 0

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


@pytest.mark.skipif(shutil.which("ldd") is None, reason="needs ldd")
def test_package_resolves_libraries_like_the_loader():
    pkg = load("hsolve_package", ROOT / "tools" / "release" / "package.py")
    libs = pkg.resolved_libs(Path(sys.executable).resolve())
    assert libs, "no libraries resolved for the Python interpreter"
    assert all(v is None or Path(v).is_absolute() for v in libs.values())


# ------------------------------------------------------------------------------- built hsolve

needs_build = pytest.mark.skipif(not HSOLVE.is_file(), reason=f"{HSOLVE} not built (tools/dev/build.sh release)")


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
    uses = [(f.name, m.group(1)) for f in sorted(WORKFLOWS.glob("*.yml"))
            for m in re.finditer(r"^\s*(?:-\s*)?uses:\s*(\S+)", f.read_text(), re.M)]
    assert uses
    for name, ref in uses:
        assert re.fullmatch(r"[\w.-]+/[\w.-]+(/[\w./-]+)?@v\d+\.\d+\.\d+", ref), f"{name}: {ref} is not an exact tag"


def test_ci_workflow_runs_exactly_the_steps_of_ci_sh():
    text = (ROOT / "tools" / "dev" / "ci.sh").read_text()
    known = set(re.search(r"^all=\(([^)]*)\)", text, re.M).group(1).split())
    used = {s for line in re.findall(r"tools/dev/ci\.sh ([a-z ]+)$", (WORKFLOWS / "ci.yml").read_text(), re.M)
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

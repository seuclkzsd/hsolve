# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 seuclkzsd and the hsolve contributors
"""Command-line features of hsolve (docs/FORMATS.md §2, §3, §5): the data-protection mode --secure
(no paths in report and log, inputs by SHA-256, files 0600), the eigenvector subspace-angle bound in
report.json, the structure-candidates switch, and the refusal of pickled numpy input.

The executable and the Python package come from the build tree: $HSOLVE_BUILD_DIR, default
build/release (tools/dev/build.sh release). Small problems only.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import scipy.sparse as sp

_ROOT = Path(__file__).resolve().parents[2]
_BUILD = Path(os.environ.get("HSOLVE_BUILD_DIR", _ROOT / "build" / "release"))
_EXE = _BUILD / "hsolve"
_PY_DIR = Path(os.environ.get("HSOLVE_PYTHON_DIR", _BUILD / "python"))

needs_exe = pytest.mark.skipif(not _EXE.is_file(), reason=f"hsolve not built in {_BUILD} (tools/dev/build.sh)")


def _lap2d(n: int) -> sp.csr_matrix:
    e = np.ones(n)
    t = sp.diags([-e[:-1], 2 * e, -e[:-1]], [-1, 0, 1], format="csr")
    return sp.kronsum(t, t, format="csr")


@pytest.fixture()
def case(tmp_path):
    d = tmp_path / "private-case-dir"
    d.mkdir()
    sp.save_npz(d / "A.npz", _lap2d(7))
    sp.save_npz(d / "B.npz", sp.diags(np.linspace(1.0, 2.0, 49), format="csr"))
    (d / "config.json").write_text(json.dumps({"target": {"mode": "nearest", "sigma": 0.5, "k": 3},
                                               "threads": 2, "memory_budget_gb": 1}))
    return d


def _run(*args: str, check: int | None = 0) -> subprocess.CompletedProcess:
    env = dict(os.environ, OMP_NUM_THREADS="2")
    r = subprocess.run([str(_EXE), *args], capture_output=True, text=True, env=env, timeout=300)
    if check is not None:
        assert r.returncode == check, r.stdout + r.stderr
    return r


def _mode(p: Path) -> int:
    return stat.S_IMODE(p.stat().st_mode)


def _strings(doc) -> list[str]:
    """Every string value of a JSON document, recursively."""
    if isinstance(doc, str):
        return [doc]
    if isinstance(doc, dict):
        doc = list(doc.values())
    if isinstance(doc, list):
        return [s for v in doc for s in _strings(v)]
    return []


def _assert_no_paths(doc, where: str) -> None:
    for s in _strings(doc):
        assert not s.startswith("/") and "/proc/" not in s and "/sys/" not in s, f"{where}: {s!r}"


@needs_exe
def test_secure_mode_records_inputs_by_content_and_writes_private_files(case, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    stale = out / "eigenvalues.npy"
    stale.write_bytes(b"old")
    stale.chmod(0o644)  # an existing file is replaced, not truncated with its old mode
    log = tmp_path / "run.jsonl"
    _run("--A", str(case / "A.npz"), "--B", str(case / "B.npz"), "--config", str(case / "config.json"),
         "--out", str(out), "--log", str(log), "--secure", "-q")
    report_text = (out / "report.json").read_text()
    log_text = log.read_text()
    for text in (report_text, log_text):
        assert "private-case-dir" not in text and str(tmp_path) not in text
    report = json.loads(report_text)
    # No file system path at all: the memory limits keep only the names of the files they were
    # read from (without --secure, MemTotal's detail is /proc/meminfo).
    _assert_no_paths(report, "report.json")
    for line in log_text.splitlines():
        _assert_no_paths(json.loads(line), "log")
    assert any(lim["name"] == "mem_total" and lim["detail"] == "meminfo" for lim in report["memory"]["limits"])
    for name, path in (("A", case / "A.npz"), ("B", case / "B.npz")):
        rec = report["input"][name]
        assert rec["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert rec["shape"] == [49, 49] and rec["dtype"] == "float64" and rec["format"] == "npz-csr"
    assert report["input"]["A"]["nnz"] == _lap2d(7).nnz
    events = [json.loads(line) for line in log_text.splitlines()]
    start = next(e for e in events if e["event"] == "start")
    assert start["secure"] is True and "A" not in start and "out" not in start
    assert next(e for e in events if e["event"] == "input")["A_sha256"] == report["input"]["A"]["sha256"]
    for f in [*out.iterdir(), log]:
        assert _mode(f) == 0o600, f
    # The same in config.json, without the flag.
    cfg = json.loads((case / "config.json").read_text())
    cfg["secure"] = True
    (case / "secure.json").write_text(json.dumps(cfg))
    out2 = tmp_path / "out2"
    _run("--A", str(case / "A.npz"), "--config", str(case / "secure.json"), "--out", str(out2), "-q")
    assert "input" in json.loads((out2 / "report.json").read_text())
    assert _mode(out2) == 0o700 and all(_mode(f) == 0o600 for f in out2.iterdir())


@needs_exe
def test_without_secure_the_report_has_no_input_record(case, tmp_path):
    out = tmp_path / "out"
    _run("--A", str(case / "A.npz"), "--config", str(case / "config.json"), "--out", str(out), "-q")
    report = json.loads((out / "report.json").read_text())
    assert "input" not in report
    assert any(lim["name"] == "mem_total" and lim["detail"] == "/proc/meminfo" for lim in report["memory"]["limits"])
    assert "private-case-dir" not in json.dumps(report)  # the report never carried paths


@needs_exe
def test_report_carries_the_subspace_bound(case, tmp_path):
    out = tmp_path / "out"
    r = _run("--A", str(case / "A.npz"), "--B", str(case / "B.npz"), "--config", str(case / "config.json"),
             "--out", str(out))
    assert "eigenvector subspace angles: sin <=" in r.stdout
    report = json.loads((out / "report.json").read_text())
    sub = report["subspace"]
    assert sub["performed"] and sub["rigorous"] and sub["residual_norm"] == "b_inverse_diagonal"
    assert 0.0 <= sub["max_sin_bound"] < 1e-6
    assert all(p["subspace_sin_bound"] <= sub["max_sin_bound"] for p in report["pairs"])
    assert sorted(j for g in sub["groups"] for j in g["pairs"]) == list(range(len(report["pairs"])))
    out_off = tmp_path / "off"
    _run("--A", str(case / "A.npz"), "--config", str(case / "config.json"), "--out", str(out_off),
         "--subspace-bound", "off", "-q")
    sub = json.loads((out_off / "report.json").read_text())["subspace"]
    assert not sub["performed"] and sub["max_sin_bound"] is None and sub["note"] == "disabled by configuration"
    out_on = tmp_path / "on"
    _run("--A", str(case / "A.npz"), "--B", str(case / "B.npz"), "--config", str(case / "config.json"),
         "--out", str(out_on), "--subspace-bound", "on", "-q")
    sub = json.loads((out_on / "report.json").read_text())["subspace"]
    assert sub["performed"] and sub["rigorous"] and sub["b_min_source"] == "diagonal"


@needs_exe
def test_structure_candidates_switch(case, tmp_path):
    for value in ("off", "auto"):
        _run("--A", str(case / "A.npz"), "--config", str(case / "config.json"), "--out", str(tmp_path / value),
             "--structure-candidates", value, "-q")
        report = json.loads((tmp_path / value / "report.json").read_text())
        assert report["candidate_source"] == "iterative"  # a 2-D Laplacian is no curl-curl operator
    _run("--A", str(case / "A.npz"), "--out", str(tmp_path / "on"), "--structure-candidates", "on", check=2)


@needs_exe
def test_version_needs_no_input_but_a_solve_does(tmp_path):
    info = _run("--version").stdout
    assert info.startswith("hsolve ") and "flags: " in info
    assert _run("--A", "unused.npz", "--version").stdout == info  # --version answers before reading
    r = _run("--out", str(tmp_path / "out"), check=2)
    assert "--A is required" in r.stderr and not (tmp_path / "out").exists()


def _pickle_npy(path: Path, marker: Path) -> None:
    """A .npy holding an object array whose pickle would create `marker` when unpickled."""

    class Payload:
        def __reduce__(self):
            return (os.system, (f"touch {marker}",))

    arr = np.empty((2, 2), dtype=object)
    arr[0, 0] = Payload()
    np.save(path, arr, allow_pickle=True)


@needs_exe
def test_pickled_input_is_refused_by_the_command_line(tmp_path):
    marker = tmp_path / "pickle-ran"
    _pickle_npy(tmp_path / "A.npy", marker)
    r = _run("--A", str(tmp_path / "A.npy"), "--out", str(tmp_path / "out"), check=2)
    assert "unsupported" in r.stderr and not marker.exists()


def test_pickled_input_is_refused_by_the_python_package(tmp_path):
    if not (_PY_DIR / "hsolve" / "__init__.py").is_file():
        pytest.skip(f"hsolve Python package not built in {_PY_DIR}")
    sys.path.insert(0, str(_PY_DIR))
    try:
        import hsolve
    finally:
        sys.path.remove(str(_PY_DIR))
    marker = tmp_path / "pickle-ran"
    _pickle_npy(tmp_path / "A.npy", marker)
    with pytest.raises(hsolve.UnsupportedError):
        hsolve.load_matrix(tmp_path / "A.npy")
    with pytest.raises(hsolve.UnsupportedError):
        hsolve.solve(tmp_path / "A.npy", sigma=0.0, k=1)
    # The repository's case reader (tools/case.py, numpy's np.load / scipy's load_npz) never unpickles.
    with pytest.raises(ValueError):
        np.load(tmp_path / "A.npy")
    assert not marker.exists()
    cfg = hsolve.default_config()
    assert cfg["structure_candidates"] == "off" and cfg["subspace_bound"] == "auto" and cfg["secure"] is False

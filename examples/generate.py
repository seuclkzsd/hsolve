#!/usr/bin/env python3
"""Generate the example cases of examples/ with the repository's generators (tools/gen).

Every example is a case directory in the layout of tools/case.py (docs/FORMATS.md):
    examples/cases/<name>/{A.npz, [B.npz], meta.json, config.json}
    examples/refs/<name>/{eigenvalues.npy, [eigenvectors.npy], ref.json}
config.json is the target the demo solves (scripts/demo.sh); refs/ holds the reference spectrum
that only the independent evaluator (tools/eval) reads - never the solver.

The generators are deterministic (fixed seeds, no time stamps; numpy's .npz entries carry a fixed
date), so the committed files are reproducible:
    python3 examples/generate.py            regenerate examples/ in place and rewrite SHA256SUMS
    python3 examples/generate.py --check    regenerate into a temporary directory and compare with
                                            SHA256SUMS (exit 1 on any difference)
    cd examples && sha256sum -c SHA256SUMS  integrity of the committed files (no Python needed)
The bytes depend on the numpy / scipy versions of env/environment.yml; --check names any file
that differs (for another environment, compare the matrices numerically instead).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from tools import case  # noqa: E402
from tools.gen import synthetic, waveguide, yee  # noqa: E402

SUMS = "SHA256SUMS"
MANIFEST = "manifest.json"


@dataclass(frozen=True)
class Example:
    name: str
    title: str          # one line for the demo table and the README
    scenario: str       # what it demonstrates
    make: Callable[[Path], dict[str, Any]]  # writes the case under root, returns its config


def _gap_point(levels: np.ndarray, below: float, frac: float = 0.5) -> float:
    """A point in the spectral gap that follows the largest level <= below (frac of the gap)."""
    i = int(np.searchsorted(levels, below, side="right")) - 1
    return float(levels[i] + frac * (levels[i + 1] - levels[i]))


def _write_config(root: Path, name: str, config: dict[str, Any]) -> dict[str, Any]:
    path = root / "cases" / name / "config.json"
    path.write_text(json.dumps(config, indent=2) + "\n")
    return config


def _yee_levels(grid: yee.YeeGrid) -> np.ndarray:
    return synthetic.distinct_levels(yee.exact_eigenvalues(grid))[0]


def make_pec_cavity(root: Path) -> dict[str, Any]:
    """PEC cube, standard curl-curl: the lowest resonances above the gradient null space, whose
    TE/TM pairs and the cube's symmetry make 3- and 6-fold eigenvalues."""
    name = "pec-cavity-multiplicity"
    yee.make_homogeneous_case(name, yee.YeeGrid((16, 16, 16)), "standard", root)
    return json.loads((root / "cases" / name / "config.json").read_text())


def make_near_singular(root: Path) -> dict[str, Any]:
    """Prescribed simple spectrum in [-1, 1]; the shift lies within 1e-12 (relative) of an
    eigenvalue, so K = A - sigma I is singular to working precision."""
    name = "near-singular-shift"
    synthetic.make_prescribed_case(name, "near-singular", 2000, False, 120, root)
    return json.loads((root / "cases" / name / "config.json").read_text())


def make_low_frequency(root: Path) -> dict[str, Any]:
    """PEC box, generalized form (B diagonal HPD): every resonance in (0, X] - the window starts
    right above the 3135-fold zero eigenvalue of the gradient fields (sigma ~ 0 from above)."""
    name = "lowfreq-null-space"
    grid = yee.YeeGrid((20, 16, 12), (1.0, 0.7, 0.45))
    yee.make_homogeneous_case(name, grid, "generalized", root)
    lev = _yee_levels(grid)
    lower = 1e-6 * float(lev[1])  # inside the gap between 0 and the first resonance
    upper = _gap_point(lev, lev[6])  # after the 6th nonzero level
    return _write_config(root, name, {"target": {"mode": "interval", "lower": lower, "upper": upper},
                                      "tol": 1e-10})


def make_waveguide(root: Path) -> dict[str, Any]:
    """10 mm square PEC air waveguide at 50 GHz, Lee-Sun-Cendes mixed elements (n = 289): every
    propagating mode, lambda = -beta^2 < 0, of a pencil whose B is indefinite (GHIEP)."""
    name = "waveguide-50ghz"
    spec = waveguide.CaseSpec(family="waveguide", a=10.0, b=10.0, freq_ghz=50.0, nx=9)
    waveguide.write(waveguide.generate(spec, name), root)
    return json.loads((root / "cases" / name / "config.json").read_text())


def make_bloch(root: Path) -> dict[str, Any]:
    """Bloch-periodic cell at a generic wavevector: complex Hermitian curl-curl (photonic band
    structure), lowest bands above the null space."""
    name = "bloch-cell-complex"
    k = (0.3 * np.pi, 0.2 * np.pi, 0.1 * np.pi)
    grid = yee.YeeGrid((16, 15, 14), (1.0, 0.9, 0.8), "bloch", k)
    yee.make_homogeneous_case(name, grid, "standard", root)
    return json.loads((root / "cases" / name / "config.json").read_text())


def make_interval(root: Path) -> dict[str, Any]:
    """PEC cube, standard form: every eigenvalue of a band in the middle of the spectrum - a
    window cut into slices, each solved with its own shift and checked by inertia counts."""
    name = "interval-slicing"
    grid = yee.YeeGrid((12, 12, 12))
    yee.make_homogeneous_case(name, grid, "standard", root)
    lev = _yee_levels(grid)
    w = yee.exact_eigenvalues(grid)
    lower = _gap_point(lev, float(np.quantile(w[w > 0], 0.40)))
    upper = _gap_point(lev, float(np.quantile(w[w > 0], 0.43)))
    return _write_config(root, name, {"target": {"mode": "interval", "lower": lower, "upper": upper},
                                      "tol": 1e-10})


EXAMPLES = [
    Example("pec-cavity-multiplicity", "PEC cube cavity, multiple resonances", "multiplicity", make_pec_cavity),
    Example("near-singular-shift", "shift within 1e-12 of an eigenvalue", "near-singular", make_near_singular),
    Example("lowfreq-null-space", "resonances just above a 3135-fold null space", "zero-cluster",
            make_low_frequency),
    Example("waveguide-50ghz", "square waveguide 50 GHz, indefinite B", "indefinite-B", make_waveguide),
    Example("bloch-cell-complex", "Bloch cell, complex Hermitian", "complex-hermitian", make_bloch),
    Example("interval-slicing", "all eigenvalues of a mid-spectrum band", "clustered", make_interval),
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate(root: Path) -> dict[str, Any]:
    """Write every example under root (cases/, refs/) and return the manifest."""
    entries = []
    for ex in EXAMPLES:
        for sub in ("cases", "refs"):
            shutil.rmtree(root / sub / ex.name, ignore_errors=True)
        config = ex.make(root)
        meta = json.loads((root / "cases" / ex.name / "meta.json").read_text())
        ref = json.loads((root / "refs" / ex.name / "ref.json").read_text())
        files = sorted(str(p.relative_to(root)) for sub in ("cases", "refs")
                       for p in (root / sub / ex.name).iterdir())
        entries.append({"name": ex.name, "title": ex.title, "scenario": ex.scenario,
                        "problem": meta["problem"], "n": meta["n"], "dtype": meta["dtype"],
                        "target": config["target"], "reference": ref["kind"], "files": files})
    return {"generator": "examples/generate.py", "layout": "tools/case.py (docs/FORMATS.md)",
            "examples": entries}


def write_sums(root: Path, manifest: dict[str, Any]) -> None:
    lines = [f"{_sha256(root / f)}  {f}" for e in manifest["examples"] for f in e["files"]]
    (root / SUMS).write_text("\n".join(lines) + "\n")
    (root / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n")


def check(root: Path) -> int:
    want = dict(reversed(line.split("  ", 1)) for line in (root / SUMS).read_text().splitlines())
    bad = 0
    with tempfile.TemporaryDirectory(prefix="hsolve-examples-") as tmp:
        manifest = generate(Path(tmp))
        got = {f: _sha256(Path(tmp) / f) for e in manifest["examples"] for f in e["files"]}
    for f in sorted(set(want) | set(got)):
        if want.get(f) != got.get(f):
            bad += 1
            print(f"differs: {f} (committed {want.get(f, 'missing')[:12]}, regenerated {got.get(f, 'missing')[:12]})")
    print(f"{len(got)} files regenerated, {bad} differ from {SUMS}")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="regenerate into a temporary directory and compare")
    ap.add_argument("--root", type=Path, default=HERE, help="output root (default: examples/)")
    ns = ap.parse_args(argv)
    if ns.check:
        return check(ns.root)
    manifest = generate(ns.root)
    write_sums(ns.root, manifest)
    for e in manifest["examples"]:
        print(f"{e['name']:<26} n={e['n']:<6} {e['problem']:<5} {e['target']['mode']:<9} {e['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

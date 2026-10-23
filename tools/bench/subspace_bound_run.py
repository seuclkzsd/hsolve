#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 seuclkzsd and the hsolve contributors
"""Eigenvector subspace-angle bounds on the data cases: the bound against the measured angle, and its cost.

Every case is solved with its default configuration (data/cases/<case>/config.json) by
build/<preset>/hsolve with --subspace-bound auto, off and on, interleaved (the order rotates per
repetition); each report's summary is kept. From every auto run of a case, every group of the
report's `subspace` section is checked against a reference of the exact spectral subspace of the
group's interval (tools/bench/subspace_reference.py): the exact eigenvectors of the synthetic
families (recomputed from the generator), else the stored reference eigenvectors of the case. The
measured ||sin Theta||_F (B inner product) is recorded next to the bound, with the reference's own
backward error and, where the case's complete spectrum is known, the true gap of the group. Each
batch also records the guard's limits as the run sees them (HSOLVE_MEMORY_LIMIT_GB, the
measurement slot) and every case's target and tol.

Run on a cluster node in the measurement slot (docs/DESIGN.md §6), one batch of cases per call:
  python3 tools/run/guard.py --exclusive --timeout 2700 --mem-gb 32 -- \
      python3 tools/bench/subspace_bound_run.py --out results/subspace_bound.json [--append] [--reps 3] [CASE ...]
--append adds the batch to an existing file (same commit and preset required). The tables of
results/subspace_bound.md are made by tools/bench/subspace_bound_table.py from that file.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import scipy.sparse as sp

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.bench import subspace_reference as sref  # noqa: E402

DEFAULT_CASES = [
    # HEP with exact eigenvectors (generator formula): multiplicities, clusters, near-singular shift
    "syn-multiplicity-real-1e4", "syn-multiplicity-complex-1e4", "syn-lap3d-22", "syn-lap3d-aniso-1e5",
    "syn-zero-cluster-real-1e5", "syn-near-singular-complex-1e5", "syn-wide-range-real-1e4", "syn-mem27-46",
    # GHEP with exact eigenvectors: general sparse HPD B (cond(B) <= 9e3)
    "syn-ghep-multiplicity-real-1e4", "syn-ghep-zero-cluster-complex-1e4", "syn-ghep-near-singular-real-1e5",
    # application matrices with stored reference eigenvectors (ARPACK shift-invert, tol 1e-14)
    "cav2d-square-1e4", "cav2d-rect-pert-1e5", "ss-qa8fk-qa8fm", "ss-helm3d01", "ss-tem27623",
    "yee-photonic-rods-1e4", "yee-photonic-spheres-1e4",
    # no reference vectors: bound and cost only
    "yee-pec-cube-32", "yee-bloch-1e4", "yee-pec-box-1e5",
    # indefinite B (GHIEP): no certificate, so no bound (null with the reason)
    "wg-square-pert-1e4",
]
GROUP_KEYS = ("kind", "pairs", "unreturned", "lower", "upper", "dimension", "gap", "residual", "orthogonality",
              "sin_bound")


def cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor()


def git_head() -> str:
    try:
        # cwd rather than git -C: the cluster nodes' git 1.8.3 predates -C.
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def true_gap(ref_dir: Path, members: np.ndarray) -> float | None:
    """Distance from the group's exact eigenvalues to the rest of the spectrum, when the case's
    reference lists the complete spectrum (kind discrete-exact, complete, no window)."""
    info_path = ref_dir / "ref.json"
    if not info_path.is_file() or members.size == 0:
        return None
    info = json.loads(info_path.read_text())
    if not (info.get("complete") and info.get("window") is None):
        return None
    w = np.sort(np.load(ref_dir / "eigenvalues.npy").real)
    # The members as evaluated by the reference formula may differ from the stored values in the
    # last bits: a slack of 64 u max|lambda| keeps their stored copies out of "the rest".
    slack = 64 * np.finfo(float).eps * np.max(np.abs(w))
    lo, hi = members.min(), members.max()
    outside = w[(w < lo - slack) | (w > hi + slack)]
    if outside.size == 0:
        return None
    return float(np.min(np.where(outside < lo, lo - outside, outside - hi)))


def reference_check(case_dir: Path, ref_dir: Path, result: Path, report: dict) -> list[dict] | None:
    """Measured angles of the report's groups against the reference (None: no reference)."""
    if not report["subspace"]["performed"]:
        return None
    a = sp.load_npz(case_dir / "A.npz").tocsr()
    b = sp.load_npz(case_dir / "B.npz").tocsr() if (case_dir / "B.npz").is_file() else None
    x = np.load(result / "eigenvectors.npy")
    out = []
    for g in report["subspace"]["groups"]:
        lo = -np.inf if g["lower"] is None else g["lower"]
        hi = np.inf if g["upper"] is None else g["upper"]
        ref = sref.reference_pairs(case_dir, ref_dir, lo, hi)
        if ref is None:
            return None
        rec = {k: g[k] for k in ("kind", "pairs", "unreturned", "dimension", "gap", "residual", "sin_bound")}
        rec.update(reference=ref.source, reference_note=ref.note, reference_dimension=int(ref.values.size),
                   reference_backward_error=None, true_gap=None, measured_sin=None)
        if ref.values.size:
            rec["reference_backward_error"] = float(np.max(sref.backward_errors(a, b, ref.values, ref.vectors)))
        if ref.values.size == g["dimension"]:
            rec["measured_sin"] = sref.subspace_sin(x[:, g["pairs"]], ref.vectors, b)
            rec["true_gap"] = true_gap(ref_dir, ref.values)
        out.append(rec)
    return out


def guard_limits() -> dict:
    """The limits tools/run/guard.py sets for this process (its environment)."""
    cap = os.environ.get("HSOLVE_MEMORY_LIMIT_GB")
    return {"guarded": os.environ.get("HS_GUARDED") == "1", "exclusive": bool(os.environ.get("HS_SLOT_HELD")),
            "memory_limit_gb": float(cap) if cap else None}


def case_target(case_dir: Path) -> dict:
    """Target and tol of the case's configuration (null: the solver's default)."""
    cfg = json.loads((case_dir / "config.json").read_text())
    target = cfg.get("target", {})
    return {"mode": target.get("mode", "nearest"), "sigma": target.get("sigma"), "k": target.get("k"),
            "lower": target.get("lower"), "upper": target.get("upper"), "tol": cfg.get("tol")}


def solve(exe: Path, case_dir: Path, out: Path, variant: str, timeout: float) -> tuple[subprocess.CompletedProcess, float]:
    cmd = [str(exe), "--A", str(case_dir / "A.npz")]
    if (case_dir / "B.npz").is_file():
        cmd += ["--B", str(case_dir / "B.npz")]
    cmd += ["--config", str(case_dir / "config.json"), "--out", str(out), "--subspace-bound", variant, "-q"]
    t0 = time.perf_counter()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r, time.perf_counter() - t0


def summarize(rep_doc: dict) -> dict:
    sub = rep_doc["subspace"]
    return {"n": rep_doc["n"], "problem": rep_doc["problem"], "complex": rep_doc["complex_scalars"],
            "pairs": len(rep_doc["pairs"]), "success": rep_doc["success"],
            "certificate": rep_doc["certificate"]["method"], "certificate_passed": rep_doc["certificate"]["passed"],
            "max_backward_error": max((p["backward_error"] for p in rep_doc["pairs"]), default=None),
            "time_total_s": rep_doc["time_total_s"], "time_verify_s": rep_doc["time_verify_s"],
            "peak_rss_bytes": rep_doc["peak_rss_bytes"],
            "subspace": {k: sub[k] for k in ("performed", "max_sin_bound", "rigorous", "residual_norm", "b_min",
                                             "b_min_source", "note", "seconds")},
            "groups": [{k: g[k] for k in GROUP_KEYS} for g in sub["groups"]]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cases", nargs="*", default=DEFAULT_CASES)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--append", action="store_true", help="add this batch to an existing --out file")
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--variants", default="auto,off,on", help="--subspace-bound values, comma separated")
    ap.add_argument("--preset", default="release")
    ap.add_argument("--data", type=Path, default=REPO / "data")
    ap.add_argument("--timeout", type=float, default=900.0, help="per solve (s)")
    args = ap.parse_args(argv)
    variants = [v for v in args.variants.split(",") if v]
    if not variants or any(v not in ("auto", "off", "on") for v in variants):
        ap.error(f"--variants takes auto, off and on, got {args.variants!r}")
    exe = REPO / "build" / args.preset / "hsolve"
    version = subprocess.run([str(exe), "--version"], capture_output=True, text=True, check=True).stdout.strip()
    head = git_head()
    if args.append and args.out.is_file():
        doc = json.loads(args.out.read_text())
        first = doc["batches"][0]
        if (first["git_head"], first["preset"]) != (head, args.preset):
            ap.error(f"--append: {args.out} was measured at {first['git_head'][:10]} / {first['preset']}, "
                     f"this batch is {head[:10]} / {args.preset}")
    else:
        doc = {"description": "hsolve --subspace-bound auto, off and on on the cases' default configurations; "
                              "bound against the measured subspace angle",
               "batches": [], "runs": [], "reference_checks": {}}
    batch = {"host": platform.node(), "cpu": cpu_model(), "cores": len(os.sched_getaffinity(0)),
             "omp_num_threads": os.environ.get("OMP_NUM_THREADS"), "git_head": head, "hsolve_version": version,
             "preset": args.preset, "reps": args.reps, "variants": variants, "cases": args.cases,
             "guard": guard_limits(), "targets": {c: case_target(args.data / "cases" / c) for c in args.cases},
             "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    done = set(args.cases)
    doc["runs"] = [r for r in doc["runs"] if r["case"] not in done]
    for case in done:
        doc["reference_checks"].pop(case, None)
    work = Path(tempfile.mkdtemp(prefix="subspace-bound-", dir=os.environ.get("TMPDIR")))
    try:
        for rep in range(args.reps):
            for case in args.cases:
                case_dir = args.data / "cases" / case
                for variant in variants[rep % len(variants):] + variants[:rep % len(variants)]:
                    out = work / case / f"{variant}-{rep}"
                    r, wall = solve(exe, case_dir, out, variant, args.timeout)
                    entry = {"case": case, "variant": variant, "rep": rep, "returncode": r.returncode, "wall_s": wall}
                    if (out / "report.json").is_file():
                        rep_doc = json.loads((out / "report.json").read_text())
                        entry.update(summarize(rep_doc))
                        if variant == "auto":
                            t0 = time.perf_counter()
                            check = reference_check(case_dir, args.data / "refs" / case, out, rep_doc)
                            if check is not None:
                                doc["reference_checks"].setdefault(case, {"runs": []})["runs"].append(
                                    {"rep": rep, "groups": check, "seconds": time.perf_counter() - t0})
                    else:
                        entry["stderr"] = r.stderr[-2000:]
                    doc["runs"].append(entry)
                    print(json.dumps({k: entry.get(k) for k in ("case", "variant", "rep", "returncode",
                                                                 "time_total_s")}), flush=True)
                    shutil.rmtree(out, ignore_errors=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    batch["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    doc["batches"].append(batch)
    args.out.write_text(json.dumps(doc, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

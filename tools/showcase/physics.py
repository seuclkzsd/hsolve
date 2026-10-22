"""Physics checks for docs/showcase/物理场景.md: hsolve's eigenpairs against closed-form solutions.

(a) PEC rectangular cavity, a x b x d = 22.86 x 10.16 x 30 mm (a WR-90 cross-section closed by two
    walls), Yee/FIT edge discretization (tools/gen/yee.py, generalized form, h ~ 0.5 mm, n = 155966).
    Query: the lowest physical resonances, sigma = 0 with the gradient null space (50445 eigenvalues
    0) filtered by inertia (zero_filter_tol). Every frequency is compared with the discrete exact one
    (Yee dispersion, what the solver must hit) and the analytic f_mnp = c/2 sqrt((m/a)^2 + (n/b)^2 +
    (p/d)^2) (what the discretization approximates, O(h^2)).
(b) Square waveguide 10 x 10 mm at 50 GHz (the competition's real case; tools/gen/waveguide.py,
    Lee-Sun-Cendes, B indefinite): the 18 propagating modes beta = sqrt(-lambda) at n ~ 1e5 and 1e6
    against the certified discrete reference (tools/showcase/waveguide_ref.py) and the analytic
    beta = sqrt(k0^2 - kc^2), kc^2 = (m pi/a)^2 + (n pi/b)^2; the two mesh sizes show the O(h^2)
    convergence of the discretization while the solver error stays at rounding level.
(c) Mode fields: |E| on the cavity's mid-plane y = b/2 and |E_t| on the waveguide cross-section,
    from hsolve's eigenvectors, sampled on pixel grids (results/showcase/physics/*_modes.npz).

Accuracy only: hsolve runs in the build/test lane (8 threads), its times are not measurements.
Every result is also judged by tools/eval (backward error, completeness against the reference).

    python3 tools/run/guard.py --skip-busy-check --timeout 3600 --mem-gb 12 -- \\
        python -m tools.showcase.physics run --root $HOME/rb-evidence/data --source-root data
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from tools import case as cio  # noqa: E402
from tools.showcase import scenarios as scn  # noqa: E402

HSOLVE = REPO / "build/release/hsolve"
OUT_DIR = REPO / "results/showcase/physics"
C_MM_PER_NS = 299.792458                     # speed of light, mm * GHz
CAVITY_CASE = "phys-cavity-wr90"
CAVITY_DIMS = (22.86, 10.16, 30.0)           # mm
CAVITY_CELLS = (46, 20, 60)
CAVITY_K_MIN = 10
WAVEGUIDES = ("wg-square-1e5", "wg-square-1e6")
# Field pictures of the 1e5 guide; a joined label is a degenerate pair (the picture is one vector of
# its eigenspace, any combination of the two being a mode).
WAVEGUIDE_PICTURES = ("TE01/TE10", "TE11", "TM11", "TE22")
FIELD_PIXELS = 160
QUIVER = 14                                  # direction arrows of E_t: a QUIVER x QUIVER grid


def freq_ghz(lam: np.ndarray | float) -> np.ndarray | float:
    """Resonance frequency of a curl-curl eigenvalue lambda = k^2 [mm^-2] (eps = mu = 1)."""
    return C_MM_PER_NS * np.sqrt(np.maximum(lam, 0.0)) / (2.0 * np.pi)


# ---------------------------------------------------------------------------------- cavity

def cavity_modes(dims, cells, kmax2: float) -> list[dict[str, Any]]:
    """Every mode (m, n, p) of the PEC box with continuous k^2 <= kmax2: analytic and discrete
    (Yee) eigenvalues, TE/TM labels with respect to z and the number of polarizations (2 when
    m, n, p >= 1: TE_mnp and TM_mnp share the value in both models; 1 when exactly one index is 0)."""
    a, b, d = dims
    h = [L / N for L, N in zip(dims, cells)]
    out = []
    for m in range(cells[0]):
        for n in range(cells[1]):
            for p in range(cells[2]):
                idx = (m, n, p)
                zeros = sum(i == 0 for i in idx)
                if zeros > 1:
                    continue
                k2 = (m * np.pi / a) ** 2 + (n * np.pi / b) ** 2 + (p * np.pi / d) ** 2
                if k2 > kmax2:
                    continue
                terms = sorted((2.0 / hd * np.sin(i * np.pi / (2 * N))) ** 2 for hd, i, N in zip(h, idx, cells))
                disc = (terms[0] + terms[1]) + terms[2]
                if zeros == 0:
                    label, pol = f"TE{m}{n}{p}/TM{m}{n}{p}", 2
                elif p == 0:
                    label, pol = f"TM{m}{n}0", 1
                else:
                    label, pol = f"TE{m}{n}{p}", 1
                out.append({"mnp": list(idx), "label": label, "polarizations": pol,
                            "lambda_analytic": k2, "lambda_discrete": disc})
    return sorted(out, key=lambda r: r["lambda_discrete"])


def write_cavity_case(root: Path) -> Path:
    """The cavity case (generalized form) with its physical-spectrum reference and target."""
    from tools.gen import yee
    grid = yee.YeeGrid(CAVITY_CELLS, CAVITY_DIMS, "pec")
    a, b = yee.assemble(grid)
    w = yee.exact_eigenvalues(grid)
    physical = w[w > 0]
    cond_b = scn.diagonal_cond(b)
    target = scn.lowest_physical_target(physical, k_min=CAVITY_K_MIN, cond_b=cond_b)
    meta = {"family": "yee", "problem": "GHEP",
            "description": (f"PEC rectangular cavity {CAVITY_DIMS[0]} x {CAVITY_DIMS[1]} x {CAVITY_DIMS[2]} mm, "
                            f"Yee/FIT {CAVITY_CELLS} cells, generalized form; physical modes only "
                            f"(the {grid.null_space_dimension()}-dimensional gradient null space is not wanted)"),
            "params": {"generator": "yee", "cells": list(CAVITY_CELLS), "lengths": list(CAVITY_DIMS),
                       "boundary": "pec", "form": "generalized", "units": {"length": "mm", "eigenvalue": "mm^-2"}}}
    path = cio.save_case(CAVITY_CASE, a, b, meta=meta, config={"target": target, "tol": scn.TOL}, root=root)
    cio.save_ref(CAVITY_CASE, physical, kind="discrete-exact", complete=True, window=None, root=root,
                 note=("discrete Yee/FIT spectrum without the gradient null space (eigenvalue 0, "
                       f"{grid.null_space_dimension()} copies): physical resonances only"))
    return path


def edge_fields_to_cells(x: np.ndarray, cells, dims) -> np.ndarray:
    """|E| at cell centres (Nx, Ny, Nz) of a PEC Yee eigenvector in integral form (u_e = h_e E_e),
    unknowns ordered x-, y-, z-edges in C order (tools/gen/yee.py): each component is the mean of the
    four parallel edges of the cell, PEC edges (not unknowns) being zero."""
    nx, ny, nz = cells
    hx, hy, hz = (L / N for L, N in zip(dims, cells))
    sizes = (nx * (ny - 1) * (nz - 1), (nx - 1) * ny * (nz - 1), (nx - 1) * (ny - 1) * nz)
    ux, uy, uz = np.split(np.asarray(x), np.cumsum(sizes)[:2])
    ex = np.zeros((nx, ny + 1, nz + 1), dtype=x.dtype)
    ey = np.zeros((nx + 1, ny, nz + 1), dtype=x.dtype)
    ez = np.zeros((nx + 1, ny + 1, nz), dtype=x.dtype)
    ex[:, 1:ny, 1:nz] = ux.reshape(nx, ny - 1, nz - 1) / hx
    ey[1:nx, :, 1:nz] = uy.reshape(nx - 1, ny, nz - 1) / hy
    ez[1:nx, 1:ny, :] = uz.reshape(nx - 1, ny - 1, nz) / hz
    cx = 0.25 * (ex[:, :-1, :-1] + ex[:, 1:, :-1] + ex[:, :-1, 1:] + ex[:, 1:, 1:])
    cy = 0.25 * (ey[:-1, :, :-1] + ey[1:, :, :-1] + ey[:-1, :, 1:] + ey[1:, :, 1:])
    cz = 0.25 * (ez[:-1, :-1, :] + ez[1:, :-1, :] + ez[:-1, 1:, :] + ez[1:, 1:, :])
    return np.sqrt(np.abs(cx) ** 2 + np.abs(cy) ** 2 + np.abs(cz) ** 2)


# ------------------------------------------------------------------------------------ runs

def run_hsolve(c: cio.Case, extra: dict[str, Any], out: Path, threads: int) -> dict[str, Any]:
    """hsolve on case c (config + extra keys), result in out; returns the report."""
    out.mkdir(parents=True, exist_ok=True)
    cfg = out / "config.json"
    cfg.write_text(json.dumps({**c.config, **extra}))
    cmd = [str(HSOLVE), "--A", str(c.path / "A.npz"), "--config", str(cfg), "--out", str(out / "result"),
           "--threads", str(threads), "-q"]
    if c.B is not None:
        cmd[3:3] = ["--B", str(c.path / "B.npz")]
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    (out / "stderr.txt").write_text(proc.stderr)
    if not (out / "result/report.json").exists():
        raise RuntimeError(f"hsolve failed on {c.name} (rc {proc.returncode}): {proc.stderr[-800:]}")
    rep = json.loads((out / "result/report.json").read_text())
    rep["_wall_s"] = time.perf_counter() - t0
    rep["_returncode"] = proc.returncode
    return rep


def judge(c: cio.Case, result: Path) -> dict[str, Any]:
    from tools.eval import evaluate
    ev = evaluate.evaluate(c, result)
    comp = ev["completeness"]
    return {"verdict": ev["verdict"], "reasons": ev["reasons"], "completeness": comp["status"],
            "certified": comp["certified"], "expected": comp["expected"], "found": comp["found"],
            "max_backward_error": ev["summary"]["max_backward_error"],
            "max_eig_scaled_error": max((p["eig_scaled_error"] for p in ev["pairs"]
                                         if p.get("eig_scaled_error") is not None), default=None)}


def cavity(root: Path, work: Path, threads: int) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    if not (root / "cases" / CAVITY_CASE / "A.npz").exists():
        write_cavity_case(root)
    c = cio.load_case(CAVITY_CASE, root=root)
    hs_keys = {**scn.METHOD_PIN, "zero_filter_tol": scn.ZERO_FILTER_TOL}
    rep = run_hsolve(c, hs_keys, work / CAVITY_CASE, threads)
    res = cio.load_result(work / CAVITY_CASE / "result")
    ev = judge(c, work / CAVITY_CASE / "result")
    lam = np.asarray(res.eigenvalues, dtype=float)
    order = np.argsort(lam)
    lam, vecs = lam[order], res.eigenvectors[:, order]
    modes = cavity_modes(CAVITY_DIMS, CAVITY_CELLS, 1.5 * float(lam.max()))
    rows, used = [], set()
    for j, x in enumerate(lam):
        cand = [i for i, md in enumerate(modes) if abs(md["lambda_discrete"] - x) <= 1e-8 * x]
        if not cand:
            raise RuntimeError(f"cavity: computed eigenvalue {x} matches no discrete mode")
        i = cand[0]
        md = modes[i]
        rows.append({"index": j, "label": md["label"], "mnp": md["mnp"], "polarizations": md["polarizations"],
                     "copy": sum(1 for r in rows if r["label"] == md["label"]) + 1,
                     "lambda_hsolve": float(x), "lambda_discrete": md["lambda_discrete"],
                     "lambda_analytic": md["lambda_analytic"], "f_hsolve_ghz": float(freq_ghz(x)),
                     "f_discrete_ghz": float(freq_ghz(md["lambda_discrete"])),
                     "f_analytic_ghz": float(freq_ghz(md["lambda_analytic"])),
                     "solver_rel_error": abs(x - md["lambda_discrete"]) / md["lambda_discrete"],
                     "discretization_rel_error_f": abs(freq_ghz(md["lambda_discrete"]) - freq_ghz(md["lambda_analytic"]))
                     / freq_ghz(md["lambda_analytic"])})
        used.add(i)
    # Field pictures: non-degenerate modes (a single vector is the mode, not a basis choice).
    fields, pictured = {}, []
    ny_mid = CAVITY_CELLS[1] // 2
    for r in rows:
        if r["polarizations"] == 1 and r["copy"] == 1 and len(pictured) < 6:
            e = edge_fields_to_cells(vecs[:, r["index"]], CAVITY_CELLS, CAVITY_DIMS)
            sl = e[:, ny_mid, :]
            fields[r["label"]] = (sl / sl.max()).astype(np.float32)
            pictured.append(r["label"])
    doc = {"case": CAVITY_CASE, "dims_mm": list(CAVITY_DIMS), "cells": list(CAVITY_CELLS), "n": c.n,
           "null_space": int((CAVITY_CELLS[0] - 1) * (CAVITY_CELLS[1] - 1) * (CAVITY_CELLS[2] - 1)),
           "h_mm": [L / N for L, N in zip(CAVITY_DIMS, CAVITY_CELLS)], "target": c.config["target"],
           "hsolve_config": hs_keys, "zero_modes_filtered": rep.get("zero_modes_filtered"),
           "certificate": rep.get("certificate"), "candidate_source": rep.get("candidate_source"),
           "success": rep.get("success"), "evaluation": ev, "modes": rows,
           "field_slice": {"plane": "y = b/2 (cell layer %d of %d)" % (ny_mid, CAVITY_CELLS[1]),
                           "axes": ["x (a)", "z (d)"], "modes": pictured}}
    return doc, fields


def waveguide(root: Path, name: str, work: Path, threads: int, with_fields: bool
              ) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    from tools.showcase import waveguide_ref as wref
    c = cio.load_case(name, root=root)
    fam_path = root / "refs" / name / "family.json"
    if not fam_path.exists():
        raise FileNotFoundError(f"{fam_path}: run `tools/showcase/run_all.sh prepare` first")
    fam = json.loads(fam_path.read_text())
    rep = run_hsolve(c, {}, work / name, threads)
    res = cio.load_result(work / name / "result")
    ev = judge(c, work / name / "result")
    lam = np.asarray(res.eigenvalues, dtype=float)
    ref = [(m["lambda"], m["lambda_continuous"], m["label"], f) for f, d in fam["families"].items()
           for m in d["modes"]]
    ref.sort()
    k0 = float(fam["k0_rad_per_mm"])
    order = np.argsort(lam)
    rows = []
    for j in order:
        x = lam[j]
        i = int(np.argmin([abs(r[0] - x) for r in ref]))
        disc, cont, label, family = ref[i]
        rows.append({"index": int(j), "label": label, "family": family, "lambda_hsolve": float(x),
                     "lambda_discrete": disc, "lambda_continuous": cont,
                     "beta_hsolve": float(np.sqrt(-x)) if x < 0 else None,
                     "beta_discrete": float(np.sqrt(-disc)) if disc < 0 else None,
                     "beta_analytic": float(np.sqrt(-cont)) if cont < 0 else None,
                     "solver_rel_error": abs(x - disc) / abs(disc),
                     "discretization_rel_error_beta": (abs(np.sqrt(-disc) - np.sqrt(-cont)) / np.sqrt(-cont)
                                                       if disc < 0 and cont < 0 else None)})
    meta = c.meta
    doc = {"case": name, "n": c.n, "k0_rad_per_mm": k0, "freq_ghz": meta["params"]["freq_ghz"],
           "h_max_mm": meta["mesh"]["h_max_mm"], "interior_edges": meta["mesh"]["interior_edges"],
           "interior_nodes": meta["mesh"]["interior_nodes"], "inertia": meta.get("inertia"),
           "target": c.config["target"], "zero_cluster_dim": rep.get("zero_cluster_dim"),
           "complex_returned": int(len(res.complex_eigenvalues) if res.complex_eigenvalues is not None else 0),
           "candidate_source": rep.get("candidate_source"), "success": rep.get("success"),
           "evaluation": ev, "reference_note": json.loads((root / "refs" / name / "ref.json").read_text())["note"],
           "modes": rows}
    fields: dict[str, np.ndarray] = {}
    if with_fields:
        rb = wref.rebuild(c)
        pictured = []
        for label in WAVEGUIDE_PICTURES:
            r = next((r for r in rows if r["label"] == label), None)
            if r is None:
                continue
            et = wref.centroid_fields(rb, res.eigenvectors[:, r["index"]])
            mag = np.sqrt((np.abs(et) ** 2).sum(axis=1))
            scale = np.nanmax(mag)
            fields[r["label"]] = wref.sample_on_grid(rb, mag / scale, FIELD_PIXELS, FIELD_PIXELS)
            # Direction of the (real) transverse field on a coarse grid, same normalization.
            fields[r["label"] + "::ex"] = wref.sample_on_grid(rb, np.real(et[:, 0]) / scale, QUIVER, QUIVER)
            fields[r["label"] + "::ey"] = wref.sample_on_grid(rb, np.real(et[:, 1]) / scale, QUIVER, QUIVER)
            pictured.append(r["label"])
        doc["field_pictures"] = {"quantity": "|E_t| (transverse field) at triangle centroids, sampled on a "
                                             f"{FIELD_PIXELS}x{FIELD_PIXELS} pixel grid; E_t components "
                                             f"('<label>::ex', '::ey') on a {QUIVER}x{QUIVER} grid",
                                 "modes": pictured}
    return doc, fields


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    rp = sub.add_parser("run")
    rp.add_argument("--root", type=Path, default=scn.DEFAULT_ROOT)
    rp.add_argument("--source-root", type=Path, action="append", default=None)
    rp.add_argument("--work", type=Path, default=Path.home() / "rb-evidence/physics")
    rp.add_argument("--out-dir", type=Path, default=OUT_DIR)
    rp.add_argument("--threads", type=int, default=int(os.environ.get("OMP_NUM_THREADS", "8")))
    rp.add_argument("--only", choices=("cavity", "waveguide"), default=None)
    args = ap.parse_args(argv)
    from tools.eval import common
    common.require_guard("showcase.physics")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    env = {"hsolve_binary": str(HSOLVE.relative_to(REPO)), "threads": args.threads,
           "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True,
                                        text=True).stdout.strip(),
           "host": os.uname().nodename, "date": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "note": "accuracy runs in the build/test lane; times are not measurements"}
    if args.only in (None, "cavity"):
        doc, fields = cavity(args.root, args.work, args.threads)
        doc["conditions"] = env
        (args.out_dir / "cavity.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
        np.savez_compressed(args.out_dir / "cavity_modes.npz", **fields)
        print(f"cavity: {len(doc['modes'])} modes, evaluation {doc['evaluation']['verdict']}", flush=True)
    if args.only in (None, "waveguide"):
        docs, all_fields = [], {}
        for i, name in enumerate(WAVEGUIDES):
            doc, fields = waveguide(args.root, name, args.work, args.threads, with_fields=(i == 0))
            docs.append(doc)
            all_fields.update(fields)
            print(f"{name}: {len(doc['modes'])} modes, evaluation {doc['evaluation']['verdict']}", flush=True)
        out = {"conditions": env, "cases": docs}
        (args.out_dir / "waveguide.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
        np.savez_compressed(args.out_dir / "waveguide_modes.npz", **all_fields)
    return 0


if __name__ == "__main__":
    sys.exit(main())

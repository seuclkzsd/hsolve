"""Certified discrete reference of a hollow rectangular waveguide case (tools/gen/waveguide.py).

For an air-filled PEC guide the Lee-Sun-Cendes pencil (A, B) decouples exactly into two
symmetric-definite families (tools/gen/waveguide.py, module docstring):

    TE   lambda = kc^2 - k0^2,  kc^2 a nonzero eigenvalue of (S_tt, T_tt)   Nedelec curl-curl
    TM   lambda = kc^2 - k0^2,  kc^2 an eigenvalue of (S_zz, T_zz)          P1 Dirichlet Laplacian

plus the eigenvalue 0 of A = blkdiag(S_tt - k0^2 T_tt, 0): its eigenvectors [0; psi] span the
interior-node space, so 0 has exactly that multiplicity whenever k0^2 is no family eigenvalue
(checked below). It is not a mode, but it is an eigenvalue of the pencil, so the reference lists it:
an evaluation of "the k eigenvalues nearest sigma" then sees the zero cluster as the next-nearest
level and can certify the set, and a solver returning null-space vectors is caught as missing modes.
Every family is counted exactly by Sylvester's law over a window [m_lo, m_hi] of kc^2 with
0 < m_lo (excluding S_tt's own null space at kc^2 = 0) and m_hi = k0^2 + lambda_hi, lambda_hi half the
lowest positive (evanescent) closed-form lambda: #eigenvalues of (S, T) below mu = #negative pivots
of an LDL^T factorization of S - mu T. The
factorization is SuperLU's in symmetric mode without off-diagonal pivoting (diag_pivot_thresh = 0;
checked: equal row and column permutations, i.e. P K P^T = L U with U = D L^T, and a solve residual
check against element growth). The values come from ARPACK shift-invert at the window centre with
k = the count: the window is symmetric about the shift, so its eigenvalues are exactly the k nearest
ones, and the null space of S_tt (at kc^2 = 0, distance > half the window) is not among them. The
reference is accepted only if ARPACK returns exactly the counted number inside the window and every
pair passes a backward-error check; the count must also equal the continuous model's (closed form,
a-priori O(h^2) error bound of the generator).

Written to <root>/refs/<case>/ with kind "solver", complete = true and the window in lambda; the
per-family values with their continuous mode labels go to family.json (used by the physics page).
This is independent of hsolve: SuperLU + ARPACK through scipy, a different formulation (two definite
problems instead of one indefinite pencil).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from tools import case as cio
from tools.gen import waveguide as wg

LOW_FRACTION = 0.25      # m_lo = LOW_FRACTION * (pi / max(a, b))^2: below the lowest cutoff of both families
HIGH_FRACTION = 0.5      # lambda_hi = HIGH_FRACTION * the lowest positive closed-form lambda
ARPACK_TOL = 1e-14
VERIFY_ETA = 1e-11       # backward error of every reference pair
SOLVE_CHECK = 1e-8       # relative residual of the LDU solve used for the counts


@dataclass
class Rebuilt:
    spec: wg.CaseSpec
    mesh: Any
    disc: wg.Discretization
    k0: float
    eps_r: np.ndarray
    mu_r: np.ndarray


def rebuild(c: cio.Case) -> Rebuilt:
    """Re-run the generator's mesh and assembly from meta.json and check that it reproduces the stored
    pencil (so dof numbering, mesh and families belong to this case)."""
    p = c.meta["params"]
    if p.get("family") != "waveguide":
        raise ValueError(f"{c.name}: not a tools.gen.waveguide waveguide case")
    hollow = float(p.get("eps_slab", 1.0)) == 1.0 and float(p.get("mu_slab", 1.0)) == 1.0
    spec = wg.CaseSpec(family="waveguide", a=p["a"], b=p["b"], freq_ghz=p["freq_ghz"], eps_slab=p["eps_slab"],
                       mu_slab=p["mu_slab"], slab_width=None if hollow else p["slab_width"], nx=p["nx"], ny=p["ny"],
                       pattern=p["pattern"], perturb=p["perturb"], seed=p["seed"])
    mesh, eps_r, mu_r = wg.build_mesh(spec, p["nx"], p["ny"])
    disc = wg.discretize(mesh)
    k0 = wg.wavenumber(spec.freq_ghz)
    a2, b2 = wg.waveguide_pencil(disc, k0, eps_r, mu_r)
    for name, mine, stored in (("A", a2, c.A), ("B", b2, c.B)):
        diff = abs(mine - stored).max() if mine.shape == stored.shape else np.inf
        if not diff <= 1e-14 * abs(stored).max():
            raise ValueError(f"{c.name}: re-assembled {name} differs from the stored one (max |diff| {diff:.3g})")
    return Rebuilt(spec, mesh, disc, k0, eps_r, mu_r)


def negative_count(k: sp.spmatrix) -> dict[str, Any]:
    """Sylvester count of a real symmetric matrix: negative pivots of P K P^T = L D L^T (SuperLU,
    symmetric mode, no off-diagonal pivoting), with the checks described in the module docstring."""
    t0 = time.perf_counter()
    kc = sp.csc_matrix(k)
    lu = spla.splu(kc, permc_spec="MMD_AT_PLUS_A", diag_pivot_thresh=0.0,
                   options={"SymmetricMode": True})
    if not np.array_equal(lu.perm_r, lu.perm_c):
        raise RuntimeError("SuperLU pivoted off the diagonal: no symmetric LDL^T, no inertia")
    d = lu.U.diagonal()
    if not np.all(np.isfinite(d)) or np.min(np.abs(d)) <= 1e-13 * np.max(np.abs(d)):
        raise RuntimeError("zero or non-finite pivot: the shift is (numerically) an eigenvalue")
    rng = np.random.default_rng(1)
    b = rng.standard_normal(kc.shape[0])
    x = lu.solve(b)
    res = float(np.linalg.norm(kc @ x - b) / (spla.norm(kc, 1) * np.linalg.norm(x) + np.linalg.norm(b)))
    if not res <= SOLVE_CHECK:
        raise RuntimeError(f"LDU solve residual {res:.2e}: element growth, the pivot signs are not trusted")
    return {"negative": int(np.count_nonzero(d < 0)), "solve_residual": res,
            "min_pivot_rel": float(np.min(np.abs(d)) / np.max(np.abs(d))), "seconds": time.perf_counter() - t0}


def family_window(s: sp.spmatrix, t: sp.spmatrix, m_lo: float, m_hi: float, seed: int = 7) -> dict[str, Any]:
    """Every eigenvalue of the definite pencil (s, t) in [m_lo, m_hi], counted and computed."""
    lo, hi = negative_count(s - m_lo * t), negative_count(s - m_hi * t)
    count = hi["negative"] - lo["negative"]
    c, r = 0.5 * (m_lo + m_hi), 0.5 * (m_hi - m_lo)
    values = np.empty(0)
    vectors = np.empty((s.shape[0], 0))
    if count > 0:
        v0 = np.random.default_rng(seed).standard_normal(s.shape[0])
        for ncv in (max(2 * count + 1, 20), max(4 * count + 1, 40)):
            values, vectors = spla.eigsh(s, k=count, M=t, sigma=c, which="LM", tol=ARPACK_TOL, ncv=ncv, v0=v0)
            inside = np.abs(values - c) <= r
            if inside.all():
                break
        if not np.all(np.abs(values - c) <= r):
            raise RuntimeError(f"ARPACK returned values outside the counted window ({count} counted)")
        order = np.argsort(values)
        values, vectors = values[order], vectors[:, order]
    resid = [float(np.linalg.norm(s @ vectors[:, j] - values[j] * (t @ vectors[:, j]))
                   / ((spla.norm(s, 1) + abs(values[j]) * spla.norm(t, 1)) * np.linalg.norm(vectors[:, j])))
             for j in range(values.size)]
    if resid and max(resid) > VERIFY_ETA:
        raise RuntimeError(f"family pair failed the backward-error check: {max(resid):.2e}")
    gram = vectors.T @ (t @ vectors) if values.size else np.zeros((0, 0))
    if values.size and np.linalg.norm(gram - np.eye(values.size)) > 1e-8:
        raise RuntimeError("family eigenvectors are not T-orthonormal: a copy was returned twice")
    return {"values": values, "count": count, "counts": [lo, hi], "max_backward_error": max(resid, default=0.0)}


def continuous_labels(spec: wg.CaseSpec, family: str, m_lo: float, m_hi: float) -> list[tuple[float, str]]:
    """Closed-form kc^2 of one family inside [m_lo, m_hi] with display labels: modes sharing a
    cutoff (TE_mn / TE_nm of a square guide) get one joined label."""
    modes = [m for m in wg.rectangle_cutoffs(spec.a, spec.b, m_hi, tm=True)
             if m.label.startswith(family) and m.value >= m_lo]
    out = []
    for m in modes:
        same = [x.label for x in modes if abs(x.value - m.value) <= 1e-12 * m.value]
        out.append((m.value, "/".join(lbl.replace(",", "") for lbl in same)))
    return out


def build(c: cio.Case) -> tuple[np.ndarray, dict[str, Any]]:
    """(lambda values ascending, family.json document) of a hollow waveguide case."""
    t0 = time.perf_counter()
    rb = rebuild(c)
    spec, disc, k0 = rb.spec, rb.disc, rb.k0
    if spec.loaded:
        raise ValueError(f"{c.name}: the TE/TM decoupling holds for hollow guides only")
    k2 = k0 * k0
    m_lo = LOW_FRACTION * (np.pi / max(spec.a, spec.b)) ** 2
    evanescent = [m.value for m in wg.hollow_guide_modes(spec.a, spec.b, k0, 4.0 * k2) if m.value > 0]
    lam_hi = HIGH_FRACTION * min(evanescent)
    m_hi = k2 + lam_hi
    fams = {"TE": (wg.curl_tt(disc), wg.mass_tt(disc)), "TM": (wg.stiff_zz(disc), wg.mass_zz(disc))}
    zeros = disc.num_node_dofs
    doc: dict[str, Any] = {"case": c.name, "k0_rad_per_mm": k0, "kc2_window": [m_lo, m_hi],
                           "lambda_window": [m_lo - k2, lam_hi], "zero_eigenvalue_multiplicity": zeros,
                           "families": {}}
    values = []
    for name, (s, t) in fams.items():
        res = family_window(s, t, m_lo, m_hi)
        model = continuous_labels(spec, name, m_lo, m_hi)
        if len(model) != res["count"]:
            raise RuntimeError(f"{name}: {res['count']} discrete eigenvalues counted in the window, the "
                               f"continuous model has {len(model)}")
        if res["values"].size and np.min(np.abs(res["values"] - k2)) <= 1e-6 * k2:
            raise RuntimeError(f"{name}: a family eigenvalue sits at k0^2: the zero eigenvalue is not semisimple")
        doc["families"][name] = {
            "count": res["count"], "counts_at_window_ends": res["counts"],
            "max_backward_error": res["max_backward_error"],
            "modes": [{"label": lbl, "kc2": float(v), "kc2_continuous": float(mv), "lambda": float(v - k2),
                       "lambda_continuous": float(mv - k2)} for v, (mv, lbl) in zip(res["values"], model)]}
        values.extend(v - k2 for v in res["values"])
    values.extend([0.0] * zeros)
    doc["seconds"] = time.perf_counter() - t0
    return np.sort(np.asarray(values)), doc


def write_reference(name: str, root: str | Path) -> str:
    """Build and save the reference of case `name` under root; returns a status line."""
    c = cio.load_case(name, root=root)
    values, doc = build(c)
    lo, hi = doc["lambda_window"]
    counts = {f: d["count"] for f, d in doc["families"].items()}
    note = (f"TE/TM family decomposition of the hollow guide: lambda = kc^2 - k0^2 over kc^2 in "
            f"[{doc['kc2_window'][0]:.6g}, {doc['kc2_window'][1]:.6g}]; counts by Sylvester inertia of "
            f"S - mu T (SuperLU symmetric LDU) {counts}, values by ARPACK shift-invert (tol {ARPACK_TOL:g}), "
            f"equal to the closed-form mode count; plus the eigenvalue 0 of A's null space with multiplicity "
            f"{doc['zero_eigenvalue_multiplicity']} (interior nodes; not a mode)")
    cio.save_ref(name, values, kind="solver", note=note, complete=True, window=(lo, hi), root=root)
    (Path(root) / "refs" / name / "family.json").write_text(json.dumps(doc, indent=1) + "\n")
    return (f"{name}: wrote TE/TM family reference ({values.size} eigenvalues in [{lo:.6g}, {hi:.6g}]: {counts} "
            f"and {doc['zero_eigenvalue_multiplicity']} zeros)")


# ------------------------------------------------------------------------------- field sampling

def centroid_fields(rb: Rebuilt, x: np.ndarray) -> np.ndarray:
    """Transverse field e_t = sum_e x_e N_e at every triangle centroid, shape (nt, 2), from the edge
    part x[:interior edges] of a pencil eigenvector (Whitney functions N_lohi = L_lo grad L_hi -
    L_hi grad L_lo with the global lo -> hi orientation; at the centroid L = 1/3)."""
    mesh, topo, disc = rb.mesh, rb.disc.topo, rb.disc
    p = mesh.nodes[mesh.triangles]                                   # (nt, 3, 2)
    area2 = (p[:, 1, 0] - p[:, 0, 0]) * (p[:, 2, 1] - p[:, 0, 1]) - (p[:, 2, 0] - p[:, 0, 0]) * (p[:, 1, 1] - p[:, 0, 1])
    # grad L_i = perp(p_{i+2} - p_{i+1}) / (2 area), perp(v) = (-v_y, v_x) for counter-clockwise triangles
    grads = np.empty_like(p)
    for i in range(3):
        v = p[:, (i + 2) % 3] - p[:, (i + 1) % 3]
        grads[:, i, 0] = -v[:, 1] / area2
        grads[:, i, 1] = v[:, 0] / area2
    field = np.zeros((mesh.num_triangles, 2), dtype=np.result_type(x.dtype, float))
    edge_vals = np.zeros(topo.num_edges, dtype=field.dtype)
    keep = disc.edge_dof >= 0
    edge_vals[keep] = x[disc.edge_dof[keep]]
    from tools.gen.mesh2d import LOCAL_EDGES
    for k, (a, b) in enumerate(LOCAL_EDGES):
        e = topo.tri_edges[:, k]
        # local a -> b; global lo -> hi: N_global = sign * (L_a grad L_b - L_b grad L_a)
        n_local = (grads[:, b] - grads[:, a]) / 3.0
        field += (topo.tri_signs[:, k] * edge_vals[e])[:, None] * n_local
    return field


def locate_pixels(nodes: np.ndarray, triangles: np.ndarray, width: float, height: float,
                  nx: int, ny: int) -> np.ndarray:
    """Triangle containing each pixel centre of an nx x ny grid over [0, width] x [0, height]
    (shape (ny, nx), rows = y from bottom to top, -1 where none does): every triangle tests the
    pixel centres inside its bounding box with barycentric coordinates (numpy only)."""
    p = nodes[triangles]                                            # (nt, 3, 2)
    dx, dy = width / nx, height / ny
    i0 = np.ceil(p[:, :, 0].min(axis=1) / dx - 0.5).astype(np.int64)
    i1 = np.floor(p[:, :, 0].max(axis=1) / dx - 0.5).astype(np.int64)
    j0 = np.ceil(p[:, :, 1].min(axis=1) / dy - 0.5).astype(np.int64)
    j1 = np.floor(p[:, :, 1].max(axis=1) / dy - 0.5).astype(np.int64)
    span_i, span_j = int(max(0, (i1 - i0).max()) + 1), int(max(0, (j1 - j0).max()) + 1)
    owner = np.full((ny, nx), -1, dtype=np.int64)
    a, b, c = p[:, 0], p[:, 1], p[:, 2]
    det = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1])
    tri_ids = np.arange(len(triangles))
    for di in range(span_i):
        for dj in range(span_j):
            i, j = i0 + di, j0 + dj
            ok = (i <= i1) & (j <= j1) & (i >= 0) & (i < nx) & (j >= 0) & (j < ny)
            if not ok.any():
                continue
            px, py = (i[ok] + 0.5) * dx, (j[ok] + 0.5) * dy
            aa, bb, cc, dd = a[ok], b[ok], c[ok], det[ok]
            l1 = ((px - aa[:, 0]) * (cc[:, 1] - aa[:, 1]) - (cc[:, 0] - aa[:, 0]) * (py - aa[:, 1])) / dd
            l2 = ((bb[:, 0] - aa[:, 0]) * (py - aa[:, 1]) - (px - aa[:, 0]) * (bb[:, 1] - aa[:, 1])) / dd
            inside = (l1 >= -1e-12) & (l2 >= -1e-12) & (l1 + l2 <= 1 + 1e-12)
            owner[j[ok][inside], i[ok][inside]] = tri_ids[ok][inside]
    return owner


def sample_on_grid(rb: Rebuilt, tri_values: np.ndarray, nx: int = 160, ny: int = 160) -> np.ndarray:
    """Per-triangle values at the pixel centres of an nx x ny grid over the guide's cross-section
    (rows = y from bottom to top; NaN outside every triangle)."""
    owner = locate_pixels(rb.mesh.nodes, rb.mesh.triangles, rb.spec.a, rb.spec.b, nx, ny)
    return np.where(owner >= 0, tri_values[np.maximum(owner, 0)], np.nan).astype(np.float32)

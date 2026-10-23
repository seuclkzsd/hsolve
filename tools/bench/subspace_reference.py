# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 seuclkzsd and the hsolve contributors
"""Reference eigenvectors for checking hsolve's eigenvector subspace-angle bounds.

The bound in report.json (docs/DESIGN.md §3.6-8c, docs/FORMATS.md §3 `subspace`) compares the span
of each group of returned vectors with the exact spectral subspace of an eigenvalue interval. This
module supplies an independent stand-in for that exact subspace and measures the angle:

* exact_pairs(case_dir, lo, hi) - the synthetic families of tools/gen/synthetic.py have known
  eigenvectors. They are recomputed from the generator parameters recorded in meta.json, replaying
  the generator's random streams: prescribed-spectrum matrices (P Q diag(d) Q^H P^T: columns of
  P Q), HPD congruence pencils (A = P W^H M W P^T, B = P W^H W P^T: x = P W^{-1} Q e_j), Dirichlet
  Laplacians and the tensor-product stencils (Kronecker products of the 1-D sine vectors). The
  stored matrices agree with these formulas up to assembly rounding; check_pairs measures how far.
* stored_pairs(ref_dir, lo, hi) - the reference eigenvectors saved with a case
  (data/refs/<case>/eigenvectors.npy; ARPACK shift-invert at tol 1e-14 for the solver references).
* subspace_sin(x, v, b) - ||sin Theta(span x, span v)||_F in the B inner product (b None: B = I),
  for dim span x <= dim span v.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from tools.gen import synthetic as syn

EXACT_GENERATORS = ("synthetic.prescribed_hermitian", "synthetic.congruence_pair", "synthetic.laplacian",
                    "synthetic.stencil_operator")


@dataclass
class ReferencePairs:
    """Eigenpairs of a case with eigenvalues in an interval, and where they come from."""
    values: np.ndarray       # ascending
    vectors: np.ndarray      # n x m, columns match values
    source: str              # "exact" (generator formula) or "stored" (data/refs eigenvectors)
    note: str = ""


# ------------------------------------------------------------------------------- the angle


def subspace_sin(x: np.ndarray, v: np.ndarray, b: sp.spmatrix | None = None) -> float:
    """||sin Theta(span x, span v)||_F in the B inner product (b None: B = I).

    Both bases are B-orthonormalized (Cholesky-free: through the eigendecomposition of the Gram
    matrix); the result is the B-Frobenius norm of x's basis minus its B-orthogonal projection onto
    span v. Needs dim span x <= dim span v (otherwise it measures span x against a smaller space)."""
    def bmul(y):
        return y if b is None else b @ y

    def orth(y):
        g = y.conj().T @ bmul(y)
        g = 0.5 * (g + g.conj().T)
        w, u = np.linalg.eigh(g)
        if w.min() <= 0.0:
            raise ValueError("basis is not linearly independent")
        return y @ (u / np.sqrt(w))

    if x.shape[1] > v.shape[1]:
        raise ValueError(f"span x ({x.shape[1]} columns) is larger than span v ({v.shape[1]})")
    xo, vo = orth(x), orth(v)
    p = xo - vo @ (vo.conj().T @ bmul(xo))
    return float(np.sqrt(max(np.real(np.trace(p.conj().T @ bmul(p))), 0.0)))


def backward_errors(a: sp.spmatrix, b: sp.spmatrix | None, values: np.ndarray, vectors: np.ndarray) -> np.ndarray:
    """||A v - lambda B v||_2 / ((||A||_1 + |lambda| ||B||_1) ||v||_2) per column (the 1-norm is an
    upper bound of the 2-norm of a Hermitian matrix, so these are lower estimates of hsolve's
    backward_error, which uses ||.||_2 estimates)."""
    norm_a = abs(a).sum(axis=0).max()
    norm_b = 1.0 if b is None else abs(b).sum(axis=0).max()
    bv = vectors if b is None else b @ vectors
    r = a @ vectors - bv * values[None, :]
    scale = (norm_a + np.abs(values) * norm_b) * np.linalg.norm(vectors, axis=0)
    return np.linalg.norm(r, axis=0) / scale


# --------------------------------------------------------------------- generator replays


def _sine_basis(n: int) -> np.ndarray:
    """Orthonormal eigenvectors of tridiag(-1, 2, -1) of order n, column j-1 for eigenvalue
    4 sin^2(j pi / (2 (n+1))) (ascending, as in synthetic.second_difference_eigenvalues)."""
    i = np.arange(1, n + 1)
    return np.sqrt(2.0 / (n + 1)) * np.sin(np.outer(i, i) * np.pi / (n + 1))


def _tensor_pairs(kappa: list[np.ndarray], mu: list[np.ndarray | None], shift: float, lo: float,
                  hi: float) -> tuple[np.ndarray, np.ndarray]:
    """Eigenpairs with eigenvalues in [lo, hi] of synthetic.tensor_operator(K, M, shift) whose
    factors share the sine eigenvectors (eigenvalues kappa_d, mu_d; mu None = identity). Index order
    as there: C order, the first dimension varies slowest (Kronecker product left to right)."""
    dims = len(kappa)
    mus = [np.ones_like(k) if m is None else np.asarray(m, dtype=float) for k, m in zip(kappa, mu)]
    idx = np.indices([k.size for k in kappa]).reshape(dims, -1)
    lam = np.zeros(idx.shape[1])
    for d in range(dims):
        term = kappa[d][idx[d]].copy()
        for e in range(dims):
            if e != d:
                term *= mus[e][idx[e]]
        lam += term
    if shift != 0.0:
        prod = np.ones(idx.shape[1])
        for e in range(dims):
            prod *= mus[e][idx[e]]
        lam -= shift * prod
    sel = np.flatnonzero((lam >= lo) & (lam <= hi))
    sel = sel[np.argsort(lam[sel], kind="stable")]
    bases = [_sine_basis(k.size) for k in kappa]
    vec = np.empty((idx.shape[1], sel.size))
    for c, t in enumerate(sel):
        col = bases[0][:, idx[0, t]]
        for d in range(1, dims):
            col = np.kron(col, bases[d][:, idx[d, t]])
        vec[:, c] = col
    return lam[sel], vec


def _prescribed_basis(lam: np.ndarray, *, block: int, complex_: bool, seed: int, grouping: str,
                      permute: bool) -> tuple[np.ndarray, sp.csc_matrix, np.ndarray | None]:
    """Replays synthetic.prescribed_hermitian: the diagonal d, the unitary Q (A = P Q diag(d) Q^H
    P^T) and the permutation p (A = (Q diag(d) Q^H)[p][:, p]; None when not permuted)."""
    n = lam.size
    rng = np.random.default_rng(seed)
    if grouping == "random":
        d = lam[rng.permutation(n)]
    elif grouping == "magnitude":
        d = lam[np.argsort(np.abs(lam), kind="stable")]
    else:
        raise ValueError(f"unknown grouping {grouping!r}")
    # The generator's evaluation order: the offset factor draws first.
    q2 = syn.block_unitary(n, block, block // 2, rng, complex_)
    q1 = syn.block_unitary(n, block, 0, rng, complex_)
    q = (q2 @ q1).tocsc()
    p = rng.permutation(n) if permute else None
    return d, q, p


def _select(d: np.ndarray, lo: float, hi: float) -> np.ndarray:
    sel = np.flatnonzero((d >= lo) & (d <= hi))
    return sel[np.argsort(d[sel], kind="stable")]


def exact_pairs(meta: dict, lo: float, hi: float) -> ReferencePairs | None:
    """The exact eigenpairs (eigenvalues in [lo, hi]) of a synthetic case from its meta.json, or
    None when the case's generator has no eigenvector formula here. The vectors are B-orthonormal
    (orthonormal for B = I) up to rounding."""
    params = meta.get("params") or {}
    gen = params.get("generator")
    if gen == "synthetic.laplacian":
        shape = params["shape"]
        h = params.get("spacing") or [1.0] * len(shape)
        kappa = [syn.second_difference_eigenvalues(n) / hd**2 for n, hd in zip(shape, h)]
        values, vectors = _tensor_pairs(kappa, [None] * len(shape), float(params["shift"]), lo, hi)
        return ReferencePairs(values, vectors, "exact", "Kronecker products of the 1-D sine vectors")
    if gen == "synthetic.stencil_operator":
        f = [syn.stencil_factors(n, int(params["order"])) for n in params["cells"]]
        values, vectors = _tensor_pairs([x[2] for x in f], [x[3] for x in f], float(params["shift"]), lo, hi)
        return ReferencePairs(values, vectors, "exact", "Kronecker products of the 1-D sine vectors")
    if gen == "synthetic.prescribed_hermitian":
        lam = syn.spectrum_preset(params["kind"], int(params["n"]), int(params["spectrum_seed"])).eigenvalues
        d, q, p = _prescribed_basis(lam, block=int(params["block"]), complex_=bool(params["complex"]),
                                    seed=int(params["matrix_seed"]), grouping=params["grouping"], permute=True)
        sel = _select(d, lo, hi)
        vectors = q[:, sel].toarray()
        if p is not None:
            vectors = vectors[p]
        return ReferencePairs(d[sel], vectors, "exact", "columns of the generator's P Q")
    if gen == "synthetic.congruence_pair":
        b_cond = float(params["b_cond"])
        lam = syn.spectrum_preset(params["kind"], int(params["n"]), int(params["spectrum_seed"]),
                                  cond_b=syn.congruence_cond_bound(b_cond)).eigenvalues
        seed = int(params["matrix_seed"])
        complex_ = bool(params["complex"])
        d, q, _ = _prescribed_basis(lam, block=int(params["block"]), complex_=complex_, seed=seed,
                                    grouping=params["grouping"], permute=False)
        rng = np.random.default_rng([seed, 1])
        w = syn.congruence_factor(lam.size, b_cond=b_cond, bandwidth=int(params["bandwidth"]),
                                  complex_=complex_, rng=rng)
        p = rng.permutation(lam.size)
        sel = _select(d, lo, hi)
        rhs = q[:, sel].toarray()
        x = spla.spsolve_triangular(w.tocsr(), rhs, lower=True) if sel.size else rhs
        return ReferencePairs(d[sel], np.asarray(x)[p], "exact", "P W^{-1} Q e_j of the generator")
    return None


def stored_pairs(ref_dir: Path, lo: float, hi: float) -> ReferencePairs | None:
    """The stored reference eigenpairs of a case with eigenvalues in [lo, hi], or None when the
    reference has no eigenvectors."""
    vec_path = Path(ref_dir) / "eigenvectors.npy"
    if not vec_path.is_file():
        return None
    values = np.load(Path(ref_dir) / "eigenvalues.npy")
    info_path = Path(ref_dir) / "ref.json"
    info = json.loads(info_path.read_text()) if info_path.is_file() else {}
    sel = _select(values.real, lo, hi)
    vectors = np.load(vec_path, mmap_mode="r")
    return ReferencePairs(values.real[sel], np.asarray(vectors[:, sel]), "stored",
                          f"{info.get('kind', '?')} reference: {info.get('note', '')}".strip())


def reference_pairs(case_dir: Path, ref_dir: Path, lo: float, hi: float) -> ReferencePairs | None:
    """Exact pairs where the generator is known, else the stored reference vectors, else None."""
    meta_path = Path(case_dir) / "meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.is_file() else {}
    exact = exact_pairs(meta, lo, hi)
    return exact if exact is not None else stored_pairs(ref_dir, lo, hi)

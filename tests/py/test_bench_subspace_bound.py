"""tools/bench/subspace_reference.py and subspace_bound_table.py: the exact eigenvectors recomputed
from the synthetic generators' parameters reproduce the generated matrices (small cases written by
the real generators), the B-inner-product angle, and the tables over a fabricated raw file (the
measurement itself needs the measurement slot)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import scipy.sparse as sp

from tools import case
from tools.bench import subspace_bound_table as table
from tools.bench import subspace_reference as sref
from tools.gen import synthetic as syn


def generated(tmp_path: Path, name: str, make, *args):
    make(name, *args, root=tmp_path)
    c = case.load_case(name, root=tmp_path)
    ref = case.load_ref(name, root=tmp_path)
    return c, np.sort(ref.eigenvalues.real)


def between_levels(w: np.ndarray, first: int, last: int) -> tuple[float, float]:
    """An interval strictly between distinct levels holding the levels first..last (indices into
    the distinct levels of w)."""
    lev, _ = syn.distinct_levels(w)
    lo = 0.5 * (lev[first - 1] + lev[first]) if first > 0 else lev[0] - 1.0
    hi = 0.5 * (lev[last] + lev[last + 1]) if last + 1 < lev.size else lev[-1] + 1.0
    return float(lo), float(hi)


CASES = [
    ("prescribed-real", syn.make_prescribed_case, ("multiplicity", 300, False, 7)),
    ("prescribed-complex", syn.make_prescribed_case, ("multiplicity", 300, True, 8)),
    ("prescribed-magnitude", syn.make_prescribed_case, ("wide-range", 300, False, 5)),
    ("pair-real", syn.make_pair_case, ("multiplicity", 300, False, 9, 1e3)),
    ("pair-complex", syn.make_pair_case, ("zero-cluster", 400, True, 11, 1e2)),
    ("laplacian-cube", syn.make_laplacian_case, ((5, 5, 5), None, 0.05)),
    ("laplacian-aniso", syn.make_laplacian_case, ((6, 5, 4), (1.0, 1.3, 0.8), 0.05)),
    ("stencil", syn.make_memory_case, ((6, 6, 5), 1, 0.02)),
]


@pytest.mark.parametrize("name,make,args", CASES, ids=[c[0] for c in CASES])
def test_exact_pairs_reproduce_the_generated_matrices(tmp_path: Path, name, make, args):
    c, w = generated(tmp_path, name, make, *args)
    # The whole spectrum: B-orthonormal eigenvectors of the stored pencil.
    full = sref.exact_pairs(c.meta, -np.inf, np.inf)
    assert full is not None and full.source == "exact"
    assert full.values.size == c.n
    np.testing.assert_allclose(np.sort(full.values), w, rtol=0, atol=1e-12 * np.max(np.abs(w)))
    assert np.max(sref.backward_errors(c.A, c.B, full.values, full.vectors)) < 1e-13
    v = full.vectors
    gram = v.conj().T @ (v if c.B is None else c.B @ v)
    assert np.max(np.abs(gram - np.eye(c.n))) < 1e-11
    # Three levels near the top (gaps there are large relative to ||A|| in every family, so the
    # dense solver below resolves the subspace): exactly the eigenvalues inside the interval.
    lev, _ = syn.distinct_levels(w)
    lo, hi = between_levels(w, lev.size - 4, lev.size - 2)
    part = sref.exact_pairs(c.meta, lo, hi)
    assert part.values.size == np.count_nonzero((w >= lo) & (w <= hi))
    assert np.all(np.diff(part.values) >= 0)
    assert np.max(sref.backward_errors(c.A, c.B, part.values, part.vectors)) < 1e-13
    # The reference subspace is the exact eigenspace: angle to the dense solver's at rounding level.
    a = c.A.toarray()
    if c.B is None:
        lam, vec = np.linalg.eigh(a)
        b = None
    else:
        import scipy.linalg as sla
        lam, vec = sla.eigh(a, c.B.toarray())
        b = c.B
    inside = (lam >= lo) & (lam <= hi)
    assert np.count_nonzero(inside) == part.values.size
    assert sref.subspace_sin(part.vectors, vec[:, inside], b) < 1e-10


def test_other_generators_have_no_exact_pairs():
    assert sref.exact_pairs({"params": {"generator": "tools.gen.waveguide"}}, 0.0, 1.0) is None
    assert sref.exact_pairs({}, 0.0, 1.0) is None


def test_stored_pairs_select_the_interval(tmp_path: Path):
    vals = np.array([3.0, 1.0, 2.0])
    vecs = np.eye(3)
    case.save_ref("r", vals, kind="solver", note="test", eigenvectors=vecs, root=tmp_path)
    got = sref.stored_pairs(tmp_path / "refs" / "r", 1.5, 3.5)
    assert got.source == "stored" and "solver reference" in got.note
    np.testing.assert_array_equal(got.values, [2.0, 3.0])
    # save_ref sorts the columns with the eigenvalues: eigenvalue 2 belongs to the third unit vector.
    np.testing.assert_array_equal(got.vectors, np.eye(3)[:, [2, 0]])
    case.save_ref("s", vals, kind="solver", root=tmp_path)
    assert sref.stored_pairs(tmp_path / "refs" / "s", 0.0, 4.0) is None


def test_subspace_sin_in_the_b_inner_product():
    t = 0.3
    e = np.eye(4)
    x = (np.cos(t) * e[:, 0] + np.sin(t) * e[:, 1])[:, None]
    assert sref.subspace_sin(x, e[:, [0]]) == pytest.approx(np.sin(t), rel=1e-14)
    assert sref.subspace_sin(x, e[:, [0, 1]]) < 1e-15
    # Scaling of the bases does not matter; the B inner product does.
    assert sref.subspace_sin(5.0 * x, 2.0 * e[:, [0]]) == pytest.approx(np.sin(t), rel=1e-14)
    b = sp.diags([1.0, 4.0, 1.0, 1.0]).tocsr()
    # x = (cos t, sin t): B-angle to e_0 has tan = 2 sin t / cos t.
    expect = np.sin(np.arctan(2.0 * np.tan(t)))
    assert sref.subspace_sin(x, e[:, [0]], b) == pytest.approx(expect, rel=1e-13)
    with pytest.raises(ValueError):
        sref.subspace_sin(e[:, [0, 1]], e[:, [0]])


def fabricated_doc() -> dict:
    group = {"kind": "cluster", "pairs": [0, 1], "unreturned": 1, "lower": 0.9, "upper": 1.1, "dimension": 3,
             "gap": 0.01, "residual": 1e-12, "orthogonality": 1e-15, "sin_bound": 1e-10}
    sub = {"performed": True, "max_sin_bound": 1e-10, "rigorous": True, "residual_norm": "2", "b_min": 1.0,
           "b_min_source": "identity", "note": "", "seconds": 0.02}
    run = {"case": "c1", "returncode": 0, "wall_s": 1.0, "n": 100, "problem": "standard", "complex": False,
           "pairs": 2, "success": True, "certificate": "inertia_counts", "certificate_passed": True,
           "max_backward_error": 1e-15, "time_verify_s": 0.05, "peak_rss_bytes": 1, "groups": [group]}
    runs = []
    for rep in range(2):
        runs.append(run | {"variant": "auto", "rep": rep, "time_total_s": 1.0 + 0.1 * rep, "subspace": sub})
        runs.append(run | {"variant": "off", "rep": rep, "time_total_s": 0.98, "groups": [],
                           "subspace": sub | {"performed": False, "max_sin_bound": None,
                                              "note": "disabled by configuration"}})
    runs.append({"case": "c2", "variant": "auto", "rep": 0, "returncode": 3, "wall_s": 0.1, "stderr": "boom"})
    # A GHEP case whose lambda_min(B) auto only estimates and on proves.
    ghep = run | {"case": "c3", "problem": "generalized_definite", "rep": 0}
    est = sub | {"rigorous": False, "residual_norm": "b_inverse_cg", "b_min_source": "estimate", "max_sin_bound": 1e-6,
                 "seconds": 0.01}
    runs.append(ghep | {"variant": "auto", "time_total_s": 1.0, "subspace": est})
    runs.append(ghep | {"variant": "on", "time_total_s": 1.3,
                        "subspace": est | {"rigorous": True, "b_min_source": "inertia_count", "max_sin_bound": 5e-7,
                                           "seconds": 0.3}})
    runs.append(ghep | {"variant": "off", "time_total_s": 0.99, "groups": [],
                        "subspace": sub | {"performed": False, "max_sin_bound": None}})
    check = {k: group[k] for k in ("kind", "pairs", "unreturned", "dimension", "gap", "residual", "sin_bound")}
    check.update(reference="exact", reference_note="", reference_dimension=3, reference_backward_error=1e-17,
                 true_gap=0.1, measured_sin=1e-12)
    batch = {"host": "node", "cpu": "cpu", "cores": 16, "omp_num_threads": "16", "git_head": "0123456789abcdef",
             "hsolve_version": "hsolve 0.1.0", "preset": "release", "reps": 2, "cases": ["c1", "c2"],
             "started": "2026-10-23T10:00:00+0800", "finished": "2026-10-23T10:05:00+0800"}
    return {"description": "", "batches": [batch], "runs": runs,
            "reference_checks": {"c1": {"groups": [check], "seconds": 0.1}}}


def test_table_from_a_fabricated_raw_file(tmp_path: Path, capsys):
    path = tmp_path / "subspace_bound.json"
    path.write_text(json.dumps(fabricated_doc()))
    assert table.main(str(path)) == 0
    out = capsys.readouterr().out
    assert "提交 `0123456789`" in out and "测量槽 16 核" in out
    assert "界不小于实测夹角的有 1 / 1 组" in out
    assert "中位数 100" in out                       # bound / measured = 1e-10 / 1e-12
    assert "真实间隙 / 界所用的间隙 δ：中位数 10，" in out
    assert "| c1 | HEP | 100 | 2 | inertia_counts | 1.00e-10 | 是 | 2 | identity | 1/0 | 0.020 | 1.050 | 0.980 | 2.0% |" in out
    assert "| c2 | — | — | — | — | 运行失败（返回码 3） |" in out
    assert "| c3 | estimate → inertia_count | 否 → 是 | 1.00e-06 → 5.00e-07 | 0.010 → 0.300 | 1.300 | 0.990 | 30% |" in out
    assert "| c1 | estimate" not in out  # on and auto agree for c1: not in the on table
    assert "| c1 | 0（0, 1 + 1 未返回） | cluster | 3 | 3 | 1.00e-02 | 1.00e-01 |" in out

# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 seuclkzsd and the hsolve contributors
"""Tests for tools/showcase/waveguide_ref.py: the TE/TM family reference of a hollow guide against a
dense QZ solve of the full indefinite pencil, the Sylvester count, and the field sampling helpers."""
import json

import numpy as np
import pytest
import scipy.linalg as sla
import scipy.sparse as sp

from tools import case as cio
from tools.gen import waveguide as wg
from tools.showcase import waveguide_ref as wref


@pytest.fixture(scope="module")
def small_guide(tmp_path_factory):
    root = tmp_path_factory.mktemp("wg")
    spec = wg.CaseSpec(family="waveguide", nx=16)
    wg.write(wg.generate(spec, "wg-small"), root)
    return root


def test_family_reference_matches_dense_pencil(small_guide):
    root = small_guide
    line = wref.write_reference("wg-small", root)
    zeros = (16 - 1) ** 2                             # interior nodes of the 16 x 16 grid
    assert f"{18 + zeros} eigenvalues" in line and f"{zeros} zeros" in line
    ref = cio.load_ref("wg-small", root=root)
    assert ref.info["complete"] and ref.info["kind"] == "solver"
    lo, hi = ref.info["window"]
    assert lo < -wg.wavenumber(50.0) ** 2 + 0.1 and 0 < hi        # the zero cluster lies inside the window
    c = cio.load_case("wg-small", root=root)
    w = sla.eigvals(c.A.toarray(), c.B.toarray())
    w = w[np.isfinite(w)]
    real = w[np.abs(w.imag) <= 1e-9].real
    dense = np.sort(real[(real >= lo) & (real <= hi)])
    assert dense.size == ref.eigenvalues.size == 18 + zeros
    assert np.max(np.abs(dense - ref.eigenvalues)) <= 1e-9
    assert np.count_nonzero(ref.eigenvalues == 0.0) == zeros and np.count_nonzero(ref.eigenvalues < 0) == 18
    fam = json.loads((root / "refs/wg-small/family.json").read_text())
    assert fam["families"]["TE"]["count"] == 12 and fam["families"]["TM"]["count"] == 6
    labels = [m["label"] for m in fam["families"]["TE"]["modes"]]
    assert labels[:2] == ["TE01/TE10", "TE01/TE10"] and "TE11" in labels


def test_rebuild_rejects_another_pencil(small_guide):
    c = cio.load_case("wg-small", root=small_guide)
    c.B = (c.B * (1 + 1e-9)).tocsr()
    with pytest.raises(ValueError, match="differs"):
        wref.rebuild(c)


def test_negative_count_is_sylvester():
    n = 200
    lap = sp.diags([-np.ones(n - 1), 2 * np.ones(n), -np.ones(n - 1)], [-1, 0, 1], format="csr")
    w = 2 - 2 * np.cos(np.arange(1, n + 1) * np.pi / (n + 1))
    for mu in (0.5 * (w[6] + w[7]), 0.5 * (w[120] + w[121])):
        assert wref.negative_count(lap - mu * sp.eye(n))["negative"] == int((w < mu).sum())


def test_locate_pixels_and_centroid_fields(small_guide):
    c = cio.load_case("wg-small", root=small_guide)
    rb = wref.rebuild(c)
    owner = wref.locate_pixels(rb.mesh.nodes, rb.mesh.triangles, rb.spec.a, rb.spec.b, 40, 30)
    assert owner.shape == (30, 40) and np.all(owner >= 0)
    p = rb.mesh.nodes[rb.mesh.triangles[owner[7, 11]]]
    x, y = (11 + 0.5) * rb.spec.a / 40, (7 + 0.5) * rb.spec.b / 30
    assert p[:, 0].min() - 1e-12 <= x <= p[:, 0].max() + 1e-12 and p[:, 1].min() - 1e-12 <= y <= p[:, 1].max() + 1e-12
    # A discrete gradient e_t = D psi interpolates to grad psi: for psi = x (linear), e_t = (1, 0)
    # wherever no boundary edge (dropped by PEC) touches the triangle.
    d = wg.incidence(rb.disc)
    nodes = rb.mesh.nodes[rb.disc.node_dof >= 0]
    psi = np.zeros(rb.disc.num_node_dofs)
    psi[rb.disc.node_dof[rb.disc.node_dof >= 0]] = nodes[:, 0]
    x_edges = np.concatenate([d @ psi, np.zeros(rb.disc.num_node_dofs)])
    field = wref.centroid_fields(rb, x_edges)
    interior = np.all(rb.disc.node_dof[rb.mesh.triangles] >= 0, axis=1)
    assert np.allclose(field[interior], [1.0, 0.0], atol=1e-12)

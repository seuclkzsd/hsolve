"""Tests for tools/showcase/scenarios.py: catalogue integrity, the target resolvers on exact Yee
spectra, and the preparation of a campaign data root from a small source case."""
import json

import numpy as np
import pytest

from tools import case as cio
from tools.gen import yee
from tools.gen.synthetic import distinct_levels
from tools.showcase import scenarios as scn

CONFIG_KEYS = {"method", "zero_filter_tol"}   # every key the catalogue hands hsolve (FORMATS.md §2)


def test_catalogue_is_consistent():
    ids = [s.id for s in scn.SCENARIOS]
    assert len(ids) == len(set(ids))
    for s in scn.SCENARIOS:
        assert s.group in scn.GROUPS
        assert set(scn.hsolve_keys(s, "GHEP")) <= CONFIG_KEYS
        assert scn.hsolve_keys(s, "GHIEP").get("method") is None   # GHIEP keeps method auto
        if isinstance(s.target, str):
            assert s.target in scn.RESOLVERS
        assert (s.source is None) == (s.reference == "generated")
    assert {s.group for s in scn.SCENARIOS} == set(scn.GROUPS)    # every hard scenario has a row
    assert scn.by_id(["zero-cluster"])[0].case == "syn-zero-cluster-real-1e5"
    with pytest.raises(SystemExit):
        scn.by_id(["no-such-scenario"])


def test_method_pin_only_on_definite_problems():
    s = scn.by_id(["lowfreq-null-space"])[0]
    assert scn.hsolve_keys(s, "HEP") == {"method": "shift_invert_lanczos", "zero_filter_tol": scn.ZERO_FILTER_TOL}
    assert scn.hsolve_keys(scn.by_id(["waveguide-square"])[0], "GHIEP") == {}


@pytest.fixture(scope="module")
def cube_spectrum():
    return yee.exact_eigenvalues(yee.YeeGrid((10, 10, 10)))


def test_multiplet_target_holds_whole_3_6_12_fold_levels(cube_spectrum):
    w = cube_spectrum
    t = scn.multiplet_target(w)
    mult = scn.target_multiplicities(w, t)
    assert {3, 6, 12} <= set(mult)
    assert sum(mult) == t["k"]
    d = np.sort(np.abs(w - t["sigma"]))
    assert d[t["k"]] - d[t["k"] - 1] > 1e-6 * t["sigma"]   # decidable: no tie at the boundary
    assert d[t["k"] - 1] < t["sigma"]                      # the zero level is not in the set
    lev, _ = distinct_levels(w)
    assert np.min(np.abs(lev - t["sigma"])) > 0            # sigma is not on a level


def test_on_eigenvalue_targets(cube_spectrum):
    w = cube_spectrum
    t0 = scn.on_eigenvalue_target(w, 20.0)
    lev, _ = scn.physical_levels(w)
    assert t0["sigma"] == t0["eigenvalue"] and t0["sigma"] in lev
    assert t0["eigenvalue"] == lev[np.argmin(np.abs(lev - 20.0))]
    t1 = scn.on_eigenvalue_target(w, 20.0, rel_offset=-1e-13)
    assert t1["eigenvalue"] == t0["eigenvalue"]
    assert abs(t1["sigma"] - t0["sigma"]) == pytest.approx(1e-13 * t0["sigma"], rel=1e-2)
    assert t0["k"] >= 10 and t1["k"] >= 10


def test_interval_and_lowest_targets(cube_spectrum):
    w = cube_spectrum
    t = scn.interval_target(w, first_level=2, count_min=40)
    inside = w[(w >= t["lower"]) & (w <= t["upper"])]
    assert inside.size == t["count"] >= 40
    lev, _ = scn.physical_levels(w)
    assert lev[1] < t["lower"] < lev[2]
    phys = w[w > 0]
    low = scn.lowest_physical_target(phys)
    assert low["sigma"] == 0.0 and low["k"] >= 10
    assert np.sort(phys)[low["k"]] > np.sort(phys)[low["k"] - 1]


def test_prepare_physical_case(tmp_path):
    src_root, root = tmp_path / "src", tmp_path / "root"
    grid = yee.YeeGrid((6, 5, 4), (1.0, 0.8, 0.6))
    yee.make_homogeneous_case("yee-tiny", grid, "generalized", src_root)
    sc = scn.Scenario("t-low", "zero", "t", "tiny-physical", "yee-tiny", "why",
                      hsolve={"zero_filter_tol": 1e-8}, reference="physical", derived=True)
    rec = scn.prepare_one(sc, root, [src_root])
    ref = cio.load_ref("tiny-physical", root=root)
    assert np.all(ref.eigenvalues > 0) and ref.info["complete"]
    assert ref.eigenvalues.size == grid.edge_count - grid.null_space_dimension()
    c = cio.load_case("tiny-physical", root=root)
    assert (root / "cases/tiny-physical/A.npz").is_symlink()
    assert c.config["target"]["sigma"] == 0.0 and not rec["override"]
    assert rec["hsolve_config"] == {"method": "shift_invert_lanczos", "zero_filter_tol": 1e-8}
    assert rec["target_multiplicities"] and sum(rec["target_multiplicities"]) == c.config["target"]["k"]
    # A linked scenario with a resolved target: the case is a link, the target an override.
    sc2 = scn.Scenario("t-on", "near-singular", "t", "yee-tiny", "yee-tiny", "why", target="sigma-on-eigenvalue")
    rec2 = scn.prepare_one(sc2, root, [src_root])
    assert (root / "cases/yee-tiny").is_symlink() and (root / "refs/yee-tiny").is_symlink()
    assert rec2["override"] and set(rec2["target"]) == {"mode", "sigma", "k"}
    assert rec2["target_info"]["eigenvalue"] == rec2["target"]["sigma"]
    json.dumps(rec2)   # the resolved record is plain JSON
    with pytest.raises(FileExistsError):   # an unrelated directory is never replaced
        scn._symlink(src_root / "cases/yee-tiny", root / "cases/tiny-physical")

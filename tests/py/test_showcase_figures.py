"""Smoke tests of tools/showcase/figures.py on synthetic raw data (skipped without matplotlib, which
the project environment does not ship; any Python with numpy + matplotlib runs them)."""
import json

import numpy as np
import pytest

pytest.importorskip("matplotlib")

from tools.showcase import figures  # noqa: E402
from test_showcase_tables import _doc, _run  # noqa: E402


@pytest.fixture
def raw(tmp_path):
    runs = []
    for rep in range(2):
        cert = {"performed": True, "passed": True, "method": "exact", "count_inertia": 4, "count_found": 4,
                "lower": 0.5, "upper": 2.5}
        runs.append(_run("hsolve", rep, True, 1.0, eigenvalues=[1.0, 1.0, 2.0, 2.0],
                         report={"certificate": cert, "candidate_source": "iterative"}))
        runs.append(_run("slepc-default", rep, False, 2.0, outcome=["missed"], missing=[2.0],
                         eigenvalues=[1.0, 1.0, 2.0, 3.0]))
        runs.append(_run("slepc-tuned", rep, True, 1.5, eigenvalues=[1.0, 1.0, 2.0, 2.0]))
    doc = _doc("te-tm-pairs-box", runs)
    doc["scenario"]["target"] = {"mode": "nearest", "sigma": 1.5, "k": 4}
    doc["reference"]["eigenvalues"] = [0.2, 1.0, 1.0, 2.0, 2.0, 3.0, 3.0]
    (tmp_path / "te-tm-pairs-box.json").write_text(json.dumps(doc))
    return tmp_path


@pytest.mark.parametrize("name", ["scenarios", "correctness", "certificate", "hero"])
def test_campaign_figures(raw, tmp_path, name):
    out = tmp_path / "img"
    paths = figures.make(name, out, raw_dir=raw, phys_dir=tmp_path / "no-physics")
    assert [p.suffix for p in paths] == [".png", ".svg"]
    assert all(p.stat().st_size > 1000 for p in paths)
    assert "<svg" in paths[1].read_text()[:400]


def test_scaling_figure_from_committed_data(tmp_path):
    paths = figures.make("thread_scaling", tmp_path)
    assert paths[0].read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_field_colormap_is_one_hue_light_to_dark():
    cmap = figures.field_cmap()
    lum = [np.dot(cmap(x)[:3], [0.2126, 0.7152, 0.0722]) for x in np.linspace(0, 1, 11)]
    assert all(a > b for a, b in zip(lum, lum[1:]))

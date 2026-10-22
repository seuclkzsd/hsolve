"""Tests for tools/showcase/tables.py and the pure helpers of tools/showcase/campaign.py: verdicts and
failure classes from raw runs, the generated page regions, and the merged tuned-profile file."""
import json

import pytest

from tools.showcase import campaign, tables


def _run(solver, rep, valid, t, outcome=(), missing=(), spurious=0, reasons=(), stderr="", **kw):
    ev = {"verdict": "pass" if valid else "fail", "reasons": list(reasons), "status": "complete" if valid else "incomplete",
          "certified": True, "expected": 10, "found": 10 - len(missing), "missing": list(missing),
          "boundary_deficit": 0, "spurious": spurious, "unmatched": spurious, "distinct_returned": 10,
          "duplicates": 0, "rejected_pairs": 0, "max_backward_error": 1e-14, "max_eig_scaled_error": 1e-16,
          "max_subspace_angle": None}
    run = {"solver": solver, "rep": rep, "valid": valid, "solver_s": t, "wall_s": None if t is None else t + 1,
           "peak_rss_gib": 1.0,
           "solver_peak_bytes": 2**30, "pairs": 10, "why": list(reasons), "evaluation": ev, "outcome": list(outcome),
           "report": {}, "stderr_tail": stderr, "solver_s_scope": "x"}
    run.update(kw)
    return run


def _doc(sid, runs, target=None, dtype="float64"):
    rec = {"id": sid, "group": "multiplicity", "group_label": "重特征值", "title": f"title {sid}", "why": "w",
           "case": "yee-bloch-1e4" if dtype == "complex128" else "case-x", "n": 1000, "problem": "HEP", "dtype": dtype,
           "target": target or {"mode": "nearest", "sigma": 1.5, "k": 10}, "target_info": {},
           "target_multiplicities": [2, 2, 3, 3], "hsolve_config": {"method": "shift_invert_lanczos"}}
    return {"scenario": rec, "started": "2026-10-22T22:00:00",
            "conditions": {"host": "c004", "cpu": "Xeon", "cores": "16-31", "mem_gb": 32.0, "reps": 3,
                           "git_commit": "abcdef1234", "hsolve_md5": "0123456789abcdef", "slepc_version": "3.26.0"},
            "reference": {"kind": "discrete-exact", "complete": True, "window": None}, "runs": runs}


@pytest.fixture
def raw(tmp_path):
    runs = []
    for rep in range(3):
        runs.append(_run("hsolve", rep, True, 2.0 + 0.1 * rep,
                         report={"certificate": {"performed": True, "passed": True, "method": "exact",
                                                 "count_inertia": 10, "count_found": 10},
                                 "candidate_source": "iterative"}))
        runs.append(_run("slepc-default", rep, False, 4.0, outcome=["missed"], missing=[1.25],
                         reasons=["completeness incomplete: 1 missing"], config="1x16", config_scope="default"))
        runs.append(_run("slepc-tuned", rep, True, 3.0, config="4x4", config_scope="case"))
    (tmp_path / "multiplet-cube.json").write_text(json.dumps(_doc("multiplet-cube", runs)))
    err = "Traceback ...\nbaseline_slepc: complex MUMPS LU does not provide inertia for spectrum slicing\n"
    runs2 = [_run("hsolve", 0, True, 1.0), _run("slepc-default", 0, False, None, outcome=["error"], stderr=err, pairs=None),
             _run("slepc-tuned", 0, False, None, outcome=["error"], stderr=err, pairs=None)]
    (tmp_path / "bloch-interval.json").write_text(json.dumps(
        _doc("bloch-interval", runs2, {"mode": "interval", "lower": 1.0, "upper": 2.0}, "complex128")))
    (tmp_path / "slepc-probe.json").write_text(json.dumps({"case": "yee-bloch-1e4", "attempts": [
        {"pc_type": "cholesky", "status": "error", "message": "error code 56\nMUMPS Cholesky Hermitian not supported"}]}))
    return tmp_path


def test_summary_verdicts_and_speedups(raw):
    s = tables.build_summary(raw)
    ids = [r["id"] for r in s["scenarios"]]
    assert ids == ["multiplet-cube", "bloch-interval"]          # catalogue order, not file order
    r = s["scenarios"][0]
    assert r["solvers"]["hsolve"]["correct"] and r["solvers"]["hsolve"]["time_s"] == pytest.approx(2.1)
    d = r["solvers"]["slepc-default"]
    assert d["verdict"] == "failed" and d["outcomes"] == {"missed": 3} and d["max_missing"] == 1
    assert r["speedup_vs"] == {"slepc-tuned": pytest.approx(3.0 / 2.1)}   # only where both are correct
    assert r["solvers"]["hsolve"]["certificate"]["passed_runs"] == 3
    assert s["correct_counts"]["hsolve"] == {"correct": 2, "scenarios": 2}
    b = s["scenarios"][1]
    assert b["slepc_probe"][0]["status"] == "error"
    assert "does not provide inertia" in b["solvers"]["slepc-tuned"]["error"]


def test_rendering_and_regions(raw):
    s = tables.build_summary(raw)
    sec = tables.scenario_sections(s)
    assert "**错误** 0/3：漏解 1 个" in sec["scenario-table"] and "不支持 0/1" in sec["scenario-table"]
    assert "含 2/3 重" in sec["scenario-table"]
    assert "hsolve 2/2" in sec["scenario-table"]
    assert "1.43×" in sec["speed-table"] and "该算例的调优配置" in sec["speed-table"]
    assert "直接调用 SLEPc" in sec["failure-details"]
    assert "hsolve **2/2**" in sec["headline"] and "漏解 1 个（1 个：title multiplet-cube）" in sec["headline"]
    assert "1 个更快（1.43–1.43×）" in sec["headline"]
    assert "c004" in sec["limitations"] and "GHIEP" in sec["limitations"]
    page = "# t\n<!-- BEGIN GENERATED: speed-table -->\nold\n<!-- END GENERATED: speed-table -->\ntail\n"
    new = tables.replace_regions(page, {"speed-table": sec["speed-table"]})
    assert "old" not in new and new.endswith("<!-- END GENERATED: speed-table -->\ntail\n")
    assert tables.replace_regions(new, {"speed-table": sec["speed-table"]}) == new   # idempotent
    with pytest.raises(ValueError):
        tables.replace_regions(page, {"scenario-table": "x"})


def test_outcome_classes():
    ev = {"missing": [], "boundary_deficit": 0, "status": "complete", "spurious": 4, "rejected_pairs": 1,
          "duplicates": 0}
    assert campaign.outcome({"valid": True}, ev) == []
    assert campaign.outcome({"valid": False, "pairs": 10, "rc": 0}, ev) == ["spurious", "residual"]
    assert campaign.outcome({"valid": False, "rc": 1}, None) == ["error"]
    miss = dict(ev, spurious=0, rejected_pairs=0, missing=[3.0])
    assert campaign.outcome({"valid": False, "pairs": 9, "rc": 0}, miss) == ["missed"]
    assert campaign.outcome({"valid": False, "pairs": 0, "rc": 0}, dict(miss, missing=[])) == ["empty"]


def test_merge_profiles_later_sources_win(tmp_path):
    def profile(name, opts, cores=16):
        return {"scope": "case", "name": name, "mode": "nearest", "cores": cores, "target": None,
                "config": {"ranks": 4, "threads": 4, "bind": "core", "options": opts}}
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(json.dumps({"schema_version": 1, "profiles": [profile("x", {"eps_ncv": "2k"}), profile("y", {}),
                                                              profile("x", {}, cores=2)]}))
    b.write_text(json.dumps({"schema_version": 1, "profiles": [profile("x", {"eps_ncv": "3k"})]}))
    doc = campaign.merge_profiles(((a, "base"), (b, "fix")))
    got = {p["name"]: p for p in doc["profiles"]}
    assert set(got) == {"x", "y"} and got["x"]["config"]["options"] == {"eps_ncv": "3k"}
    assert got["x"]["source"].endswith("b.json") and [s["profiles"] for s in doc["sources"]] == [2, 1]


def test_raw_records_are_written_home_relative():
    text = '{"slepc_env": "/share/home/u/envs/ref", "cmd": ["/share/home/u/envs/ref/bin/mpiexec", "/share/home/uv/x"]}'
    out = campaign.home_relative(text, "/share/home/u")
    assert out == '{"slepc_env": "~/envs/ref", "cmd": ["~/envs/ref/bin/mpiexec", "/share/home/uv/x"]}'
    assert json.loads(out)
    assert campaign.home_relative(text, "/") == text

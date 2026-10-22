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
    cube_title = next(c.title for c in tables.scn.SCENARIOS if c.id == "multiplet-cube")   # catalogue wording wins
    assert "hsolve **2/2**" in sec["headline"] and f"未通过 2 个场景：不支持（库报错） 1 个" in sec["headline"]
    assert f"漏解 1 个（{cube_title}）" in sec["headline"]
    assert "1 个场景 hsolve 更快（1.43–1.43×）" in sec["headline"]
    assert "c004" in sec["limitations"] and "GHIEP" in sec["limitations"]
    page = "# t\n<!-- BEGIN GENERATED: speed-table -->\nold\n<!-- END GENERATED: speed-table -->\ntail\n"
    new = tables.replace_regions(page, {"speed-table": sec["speed-table"]})
    assert "old" not in new and new.endswith("<!-- END GENERATED: speed-table -->\ntail\n")
    assert tables.replace_regions(new, {"speed-table": sec["speed-table"]}) == new   # idempotent
    with pytest.raises(ValueError):
        tables.replace_regions(page, {"scenario-table": "x"})


def test_readme_quotes_count_from_the_summary(raw):
    s = tables.build_summary(raw)
    assert s["run_counts"]["hsolve"] == {"runs": 4, "valid": 4, "max_backward_error": pytest.approx(1e-14)}
    sec = tables.readme_sections(s)
    facts = sec["readme-facts"]
    assert "hsolve 2/2，SLEPc 常规用法 0/2，SLEPc 逐例调优 1/2" in facts
    assert "hsolve 4/4 次有效" in facts
    assert "每次都返回 10 个特征对，却漏掉其中 1 个" in facts and "惯性计数 10 个 = 找到 10 个" in facts
    assert "中位求解时间之比为 1.43–1.43（每个场景都是 hsolve 更快）" in facts
    assert "1.0e-14" in facts and "c004" in facts
    table = sec["readme-table"].splitlines()
    assert len(table) == 4 and "**不支持**（PETSc 报错）" in table[3] and "正确 3/3，2.1 s" in table[2]
    assert "hsolve 2/2, SLEPc default use 0/2, SLEPc tuned per case 1/2" in sec["readme-facts-en"]


def test_silent_failures_are_counted_and_quoted():
    runs = [_run("hsolve", 0, True, 1.0), _run("slepc-default", 0, False, 2.0, outcome=["missed"], missing=[1.0],
                                              report={"success": True}),
            _run("slepc-default", 1, False, 2.0, outcome=["residual"], report={"success": False})]
    e = tables.summarize_solver([r for r in runs if r["solver"] == "slepc-default"])
    assert e["silent_failures"] == 1
    s = {"scenarios": [{"title": "t", "short": "s", "solvers": {"slepc-default": e}}]}
    assert tables.silent_failures(s) == {"slepc-default": (1, ["t"])}
    assert tables.silent_failures(s, key="short") == {"slepc-default": (1, ["s"])}


def test_campaign_tuning_is_reported(raw, tmp_path):
    tf = tmp_path / "elsewhere" / "tuning.json"
    tf.parent.mkdir()
    tf.write_text(json.dumps({"tunings": {"multiplet-cube": {"configurations": 31, "trials": 70, "valid_trials": 0,
                                                             "best": None}}}))
    s = tables.build_summary(raw, tuning_file=tf)
    r = s["scenarios"][0]
    assert tables.tuned_source(r) == "本次逐例调优 31 种配置、70 次试验均未通过评测，沿用该算例的调优配置"
    lim = tables.limitations(s)
    assert "1 个场景（" in lim and "没有找到通过评测的配置" in lim


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


def test_merge_profiles_scope_filter_and_tuning_record(tmp_path):
    def profile(scope, name):
        return {"scope": scope, "name": name, "mode": "nearest", "cores": 16, "target": None,
                "config": {"ranks": 1, "threads": 16, "bind": "none", "options": {}}}
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps({"schema_version": 1, "profiles": [profile("class", "HEP/nearest")]}))
    b.write_text(json.dumps({"schema_version": 1, "profiles": [profile("class", "HEP/nearest"),
                                                              profile("case", "cube")]}))
    doc = campaign.merge_profiles(((a, "base"), (b, "showcase", ("case",)), (tmp_path / "missing.json", "none")))
    assert [(p["scope"], p["name"], p["source"].endswith(n)) for p, n in zip(doc["profiles"], ("b.json", "a.json"))] \
        == [("case", "cube", True), ("class", "HEP/nearest", True)]
    assert [s["profiles"] for s in doc["sources"]] == [1, 1, 0]
    trials = [{"label": "1x16", "valid": False, "why": "completeness incomplete"},
              {"label": "1x16 eps_ncv=3k", "valid": True, "why": None},
              {"label": "1x16 eps_ncv=3k", "valid": True, "why": None}]
    rec = campaign.tuning_record("multiplet-cube", {"case": "cube", "mode": "nearest", "trials": trials,
                                                     "best": "1x16 eps_ncv=3k", "best_median_s": 4.0,
                                                     "default_valid": False, "default_median_s": 3.0})
    assert (rec["trials"], rec["valid_trials"], rec["configurations"]) == (3, 2, 2)
    assert rec["best_median_s"] == 4.0 and rec["invalid_reasons"] == ["completeness incomplete"]


def test_raw_records_are_written_home_relative():
    text = '{"slepc_env": "/share/home/u/envs/ref", "cmd": ["/share/home/u/envs/ref/bin/mpiexec", "/share/home/uv/x"]}'
    out = campaign.home_relative(text, "/share/home/u")
    assert out == '{"slepc_env": "~/envs/ref", "cmd": ["~/envs/ref/bin/mpiexec", "/share/home/uv/x"]}'
    assert json.loads(out)
    assert campaign.home_relative(text, "/") == text


def test_reference_excerpt_keeps_levels_and_nearest_values():
    from types import SimpleNamespace
    import numpy as np
    w = np.concatenate([np.zeros(5000), [3.0, 3.0, 4.0, 6.0, 6.0, 6.0, 9.0]])
    ref = SimpleNamespace(eigenvalues=w, info={"kind": "discrete-exact", "complete": True, "window": None})
    ex = campaign.reference_excerpt(ref, {"mode": "nearest", "sigma": 4.0, "k": 5}, limit=10)
    # radius 2 x (5th nearest distance 2) = 4: the zero level is in range, 9.0 is not
    assert ex["truncated"] and ex["levels"] == [[0.0, 5000], [3.0, 2], [4.0, 1], [6.0, 3]]
    assert ex["eigenvalues"] == [0.0] * 4 + [3.0, 3.0, 4.0, 6.0, 6.0, 6.0]
    assert campaign.reference_levels([1.0, 1.0 + 1e-12, 2.0]) == [[1.0, 2], [2.0, 1]]

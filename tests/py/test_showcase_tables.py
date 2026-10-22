"""Tests for tools/showcase/tables.py and the pure helpers of tools/showcase/campaign.py: verdicts and
failure classes from raw runs, the generated page regions, the tuning records and the merged
tuned-profile file, and that the committed tables and pages match the committed raw data."""
import json

import pytest

from tools.showcase import campaign, figures, tables


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
    runs2 = [_run("hsolve", 0, True, 1.0),
             _run("slepc-default", 0, False, None, outcome=["error"], stderr=err, pairs=None, evaluation=None),
             _run("slepc-tuned", 0, False, None, outcome=["error"], stderr=err, pairs=None, evaluation=None)]
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
    assert tables.tuned_source(r) == "本次逐例调优（31 种配置、70 次试验）没有找到通过评测的配置，沿用该算例的调优配置"
    r["slepc_tuning"] = {**r["slepc_tuning"], "flaky": True, "flaky_confirm_reps": 20}
    assert "按随机失败的情形每个候选确认 20 次" in tables.tuned_source(r)
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
    text = '{"slepc_env": "/home/user/envs/ref", "cmd": ["/home/user/envs/ref/bin/mpiexec", "/home/userx/x"]}'
    out = campaign.home_relative(text, "/home/user")
    assert out == '{"slepc_env": "~/envs/ref", "cmd": ["~/envs/ref/bin/mpiexec", "/home/userx/x"]}'
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


def test_null_space_answers_are_their_own_class_and_not_silent():
    # sigma = 0 on a pencil with a null space, judged against the physical spectrum: SLEPc returns
    # exact zero eigenpairs (as the query literally asks); hsolve filtered them by inertia.
    ev = {"missing": [27.4] * 10, "boundary_deficit": 0, "status": "incomplete", "spurious": 10,
          "rejected_pairs": 0, "duplicates": 0}
    zeros = {"valid": False, "pairs": 10, "rc": 0, "claimed_success": True, "eigenvalues": [1e-16] * 10}
    assert campaign.outcome(zeros, ev) == ["missed", "spurious"]             # no null level: plain spurious
    assert campaign.outcome(zeros, ev, null_tol=2.4e-4) == ["nullspace"]
    strays = dict(zeros, eigenvalues=[1e-16] * 5 + [31.0] * 5)               # genuine strays stay spurious
    assert campaign.outcome(strays, ev, null_tol=2.4e-4) == ["missed", "spurious"]
    assert campaign.null_level({"reference": "physical"}, 2.4e4) == pytest.approx(2.4e-4)
    assert campaign.null_level({"reference": "source"}, 2.4e4) is None
    run = _run("slepc-default", 0, False, 6.0, outcome=["nullspace"], missing=[27.4] * 10, spurious=10,
               reasons=["10 spurious eigenvalue(s) absent from the complete reference"], claimed_success=True,
               eigenvalues=[1e-16] * 10, report={"success": True})
    assert not tables.silent(run) and tables.silent(dict(run, outcome=["missed"]))
    doc = _doc("lowfreq-null-space", [_run("hsolve", 0, True, 19.0), run])
    doc["scenario"]["reference"] = "physical"
    doc["norms"] = {"scale": 2.4e4}
    e = tables.summarize_scenario(doc, None)["solvers"]["slepc-default"]
    assert e["outcomes"] == {"nullspace": 1} and e["silent_failures"] == 0 and e["max_spurious"] == 10
    assert tables.failure_text(e) == "返回零空间模 10 个"
    assert figures.failure_short(e) == "10 null-space modes"


def test_failure_details_show_the_solvers_own_claim():
    reasons = ["solver claims no success", "3 of 21 pairs have backward error > tol=1e-10",
               "completeness incomplete: 7 missing", "x", "y"]
    runs = [_run("hsolve", 0, True, 1.0)] + [
        _run("slepc-default", rep, False, 4.0, missing=[1.25], claimed_success=False, reasons=reasons)
        for rep in range(3)]
    s = {"scenarios": [tables.summarize_scenario(_doc("multiplet-cube", runs), None)]}
    details = tables.failure_details(s)
    assert "求解器自报成功 0/3 次" in details and "solver claims no success" not in details
    assert "completeness incomplete: 7 missing" in details and "；y" in details   # not cut to three reasons


def test_tuned_column_labels_say_what_was_tuned_for():
    def row(**tuned):
        runs = [_run("hsolve", 0, True, 1.0), _run("slepc-tuned", 0, False, 2.0, **tuned)]
        return tables.summarize_scenario(_doc("sigma-on-eigenvalue", runs), None)
    cases = {"case": dict(config="4x4/core eps_nev=k+2", config_scope="case", profile_for_target=True),
             "other-target": dict(config="4x4/core eps_nev=k+2", config_scope="case", profile_for_target=False),
             "class": dict(config="4x4/core eps_nev=k+2", config_scope="class"),
             "default": dict(config="1x16", config_scope="class")}      # a class profile that is the default
    for kind, tuned in cases.items():
        r = row(**tuned)
        assert tables.tuned_kind(r) == kind
        r["tuned_kind"] = kind
        assert tables.tuned_source(r) == tables.TUNED_LABELS[kind]
    s = {"scenarios": [dict(row(**cases["default"]), tuned_kind="default")], "hosts": ["c004"]}
    assert [r["id"] for r in tables.untuned_rows(s)] == ["sigma-on-eigenvalue"]
    assert "默认配置（无该算例的调优配置）" in tables.limitations(s)


def test_a_row_must_have_run_its_scenarios_tuned_configuration(raw, tmp_path):
    tf = tmp_path / "tuning.json"
    tf.write_text(json.dumps({"tunings": {"multiplet-cube": {"configurations": 3, "trials": 5, "valid_trials": 4,
                                                             "best": "1x16 eps_nev=3k"}}}))
    with pytest.raises(ValueError, match="re-run the campaign row"):
        tables.build_summary(raw, tuning_file=tf)                      # the raw tuned runs used 4x4


def _tune_doc(case, best):
    trials = [{"id": 0, "phase": "default", "label": "1x16", "valid": False, "why": "7 missing", "solver_s": 4.5},
              {"id": 1, "phase": "accuracy", "label": "1x16 eps_nev=3k", "valid": best is not None, "why": None,
               "solver_s": 11.0}]
    cfg = {"ranks": 1, "threads": 16, "bind": "none", "options": {"eps_nev": "3k"}}
    target = {"mode": "nearest", "sigma": 4.0, "k": 21}
    return {"case": case, "mode": "nearest", "ncores": 16, "target_override": target, "target": target, "tag": "t",
            "date": "d", "host": "h", "best": best, "best_config": cfg if best else None, "default_median_s": 4.5,
            "default_valid": False, "best_median_s": 11.0 if best else None,
            "speedup_vs_default": 0.4 if best else None, "trials": trials,
            "confirmation": {"configs": {"1x16 eps_nev=3k": {"median_s": 11.0, "n": 5, "phases": {}}}}}


def test_tuning_records_give_profiles_and_a_summary(tmp_path):
    (tmp_path / "multiplet-cube.json").write_text(json.dumps(_tune_doc("cube", "1x16 eps_nev=3k")))
    (tmp_path / "lowfreq-null-space.json").write_text(json.dumps(_tune_doc("phys", None)))
    (tmp_path / "unfinished.json").write_text(json.dumps({"case": "x", "in_progress": True, "trials": []}))
    tunings = campaign.load_tunings(tmp_path)
    assert sorted(tunings) == ["lowfreq-null-space", "multiplet-cube"]
    prof = campaign.showcase_profiles(tunings)
    assert [(p["name"], p["config"]["options"], p["tuned"]["scenario"]) for p in prof["profiles"]] \
        == [("cube", {"eps_nev": "3k"}, "multiplet-cube")]
    summ = campaign.tuning_summary(tunings)["tunings"]
    assert summ["multiplet-cube"]["record"] == "results/showcase/tuning/multiplet-cube.json"
    assert [(t["phase"], t["label"], t["valid"]) for t in summ["multiplet-cube"]["trial_list"]] \
        == [("default", "1x16", False), ("accuracy", "1x16 eps_nev=3k", True)]
    assert summ["lowfreq-null-space"]["best"] is None and summ["lowfreq-null-space"]["valid_trials"] == 0
    with pytest.raises(ValueError, match="both tune case cube"):
        campaign.showcase_profiles({"a": _tune_doc("cube", "1x16 eps_nev=3k"), "b": _tune_doc("cube", "1x16 eps_nev=3k")})


def test_a_random_failure_in_the_campaign_is_found_for_the_tuning(tmp_path):
    runs = [_run("slepc-tuned", 0, True, 8.2, config="4x4 eps_nev=3k"),
            _run("slepc-tuned", 1, False, 8.1, config="4x4 eps_nev=3k"),
            _run("slepc-default", 0, False, 4.5, config="1x16"), _run("slepc-default", 1, True, 4.5, config="1x16")]
    (tmp_path / "multiplet-cube.json").write_text(json.dumps(_doc("multiplet-cube", runs)))
    seen = campaign.campaign_random_failure("multiplet-cube", tmp_path)
    assert seen["config"] == "4x4 eps_nev=3k" and (seen["valid_runs"], seen["runs"]) == (1, 2)
    assert seen["record"] == "results/showcase/raw/multiplet-cube.json" and seen["host"] == "c004"
    steady = [dict(r, valid=False) for r in runs]                     # failing every time is not random
    (tmp_path / "multiplet-cube.json").write_text(json.dumps(_doc("multiplet-cube", steady)))
    assert campaign.campaign_random_failure("multiplet-cube", tmp_path) is None
    assert campaign.campaign_random_failure("no-record", tmp_path) is None


def test_ratios_near_one_are_reported_as_comparable(raw):
    s = tables.build_summary(raw)
    cube = s["scenarios"][0]
    cube["speedup_vs"] = {"slepc-tuned": 1.004}
    s["scenarios"].append({**cube, "id": "x", "title": "slow one", "short": "slow", "speedup_vs": {"slepc-tuned": 0.6}})
    n, lo, hi, slower, same = tables.speed_range(s, "slepc-tuned")
    assert (n, slower, same) == (2, ["slow one 0.60×"], [f"{cube['title']} 1.00×"])
    head = tables.headline(s)
    assert "1 个场景相当（1.00–1.00×，相差不到 3%）" in head and "1 个场景 hsolve 更慢（0.60–0.60×）" in head
    assert "hsolve 更快" not in head.split("SLEPc 逐例调优与 hsolve")[1].split("\n")[0]


def test_same_target():
    near = {"mode": "nearest", "sigma": 50.1, "k": 10}
    assert campaign.same_target(near, dict(near, k=12)) and not campaign.same_target(near, dict(near, sigma=52.8))
    box = {"mode": "interval", "lower": 40.0, "upper": 200.0}
    assert campaign.same_target(box, dict(box)) and not campaign.same_target(box, near)
    assert not campaign.same_target(None, near)


def test_correctness_cells_wrap_long_status_texts():
    assert figures.wrap_status("3/3 correct") == ["3/3 correct"]
    lines = figures.wrap_status("missed 10, 10 spurious, error exit")
    assert lines == ["missed 10, 10 spurious,", "error exit"]
    assert all(len(x) <= figures.CELL_CHARS for x in lines)
    assert figures.wrap_status("not supported (library error)") == ["not supported (library error)"]


def test_committed_tables_pages_and_quotes_match_the_raw_data():
    # results/showcase/scenarios.{json,md}, the generated regions of docs/showcase/*.md and the README
    # quotes in results/showcase/README.md, regenerated from results/showcase/raw/ and compared
    assert tables.main(["--check"]) == 0

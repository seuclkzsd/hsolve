# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 seuclkzsd and the hsolve contributors
"""Tests for the one-solver re-measurement: the campaign's solver filter (run order, command line)
and tools/showcase/recheck.py (the comparison of new hsolve records with the committed ones)."""
import json

import pytest

from tools.showcase import campaign, recheck


def test_solver_order_rotates_and_filters():
    assert campaign.solver_order(0) == ("hsolve", "slepc-default", "slepc-tuned")
    assert campaign.solver_order(1) == ("slepc-default", "slepc-tuned", "hsolve")
    assert campaign.solver_order(2) == ("slepc-tuned", "hsolve", "slepc-default")
    assert campaign.solver_order(3) == campaign.solver_order(0)
    # a filter keeps the rotation of the solvers it keeps
    assert campaign.solver_order(1, ("hsolve", "slepc-tuned")) == ("slepc-tuned", "hsolve")
    assert [campaign.solver_order(r, ("hsolve",)) for r in range(3)] == [("hsolve",)] * 3


def test_run_accepts_only_known_solvers(capsys):
    with pytest.raises(SystemExit):
        campaign.main(["run", "--scenario", "x", "--solvers", "petsc"])
    assert "invalid choice" in capsys.readouterr().err


def _run(rep, t, valid=True, cert=None, version="1.0.0", phases=None, subspace=None, **kw):
    cert = cert if cert is not None else {"performed": True, "passed": True, "rigorous": True, "method": "exact",
                                          "count_inertia": 10, "count_found": 10, "note": ""}
    ph = phases or {"analysis_s": 0.1, "numeric_s": 0.5, "factorizations": 2, "solves": 100, "solve_s": 0.2,
                    "iterate_s": 0.4 * t, "verify_s": 0.1 * t}
    report = {"version": version, "candidate_source": "iterative", "certificate": cert,
              "time_certificate_s": 0.2 * t}
    if subspace is not None:
        report["subspace"] = {"performed": True, "seconds": subspace}
    run = {"solver": "hsolve", "rep": rep, "valid": valid, "solver_s": t, "phases": ph, "report": report,
           "solver_peak_bytes": 2 * 1024 ** 3, "outcome": [] if valid else ["missed"],
           "why": [] if valid else ["completeness incomplete: 1 missing"],
           "evaluation": {"max_backward_error": 1e-13}}
    run.update(kw)
    return run


def _doc(sid, runs, commit, host="c005", slepc=True):
    rec = {"id": sid, "title": f"title {sid}", "case": "case-x", "n": 1000, "problem": "GHEP", "dtype": "float64",
           "target": {"mode": "nearest", "sigma": 1.0, "k": 10}, "hsolve_config": {"method": "shift_invert_lanczos"},
           "override": True, "timeout_s": 900, "reps": 3, "reference": "source"}
    if slepc:   # the committed records hold the SLEPc runs too: they are not compared
        runs = runs + [{"solver": "slepc-tuned", "rep": 0, "valid": True, "solver_s": 9.0}]
    return {"scenario": rec, "started": "2026-10-23T02:00:00", "finished": "2026-10-23T02:01:00",
            "conditions": {"host": host, "cpu": "Xeon", "cores": "16-31", "ncores": 16, "mem_gb": 32.0, "reps": 3,
                           "source_commit": commit, "git_commit": commit, "hsolve_binary": "build/release/hsolve",
                           "hsolve_md5": commit * 4, "hsolve_build": "hsolve x"},
            "runs": runs}


@pytest.fixture
def dirs(tmp_path):
    base, new = tmp_path / "raw", tmp_path / "recheck"
    base.mkdir()
    new.mkdir()
    # same speed, slower (iteration grew), invalid in one repetition with a changed certificate
    (base / "a.json").write_text(json.dumps(_doc("a", [_run(r, 2.0 + 0.01 * r, version="0.1.0") for r in range(3)],
                                                 "b9aadc4")))
    (new / "a.json").write_text(json.dumps(_doc("a", [_run(r, 2.02, subspace=0.01) for r in range(3)], "47d03dc",
                                                 slepc=False)))
    (base / "b.json").write_text(json.dumps(_doc("b", [_run(r, 1.0, version="0.1.0") for r in range(3)], "b9aadc4")))
    slow = {"analysis_s": 0.1, "numeric_s": 0.5, "factorizations": 3, "solves": 150, "solve_s": 0.3,
            "iterate_s": 0.8, "verify_s": 0.1}
    (new / "b.json").write_text(json.dumps(_doc("b", [_run(r, 1.4, phases=slow) for r in range(3)], "47d03dc",
                                                 slepc=False)))
    (base / "c.json").write_text(json.dumps(_doc("c", [_run(r, 3.0, version="0.1.0") for r in range(3)], "b9aadc4")))
    miss = {"performed": True, "passed": False, "rigorous": True, "method": "exact", "count_inertia": 10,
            "count_found": 9, "note": ""}
    (new / "c.json").write_text(json.dumps(_doc("c", [_run(0, 2.0), _run(1, 2.0, valid=False, cert=miss),
                                                      _run(2, 2.0)], "47d03dc", slepc=False)))
    (base / "d.json").write_text(json.dumps(_doc("d", [_run(0, 1.0)], "b9aadc4")))   # not re-measured
    (base / "slepc-probe.json").write_text(json.dumps({"case": "x", "attempts": []}))
    return base, new


def test_rows_compare_validity_time_phases_and_certificate(dirs):
    base, new = dirs
    doc = recheck.build(new, base)
    rows = {r["scenario"]: r for r in doc["rows"]}
    a, b, c = rows["a"], rows["b"], rows["c"]
    assert a["speed"] == "same" and a["ratio"] == pytest.approx(2.02 / 2.01) and a["grown_phase"] is None
    assert a["valid"] == a["runs"] == 3 and a["base_runs"] == 3 and a["certificate_same"]
    assert a["certificate"]["text"] == "3/3 passed (exact: inertia 10 = found 10)"
    assert a["phases"]["subspace_s"] == {"base": 0.0, "new": 0.01, "delta": pytest.approx(0.01)}
    assert (a["version"], a["base_version"]) == ("1.0.0", "0.1.0") and a["same_scenario"] and a["fast_path_off"]
    # slower: the iteration's growth (0.4 -> 0.8 s) is larger than every other phase's
    assert b["speed"] == "slower" and b["ratio"] == pytest.approx(1.4) and b["grown_phase"] == "iterate_s"
    assert b["phases"]["setup_factor_s"]["new"] == pytest.approx(1.4 - 0.8 - 0.1 - 0.28)
    assert b["phases"]["factorizations"] == {"base": 2.0, "new": 3.0, "delta": 1.0}
    # invalid in one repetition, faster, the certificate changed
    assert (c["valid"], c["runs"], c["speed"]) == (2, 3, "faster") and not c["certificate_same"]
    assert c["invalid"][0]["rep"] == 1 and c["invalid"][0]["outcome"] == ["missed"]
    assert "inertia 10 != found 9" in c["certificate"]["text"]
    s = doc["summary"]
    assert (s["scenarios"], s["valid_every_rep"], s["runs"], s["valid_runs"]) == (3, 2, 9, 8)
    assert s["slower"] == ["b"] and s["faster"] == ["c"] and s["certificate_changed"] == ["c"]
    assert doc["not_remeasured"] == ["d"]
    assert doc["conditions"]["source_commit"] == "47d03dc" and doc["base_conditions"]["source_commit"] == "b9aadc4"


def test_certificate_not_performed_names_the_reason():
    note = "not available for indefinite B (Sylvester inertia does not count eigenvalues)"
    runs = [_run(r, 1.0, cert={"performed": False, "passed": False, "method": "none", "count_inertia": -1,
                               "count_found": -1, "note": note}) for r in range(3)]
    s = recheck.certificate_summary(runs)
    assert (s["performed"], s["passed"]) == (0, 0) and s["text"] == f"not performed ({note})"


def test_a_changed_scenario_definition_is_flagged(dirs):
    base, new = dirs
    doc = json.loads((new / "a.json").read_text())
    doc["scenario"]["hsolve_config"] = {"method": "auto"}
    (new / "a.json").write_text(json.dumps(doc))
    assert recheck.build(new, base)["summary"]["scenario_changed"] == ["a"]


def test_written_files_and_check(dirs, capsys):
    base, new = dirs
    assert recheck.main(["--new", str(new), "--base", str(base)]) == 0
    md = (new.parent / "recheck.md").read_text()
    js = json.loads((new.parent / "recheck.json").read_text())
    assert js["summary"]["slower"] == ["b"]
    assert "| `b` | case-x, 1,000 | 3/3 | 1.4 | 1 | **1.400** (slower; iterate_s grew) |" in md
    assert "| `c` | case-x, 1,000 | 2/3 **INVALID** |" in md and "- `c` rep 1: missed;" in md
    assert "Not re-measured: d." in md
    assert recheck.main(["--new", str(new), "--base", str(base), "--check"]) == 0
    (new.parent / "recheck.md").write_text(md + "edited\n")
    assert recheck.main(["--new", str(new), "--base", str(base), "--check"]) == 1
    assert "out of date" in capsys.readouterr().out


def test_a_record_without_a_committed_one_is_an_error(dirs):
    base, new = dirs
    (new / "e.json").write_text(json.dumps(_doc("e", [_run(0, 1.0)], "47d03dc")))
    with pytest.raises(SystemExit, match="no committed record for e"):
        recheck.build(new, base)

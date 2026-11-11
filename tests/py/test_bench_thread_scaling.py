# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Lin Zihan and the hsolve contributors
"""tools/bench/thread_scaling.py: the phase split of a report, the configurations (--variant) and their
run order, and the speedup / efficiency table over a raw run directory - against the configuration's
own smallest thread count and against the case's fastest configuration there (synthetic runs; the
run itself needs the measurement slot)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.bench import thread_scaling as ts


def report(setup: float, factor: float, iterate: float, verify: float, cert: float, analysis: float,
           factorize: float, solves: float, ordering: int = 10) -> dict:
    return {"time_total_s": setup + factor + iterate + verify + cert, "time_setup_s": setup,
            "time_factor_s": factor, "time_iterate_s": iterate, "time_verify_s": verify,
            "time_certificate_s": cert, "n": 1000, "problem": "standard", "success": True, "block_size": 4,
            "factor_options": {"ordering": ordering},
            "factor_stats": {"analyze_s": analysis, "factorize_s": factorize, "solve_s": solves}}


def test_phases_are_exclusive_and_split_the_total(tmp_path: Path):
    # Certificate counts on the main object: factor_stats.factorize_s (3.5) also holds them, the
    # split takes the factorization from the factor phase instead and never counts them twice.
    (tmp_path / "report.json").write_text(json.dumps(report(0.25, 5.0, 3.0, 0.25, 1.5, 1.0, 3.5, 2.5, 3)))
    p = ts.phases(tmp_path)
    assert p == pytest.approx({"analysis": 1.0, "numeric": 4.0, "solves": 2.5, "iterate_other": 0.5,
                               "certificate": 1.5, "rest": 0.5})
    assert sum(p.values()) == pytest.approx(10.0)
    assert ts.ordering(tmp_path) == "SCOTCH"
    # Analysis or solves beyond their phase are capped by it.
    (tmp_path / "report.json").write_text(json.dumps(report(0.0, 1.0, 1.0, 0.0, 0.0, 2.0, 0.5, 3.0)))
    p = ts.phases(tmp_path)
    assert p["analysis"] == 1.0 and p["numeric"] == 0.0 and p["solves"] == 1.0 and p["iterate_other"] == 0.0


def write_run(rd: Path, case: str, t: int, rep: int, total: float, verdict: str = "pass",
              label: str | None = None, **extra) -> dict:
    label = label or f"t{t}"
    out = rd / case / f"{label}-r{rep}"
    out.mkdir(parents=True)
    (out / "evaluation.json").write_text(json.dumps({"verdict": verdict, "completeness": {"status": "complete"}}))
    rec = {"case": case, "label": label, "threads": t, "rep": rep, "host": "h", "binary": "b", "rc": 0,
           "killed": None, "wall_s": total + 1, "peak_rss_gib": 1.0, "success": True, "time_total_s": total,
           "n": 1000, "problem": "standard", "block_size": 4, "certificate_method": "exact",
           "phases": {"analysis": 0.1 * total, "numeric": 0.5 * total, "solves": 0.2 * total,
                      "iterate_other": 0.0, "certificate": 0.2 * total, "rest": 0.0}, **extra}
    with open(rd / "runs.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def test_table_speedup_and_efficiency(tmp_path: Path):
    rd = tmp_path / "T"
    rd.mkdir()
    for rep, scale in enumerate((1.0, 1.1, 0.9)):
        write_run(rd, "c", 1, rep, 8.0 * scale)
        write_run(rd, "c", 4, rep, 2.5 * scale)
        write_run(rd, "c", 16, rep, 1.0 * scale)
    write_run(rd, "d", 2, 0, 4.0)
    write_run(rd, "d", 8, 0, 2.0, verdict="fail")    # an invalid run: no speedup for that row
    out = tmp_path / "t.json"
    assert ts.main(["table", str(rd), "--json", str(out), "--md", str(tmp_path / "t.md")]) == 0
    doc = json.loads(out.read_text())
    c = {r["threads"]: r for r in doc["cases"][0]["rows"]}
    assert c[1]["speedup"] == pytest.approx(1.0) and c[4]["speedup"] == pytest.approx(3.2)
    assert c[4]["efficiency"] == pytest.approx(0.8) and c[16]["efficiency"] == pytest.approx(0.5)
    assert c[16]["phase_speedup"]["numeric"] == pytest.approx(8.0)
    d = {r["threads"]: r for r in doc["cases"][1]["rows"]}
    assert d[2]["speedup"] == pytest.approx(1.0)       # the smallest measured thread count is the base
    assert d[8]["speedup"] is None and d[8]["valid"] == 0
    md = (tmp_path / "t.md").read_text()
    assert "| 16 | 1.000 [0.900-1.100] | 8.00x | 0.50 |" in md
    assert "Not valid (not in the medians): T = 8 r0: rc=0 killed=None success=True verdict=fail, 2.000 s" in md


def test_table_rereads_the_reports(tmp_path: Path):
    rd = tmp_path / "T"
    rd.mkdir()
    for t, factor in ((1, 4.0), (2, 2.0)):
        write_run(rd, "c", t, 0, factor + 1.0)
        (rd / "c" / f"t{t}-r0" / "report.json").write_text(
            json.dumps(report(0.5, factor, 0.5, 0.0, 0.0, 1.0, 9.9, 0.25, 0 if t == 1 else 10)))
    out = tmp_path / "t.json"
    assert ts.main(["table", str(rd), "--json", str(out)]) == 0
    rows = json.loads(out.read_text())["cases"][0]["rows"]
    assert [r["ordering"] for r in rows] == ["AMD", "ND"]
    assert rows[1]["phases"]["numeric"] == pytest.approx(1.0)       # from the report, not runs.jsonl
    assert rows[1]["phase_speedup"]["numeric"] == pytest.approx(3.0)
    assert not rows[1]["same_ordering"]                              # AMD at 1 thread, ND at 2


def test_variants_parse_and_label():
    d = ts.parse_variant("default")
    assert d.name == "default" and d.threads is None and d.overrides == {} and d.label(16) == "t16"
    nd = ts.parse_variant('nd={"ordering": 10}')
    assert nd.threads is None and nd.overrides == {"ordering": 10} and nd.label(16) == "nd-t16"
    sc = ts.parse_variant('scotch@1,2={"ordering":3}')
    assert sc.threads == [1, 2] and sc.overrides == {"ordering": 3}
    d1 = ts.parse_variant("default@1,16")
    assert d1.name == "default" and d1.threads == [1, 16] and d1.label(1) == "t1" and d1.slepc is None
    for bad in ('default={"ordering":10}', 'default@1={"ordering":10}', "nd", 'a-b={"ordering":3}', "nd=[10]",
                "nd={}", "nd={", 's={"slepc":"tuned","ordering":3}', 's={"slepc":"best"}', 's={"slepc":{"threads":2}}'):
        with pytest.raises(ValueError):
            ts.parse_variant(bad)
    assert ts.parse_label("t4") == ("default", 4) and ts.parse_label("nd-t16") == ("nd", 16)
    assert ts.parse_label("scotch.x_1-t1") == ("scotch.x_1", 1)
    assert ts.parse_label("main") is None and ts.parse_label("nd-16") is None


def test_variant_config_and_schedule(tmp_path: Path):
    case = tmp_path / "cases" / "c"
    case.mkdir(parents=True)
    (case / "config.json").write_text(json.dumps({"target": {"mode": "nearest", "k": 4}, "ordering": -1}))
    assert ts.variant_config(case, tmp_path / "R" / "c", ts.Variant("default")) == case / "config.json"
    p = ts.variant_config(case, tmp_path / "R" / "c", ts.parse_variant('nd={"ordering":10}'))
    assert p == tmp_path / "R" / "c" / "config-nd.json"
    assert json.loads(p.read_text()) == {"target": {"mode": "nearest", "k": 4}, "ordering": 10}
    vs = [ts.Variant("default"), ts.parse_variant('nd={"ordering":10}'), ts.parse_variant('amd@1={"ordering":0}')]
    s = [(rep, c, t, v.name) for rep, c, t, v in ts.schedule(["a", "b"], [1, 4], vs, [0, 1])]
    assert s[:5] == [(0, "a", 1, "default"), (0, "a", 1, "nd"), (0, "a", 1, "amd"), (0, "a", 4, "default"),
                     (0, "a", 4, "nd")]
    assert s[10:15] == [(1, "a", 4, "nd"), (1, "a", 4, "default"), (1, "a", 1, "amd"), (1, "a", 1, "nd"),
                        (1, "a", 1, "default")]
    assert len(s) == 2 * 2 * 5     # amd only at T = 1


def write_variant_run(rd: Path, case: str, label: str, t: int, rep: int, total: float, order: int, entries: int,
                      verdict: str = "pass") -> None:
    write_run(rd, case, t, rep, total, verdict, label)
    rep_doc = report(0.0, 0.5 * total, 0.3 * total, 0.0, 0.2 * total, 0.1 * total, 0.4 * total, 0.2 * total, order)
    rep_doc["factor_stats"]["factor_entries"] = entries
    (rd / case / f"{label}-r{rep}" / "report.json").write_text(json.dumps(rep_doc))


def test_speedup_against_the_fastest_serial_configuration(tmp_path: Path):
    # The p9int review: the adaptive default took SCOTCH at 1 thread (11.0 s) and the own dissection
    # from 2 threads on; the dissection itself was faster at 1 thread (9.8 s). The default's speedup
    # is taken against the fastest 1-thread configuration; its speedup against itself is flagged.
    rd = tmp_path / "T"
    rd.mkdir()
    for rep, scale in enumerate((1.0, 1.02, 0.98)):
        write_variant_run(rd, "c", "t1", 1, rep, 11.0 * scale, 3, 900)
        write_variant_run(rd, "c", "t2", 2, rep, 5.6 * scale, 10, 800)
        write_variant_run(rd, "c", "t16", 16, rep, 2.0 * scale, 10, 800)
        write_variant_run(rd, "c", "nd-t1", 1, rep, 9.8 * scale, 10, 800)
        write_variant_run(rd, "c", "nd-t2", 2, rep, 5.0 * scale, 10, 800)
        write_variant_run(rd, "c", "nd-t16", 16, rep, 1.96 * scale, 10, 800)
        write_variant_run(rd, "c", "metis-t1", 1, rep, 10.5 * scale, 5, 850)
    out = tmp_path / "t.json"
    assert ts.main(["table", str(rd), "--json", str(out), "--md", str(tmp_path / "t.md")]) == 0
    c = json.loads(out.read_text())["cases"][0]
    assert c["fastest"] == {"variant": "nd", "threads": 1, "time_s": pytest.approx(9.8), "ordering": "ND"}
    assert [x["variant"] for x in c["variants"]] == ["default", "metis", "nd"]
    v = {x["variant"]: {r["threads"]: r for r in x["rows"]} for x in c["variants"]}
    d16 = v["default"][16]
    assert d16["speedup"] == pytest.approx(5.5) and not d16["same_ordering"]
    assert d16["speedup_vs_fastest"] == pytest.approx(4.9)
    assert d16["efficiency_vs_fastest"] == pytest.approx(4.9 / 16)
    assert v["nd"][16]["speedup"] == pytest.approx(5.0) and v["nd"][16]["same_ordering"]
    assert v["nd"][16]["factor_entries"] == 800 and v["default"][1]["factor_entries"] == 900
    assert v["metis"][1]["speedup_vs_fastest"] == pytest.approx(9.8 / 10.5)
    md = (tmp_path / "t.md").read_text()
    assert "| c | default | SCOTCH/ND | 11.00 | 5.60 | 2.00 | 5.50x (orderings differ) | 4.90x | 0.31 |" in md
    assert "| c | nd | ND | 9.80 | 5.00 | 1.96 | 5.00x | 5.00x | 0.31 |" in md
    assert "orderings differ (SCOTCH at 1, ND at 16): not the parallel speedup of one computation" in md
    assert "| 16 | 2.000 [1.960-2.040] | 5.50x | 0.34 | 4.90x |" in md and "| ND * | 800 |" in md
    # An invalid run removes its configuration from the choice of the fastest.
    write_variant_run(rd, "c", "nd-t1", 1, 3, 9.8, 10, 800, verdict="fail")
    assert ts.main(["table", str(rd), "--json", str(out)]) == 0
    c = json.loads(out.read_text())["cases"][0]
    assert c["fastest"]["variant"] == "metis"
    assert {x["variant"]: x["rows"][-1] for x in c["variants"]}["nd"]["speedup"] is None


def test_slepc_variants_parse_and_configure(tmp_path: Path):
    v = ts.parse_variant('slepc.tuned@1,16={"slepc":"tuned"}')
    assert v.slepc == "tuned" and v.threads == [1, 16] and v.label(16) == "slepc.tuned-t16"
    assert ts.parse_variant('s={"slepc":"default"}').slepc == "default"
    case = tmp_path / "cases" / "c"
    case.mkdir(parents=True)
    (case / "meta.json").write_text(json.dumps({"problem": "HEP"}))
    (case / "config.json").write_text(json.dumps({"target": {"mode": "nearest", "sigma": 1.0, "k": 10}}))
    prof = tmp_path / "profiles.json"
    tuned = {"ranks": 4, "threads": 4, "bind": "core",
             "options": {"eps_ncv": "3k", "st_mat_mumps_icntl_28": "2", "st_mat_mumps_icntl_29": "2"}}
    prof.write_text(json.dumps({"schema_version": 1, "profiles": [
        {"scope": "case", "name": "c", "mode": "nearest", "cores": 16, "target": None, "config": tuned}]}))
    # The default: one rank x T threads, no options.
    assert ts.slepc_config("default", 1, case, prof, 16).label() == "1x1"
    assert ts.slepc_config("default", 16, case, prof, 16).label() == "1x16"
    # The tuned profile keeps its ranks where they divide T, else one rank; one rank drops the
    # parallel analysis (SlepcConfig.fitted).
    assert ts.slepc_config("tuned", 16, case, prof, 16).label() == \
        "4x4/core eps_ncv=3k st_mat_mumps_icntl_28=2 st_mat_mumps_icntl_29=2"
    assert ts.slepc_config("tuned", 1, case, prof, 16).label() == "1x1/core eps_ncv=3k"
    assert ts.slepc_config("tuned", 8, case, prof, 16).label().startswith("4x2/core")
    assert ts.slepc_config({"ranks": 2, "options": {"eps_tol": "1e-11"}}, 4, case, prof, 16).label() == \
        "2x2 eps_tol=1e-11"
    with pytest.raises(SystemExit):     # no tuned profile at that core count
        ts.slepc_config("tuned", 16, case, prof, 32)
    cmd = ts.slepc_command(ts.slepc_config("tuned", 16, case, prof, 16), case, tmp_path / "o", tmp_path / "lv.txt",
                           tmp_path, "/env", "/env/lib")
    assert cmd[:5] == ["env", "LD_LIBRARY_PATH=/env/lib", "/env/bin/mpiexec", "-x", "LD_LIBRARY_PATH"]
    assert cmd[cmd.index("-n") + 1] == "4" and cmd[cmd.index("-eps_ncv") + 1] == "30"
    assert cmd[cmd.index("--case") + 1] == "c" and cmd[-2:] == ["-log_view", f":{tmp_path / 'lv.txt'}"]
    assert ts.slepc_command(ts.slepc_config("default", 1, case, prof, 16), case, tmp_path / "o",
                            tmp_path / "lv.txt", tmp_path, "/env", None)[0] == "/env/bin/mpiexec"


def test_slepc_times_from_the_log_view_or_the_report(tmp_path: Path, monkeypatch):
    (tmp_path / "report.json").write_text(json.dumps({"time_setup_s": 3.0, "time_solve_s": 2.0, "time_total_s": 9.0}))
    monkeypatch.setattr(ts.slepc_log, "read_phases", lambda path: None)
    t = ts.slepc_times(tmp_path, tmp_path / "missing.txt")
    assert t["time_total_s"] == 5.0 and t["time_scope"] == "report time_setup_s+time_solve_s"
    assert sum(t["phases"].values()) == 5.0
    monkeypatch.setattr(ts.slepc_log, "read_phases", lambda path: {
        "analysis_s": 1.0, "numeric_s": 4.0, "solve_s": 2.0, "solver_s": 8.0})
    t = ts.slepc_times(tmp_path, tmp_path / "lv.txt")
    assert t["time_total_s"] == 8.0 and t["time_scope"] == "log_view setup+solve+vectors"
    assert t["phases"] == {"analysis": 1.0, "numeric": 4.0, "solves": 2.0, "iterate_other": 1.0,
                           "certificate": 0.0, "rest": 0.0}


def test_table_slepc_rows(tmp_path: Path):
    # SLEPc rows: their own speedup, never hsolve's fastest configuration (though faster here at
    # T = 1), and their time over hsolve's default at the same T.
    rd = tmp_path / "T"
    rd.mkdir()
    for rep in range(3):
        write_variant_run(rd, "c", "t1", 1, rep, 100.0, 10, 800)
        write_variant_run(rd, "c", "t16", 16, rep, 12.5, 10, 800)
        for t, total, layout in ((1, 80.0, "1x1"), (16, 20.0, "2x8")):
            write_run(rd, "c", t, rep, total, label=f"slepc.tuned-t{t}", solver="slepc",
                      slepc_config=f"{layout} eps_ncv=4k", time_scope="log_view setup+solve+vectors")
    out = tmp_path / "t.json"
    assert ts.main(["table", str(rd), "--json", str(out), "--md", str(tmp_path / "t.md")]) == 0
    c = json.loads(out.read_text())["cases"][0]
    assert c["fastest"]["variant"] == "default"
    assert [(v["variant"], v["solver"]) for v in c["variants"]] == [("default", "hsolve"), ("slepc.tuned", "slepc")]
    s = {r["threads"]: r for r in c["variants"][1]["rows"]}
    assert s[16]["speedup"] == pytest.approx(4.0) and s[16]["speedup_vs_fastest"] is None
    assert s[1]["slepc_over_default"] == pytest.approx(0.8) and s[16]["slepc_over_default"] == pytest.approx(1.6)
    assert s[1]["ordering"] == "SLEPc" and s[16]["same_ordering"]
    md = (tmp_path / "t.md").read_text()
    assert "*slepc.tuned* (SLEPc 1x1 eps_ncv=4k; 2x8 eps_ncv=4k; time log_view setup+solve+vectors)" in md
    assert "SLEPc / hsolve default at the same T: T = 1: 0.80, T = 16: 1.60" in md


def test_table_factor_entries_from_the_estimate_and_the_rate(tmp_path: Path):
    # 1.0.0 reports factor_stats.factor_entries = 0 and the analysis estimate; the rate is the
    # factorizations x the analysed flops over the factorization + certificate phases.
    rd = tmp_path / "T"
    rd.mkdir()
    for t, total in ((1, 60.0), (16, 10.0)):
        write_run(rd, "c", t, 0, total, factorizations=3)
        doc = report(0.0, 0.5 * total, 0.3 * total, 0.0, 0.2 * total, 0.1 * total, 0.4 * total, 0.2 * total)
        doc["factor_stats"].update(factor_entries=0, estimate={"factor_entries": 500, "flops": 2e12})
        (rd / "c" / f"t{t}-r0" / "report.json").write_text(json.dumps(doc))
    out = tmp_path / "t.json"
    assert ts.main(["table", str(rd), "--json", str(out), "--md", str(tmp_path / "t.md")]) == 0
    rows = {r["threads"]: r for r in json.loads(out.read_text())["cases"][0]["rows"]}
    assert rows[1]["factor_entries"] == 500 and rows[16]["factor_flops"] == 2e12
    assert rows[1]["factor_gflops"] == pytest.approx(3 * 2e12 / (0.6 * 60.0) / 1e9)
    assert rows[16]["factor_gflops"] == pytest.approx(1000.0)
    assert "| ND | 500 | 1/1 | 1.00 | 1000.0 |" in (tmp_path / "t.md").read_text()

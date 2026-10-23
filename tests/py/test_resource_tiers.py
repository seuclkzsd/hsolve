# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 seuclkzsd and the hsolve contributors
"""scripts/resource_tiers.py: core selection for the runs, the tier tables of docs/INSTALL.md §5,
that only runs of the general path (report candidate_source = iterative) are measured and tabulated,
and that the committed tables are what the committed raw data give."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TIERS_DIR = ROOT / "results" / "resource-tiers"


def load():
    spec = importlib.util.spec_from_file_location("hsolve_resource_tiers", ROOT / "scripts" / "resource_tiers.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rt = load()


# ------------------------------------------------------------------------------- cores

def topology(tmp_path: Path, siblings: dict[int, str]) -> Path:
    for cpu, lst in siblings.items():
        d = tmp_path / f"cpu{cpu}" / "topology"
        d.mkdir(parents=True)
        (d / "thread_siblings_list").write_text(lst + "\n")
    return tmp_path


def test_the_measurement_slot_is_the_pool_where_the_node_defines_one():
    assert rt.core_pool({"HS_MEASURE_CORES": "16-31"}, set(range(64))) == list(range(16, 32))
    assert rt.core_pool({}, {3, 0, 1, 2}) == [0, 1, 2, 3]  # a workstation: the CPUs it may use


def test_runs_take_the_first_cores_of_the_pool_or_from_the_given_one():
    slot = list(range(16, 32))
    assert rt.pick_cores(slot, 16, None) == "16-31"  # the published runs: 16 threads on 16-31,
    assert rt.pick_cores(slot, 4, None) == "16-19"   # 4 threads on 16-19
    assert rt.pick_cores(list(range(16)), 16, None) == "0-15"  # a 16-core workstation
    assert rt.pick_cores(list(range(16)), 4, 8) == "8-11"
    assert rt.pick_cores([0, 2, 4, 6, 8], 3, None) == "0,2,4"
    with pytest.raises(SystemExit, match="16 threads need 16 physical cores"):
        rt.pick_cores(list(range(8)), 16, None)
    with pytest.raises(SystemExit, match="not among the usable CPUs"):
        rt.pick_cores(slot, 4, 0)


def test_hyperthread_siblings_are_left_out(tmp_path):
    # 4 cores x 2 threads, siblings numbered n and n + 4 (cpu0/cpu4 ...), and adjacent (cpu8/cpu9).
    topo = topology(tmp_path, {0: "0,4", 1: "1,5", 2: "2,6", 3: "3,7", 4: "0,4", 5: "1,5", 6: "2,6", 7: "3,7",
                               8: "8-9", 9: "8-9"})
    assert rt.one_per_core(list(range(10)), topo) == [0, 1, 2, 3, 8]
    assert rt.one_per_core([16, 17], topo) == [16, 17]  # no topology: each CPU its own core


def test_cpulist_compresses_runs():
    assert rt.cpulist([16, 17, 18, 20]) == "16-18,20"
    assert rt.cpulist([5]) == "5"
    assert rt.cpulist([]) == ""


# ------------------------------------------------------------------------------- tables

def row(case: str, threads: int, certified: str, mem_gb: float = 32.0, ok: int = 3) -> dict:
    return {"case": case, "n": 1000, "nnz": 5000, "pairs": 10, "threads": threads, "mem_gb": mem_gb, "reps": 3,
            "ok": ok, "time_median_s": 1.0, "peak_rss_gib": 0.5, "memory_mode": "in-core", "errors": [],
            "certified": certified}


@pytest.mark.parametrize("states, shown", [
    (("passed", "passed"), "通过"),
    (("none", "none"), "不适用（B 不定）"),
    (("passed", "failed"), "未通过"),   # the 4-thread runs failed their certificate
    (("failed", "passed"), "未通过"),
    (("passed", "none"), "未通过"),
])
def test_summary_certificate_holds_for_every_thread_count(states, shown):
    rows = [row("yee-pec-box-1e4", 16, states[0]), row("yee-pec-box-1e4", 4, states[1])]
    line = rt.summary(rows).splitlines()[2]
    assert line.endswith(f"| {shown} |"), line


# ------------------------------------------------------------------------------- general path only

def fake_solver(monkeypatch, tmp_path: Path, candidate_source: str) -> list[str]:
    """`run` arguments for one case with an hsolve whose reports give candidate_source; guard.py and
    hsolve are replaced by a stand-in for subprocess.run that writes the guard summary and the report."""
    for var in ("HS_MEASURE_CORES", "HS_TIER_FIRST_CORE", "HS_SLOT_HELD"):
        monkeypatch.delenv(var, raising=False)
    hsolve = tmp_path / "hsolve"
    hsolve.write_text("")
    (tmp_path / "data" / "cases" / "box").mkdir(parents=True)

    def solve(cmd, **_kw):
        if cmd[-1] == "--version":
            return subprocess.CompletedProcess(cmd, 0, "hsolve 1.0.0\n", "")
        Path(cmd[cmd.index("--summary") + 1]).write_text(json.dumps({"returncode": 0, "wall_s": 1.5,
                                                                     "peak_rss_gib": 0.25}))
        report = {"success": True, "time_total_s": 1.0, "problem": "generalized_definite", "n": 100,
                  "candidate_source": candidate_source, "pairs": [{}] * 10,
                  "certificate": {"performed": True, "passed": True, "method": "exact"}}
        (Path(cmd[cmd.index("--out") + 1]) / "report.json").write_text(json.dumps(report))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(rt.subprocess, "run", solve)
    return ["run", "--root", str(tmp_path / "data"), "--out", str(tmp_path / "raw"), "--cases", "box",
            "--threads", "1", "--mem-gb", "32", "--reps", "2", "--hsolve", str(hsolve)]


def logged(tmp_path: Path) -> list[dict]:
    return [json.loads(line) for line in (tmp_path / "raw" / "runs.jsonl").read_text().splitlines()]


def test_runs_record_the_candidate_source_of_the_general_path(monkeypatch, tmp_path):
    assert rt.main(fake_solver(monkeypatch, tmp_path, "iterative")) == 0
    assert [r["candidate_source"] for r in logged(tmp_path)] == ["iterative", "iterative"]
    rows = rt.summarize([tmp_path / "raw"])
    assert [(r["ok"], r["candidate_source"]) for r in rows] == [(2, "iterative")]


def test_run_stops_at_a_report_of_the_structure_fast_path(monkeypatch, tmp_path):
    with pytest.raises(SystemExit, match='box t1-m32-r0: report candidate_source = "separable_cartesian_curl"'):
        rt.main(fake_solver(monkeypatch, tmp_path, "separable_cartesian_curl"))
    assert [r["candidate_source"] for r in logged(tmp_path)] == ["separable_cartesian_curl"]  # logged, then stopped


def raw_dir(tmp_path: Path, *records: dict) -> Path:
    raw = tmp_path / "tiers-node"
    raw.mkdir()
    (raw / "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
    return raw


RUN = {"case": "yee-pec-box-1e6", "threads": 16, "mem_gb": 32.0, "rep": 0, "host": "node", "version": "hsolve",
       "rc": 0, "killed": None, "wall_s": 2.0, "peak_rss_gib": 1.0, "success": True, "time_total_s": 1.5,
       "n": 1000, "pairs": 10, "certificate": "exact", "certificate_passed": True, "candidate_source": "iterative"}


@pytest.mark.parametrize("source", ["separable_cartesian_curl", "separable_bloch_curl", None])
def test_tables_refuse_runs_off_the_general_path(tmp_path, source):
    bad = dict(RUN, rep=1, candidate_source=source)
    if source is None:
        del bad["candidate_source"]  # raw data from before the field was recorded
    with pytest.raises(SystemExit, match=f"yee-pec-box-1e6 t16-m32-r1: report candidate_source = {json.dumps(source)}"):
        rt.summarize([raw_dir(tmp_path, RUN, bad)])


def test_a_refused_run_has_no_report_to_check(tmp_path):
    refused = {k: v for k, v in RUN.items() if k in ("case", "threads", "rep", "host", "version", "killed")}
    refused.update(mem_gb=4.0, rc=2, wall_s=5.0, peak_rss_gib=1.1, error="FileNotFoundError: no report.json")
    raw = raw_dir(tmp_path, RUN, refused)
    (raw / "yee-pec-box-1e6").mkdir()
    (raw / "yee-pec-box-1e6" / "stderr-t16-m4-r0.txt").write_text(
        "hsolve: error [out_of_memory_budget]: predicted factorization memory ...\n")
    rows = {r["mem_gb"]: r for r in rt.summarize([raw])}
    assert rows[32.0]["candidate_source"] == "iterative"
    assert (rows[4.0]["candidate_source"], rows[4.0]["errors"]) == (None, ["out_of_memory_budget"])


def test_committed_tables_are_those_of_the_committed_raw_data(tmp_path):
    """results/resource-tiers/reproduce.sh retable, compared with the files in the repository."""
    safe = {"filter": "data"} if hasattr(tarfile, "data_filter") else {}
    for raw in sorted(TIERS_DIR.glob("raw-tiers-*.tar.gz")):
        with tarfile.open(raw) as tar:
            tar.extractall(tmp_path, **safe)
    out = tmp_path / "out"
    out.mkdir()
    args = [str(p) for p in sorted(tmp_path.glob("tiers-*"))]
    assert args, "no raw data"
    assert rt.main(["table", *args, "--md", str(out / "tiers.md"), "--json", str(out / "tiers.json"),
                    "--summary-md", str(out / "tiers-summary.md")]) == 0
    for name in ("tiers.md", "tiers.json", "tiers-summary.md"):
        assert (out / name).read_text() == (TIERS_DIR / name).read_text(), name

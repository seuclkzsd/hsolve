# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 seuclkzsd and the hsolve contributors
"""scripts/resource_tiers.py: core selection for the runs, the tier tables of docs/INSTALL.md §5,
and that the committed tables are what the committed raw data give."""
from __future__ import annotations

import importlib.util
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

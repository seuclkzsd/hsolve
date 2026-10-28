# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 seuclkzsd and the hsolve contributors
"""Tests of the P10 "mpi" layout campaign tool (tools/bench/mpi_layouts.py): the layout names, the
bench table (one count, the pair of counts - the slower of two concurrent ones -, factorization,
solve; ratios to a base layout; a failed inertia check or run counts against "runs ok") and the
hsolve table (valid runs only, phases). Synthetic JSON lines; no MUMPS, MPI or guard needed."""
import json
from pathlib import Path

import pytest

from tools.bench import mpi_layouts


def test_layouts_parse_and_reject():
    assert mpi_layouts.parse_layouts("one:1x16,two:2x8,two:1+2x8") == [("one", "1x16"), ("two", "2x8"),
                                                                         ("two", "1+2x8")]
    for bad in ("three:1x16", "one:4x4", "1x16"):
        with pytest.raises(SystemExit):
            mpi_layouts.parse_layouts(bad)
    assert mpi_layouts.parse_layouts("one:1x1") == [("one", "1x1")]


def test_set_replaces_config_keys_of_one_layout_only(tmp_path):
    layouts = mpi_layouts.parse_layouts("one:1x1,one:1x16")
    sets = mpi_layouts.parse_sets(['one:1x1={"ordering": 10}', 'one:1x1={"block_size": 4}'], layouts)
    assert sets == {"one:1x1": {"ordering": 10, "block_size": 4}}
    for bad in ('two:1x1={"ordering": 10}', "one:1x1", 'one:1x1=[1]', 'one:1x1={"target": {}}'):
        with pytest.raises(SystemExit):
            mpi_layouts.parse_sets([bad], layouts)
    cdir = tmp_path / "data" / "cases" / "c"
    cdir.mkdir(parents=True)
    (cdir / "A.npz").write_bytes(b"")
    (cdir / "config.json").write_text(json.dumps({"target": {"mode": "nearest", "sigma": 1.0, "k": 4},
                                                  "tol": 1e-10, "ordering": 0}))
    out = tmp_path / "runs" / "c" / "one-1x1-r0"
    args = mpi_layouts.hsolve_args(tmp_path / "data", "c", out, {"mode": "interval", "lower": 0, "upper": 2},
                                   sets["one:1x1"])
    cfg = json.loads(Path(args[args.index("--config") + 1]).read_text())
    assert cfg == {"target": {"mode": "interval", "lower": 0, "upper": 2}, "tol": 1e-10, "ordering": 10,
                   "block_size": 4}
    assert "--B" not in args
    plain = mpi_layouts.hsolve_args(tmp_path / "data", "c", tmp_path / "runs" / "c" / "one-1x16-r0", None, None)
    assert plain[plain.index("--config") + 1] == str(cdir / "config.json")   # the case's own config


FAKE_HSOLVE = """#!/usr/bin/env bash
cpus=$(awk '/^Cpus_allowed_list/ { print $2 }' /proc/self/status)
echo "{\\"omp\\": \\"$OMP_NUM_THREADS\\", \\"allowed\\": \\"$cpus\\", \\"args\\": \\"$*\\"}"
"""


@pytest.mark.parametrize("split, want_cpus, want_threads", [("1x16", "all", "2"), ("1x8", "first", "1"),
                                                             ("1x1", "first", "1")])
def test_socket_run_places_the_single_process_splits(tmp_path, split, want_cpus, want_threads):
    """mpi_socket_run.sh on two inherited CPUs, with a fake build/release/hsolve that prints its
    cpuset and OMP_NUM_THREADS: 1x16 takes both, 1x8 and 1x1 the first one with one thread."""
    import os
    import shutil
    import subprocess
    allowed = sorted(os.sched_getaffinity(0))
    if len(allowed) < 2 or shutil.which("taskset") is None:
        pytest.skip("needs two CPUs and taskset")
    two = allowed[:2]
    (tmp_path / "tools/bench").mkdir(parents=True)
    shutil.copy(Path(mpi_layouts.RUN), tmp_path / "tools/bench/mpi_socket_run.sh")
    exe = tmp_path / "build/release/hsolve"
    exe.parent.mkdir(parents=True)
    exe.write_text(FAKE_HSOLVE)
    exe.chmod(0o755)
    cmd = ["taskset", "-c", ",".join(map(str, two)), "bash", str(tmp_path / "tools/bench/mpi_socket_run.sh"),
           split, "hsolve", "--A", "a.npz"]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    d = json.loads(out.strip().splitlines()[-1])
    assert d["omp"] == want_threads and d["args"] == f"--A a.npz --threads {want_threads}"
    if want_cpus == "first":
        assert d["allowed"] == str(two[0]) and d["cores"] == str(two[0])
    else:   # unbound inside the inherited CPUs
        assert d["cores"] == f"{two[0]},{two[1]}" and d["allowed"] != str(two[0])


def _bench_rows(case, lay, rep, procs, count, factor, solve, ok=True):
    rows = []
    for p in range(procs):
        rows += [{"kind": "bench", "case": case, "layout": lay, "rep": rep, "proc": p, "event": "factorize",
                  "mode": "count", "s": count[p]},
                 {"kind": "bench", "case": case, "layout": lay, "rep": rep, "proc": p, "event": "factorize",
                  "mode": "full", "s": factor},
                 {"kind": "bench", "case": case, "layout": lay, "rep": rep, "proc": p, "event": "solve",
                  "mode": "full", "s": solve},
                 {"kind": "bench", "case": case, "layout": lay, "rep": rep, "proc": p, "event": "run",
                  "inertia_ok": ok}]
    rows.append({"kind": "bench", "case": case, "layout": lay, "rep": rep, "event": "guard", "returncode": 0,
                 "killed": None, "peak_rss_gib": 1.0})
    return rows


def _cells(lines, layout):
    row = next(l for l in lines if f"| {layout} |" in l)
    return [c.strip() for c in row.strip("|").split("|")]


def test_bench_table_pairs_and_ratios():
    rows = []
    for rep in range(3):
        rows += _bench_rows("c", "one:1x16", rep, 1, [10.0], 11.0, 1.0)
        rows += _bench_rows("c", "two:2x8", rep, 2, [6.0, 7.0], 12.0, 1.0)
    lines = mpi_layouts.bench_table(rows, "one:1x16")
    base, two = _cells(lines, "one:1x16"), _cells(lines, "two:2x8")
    assert base[2] == "3/3" and base[4].startswith("20.000")  # sequential pair = 2 x one count
    assert two[4].startswith("7.000") and two[5] == "2.86"     # concurrent pair = the slower count
    assert two[7] == "0.92"                                     # factorization 11 / 12


def test_bench_table_counts_a_wrong_inertia_against_the_layout():
    rows = _bench_rows("c", "one:1x16", 0, 1, [10.0], 11.0, 1.0)
    rows += _bench_rows("c", "two:2x8", 0, 2, [6.0, 7.0], 12.0, 1.0, ok=False)
    lines = mpi_layouts.bench_table(rows, "one:1x16")
    assert _cells(lines, "two:2x8")[2].startswith("1/")


def test_hsolve_table_uses_valid_runs_only():
    rows, verdicts = [], {}
    for rep, (t, ok) in enumerate([(10.0, True), (12.0, True), (1.0, False)]):
        out = f"/x/one-1x16-r{rep}"
        rows.append({"kind": "hsolve", "case": "c", "layout": "one:1x16", "rep": rep, "event": "guard", "out": out,
                     "returncode": 0, "killed": None, "peak_rss_gib": 2.0,
                     "report": {"time_total_s": t, "time_factor_s": 1.0, "time_iterate_s": 2.0,
                                "time_certificate_s": 3.0, "time_verify_s": 0.5, "time_setup_s": 0.5}})
        verdicts[out] = {"valid": ok}
        out2 = f"/x/two-1+2x8-r{rep}"
        rows.append({"kind": "hsolve", "case": "c", "layout": "two:1+2x8", "rep": rep, "event": "guard",
                     "out": out2, "returncode": 0, "killed": None, "peak_rss_gib": 3.0,
                     "report": {"time_total_s": 5.5, "time_factor_s": 1.0, "time_iterate_s": 2.0,
                                "time_certificate_s": 1.5, "time_verify_s": 0.5, "time_setup_s": 0.5}})
        verdicts[out2] = {"valid": True}
    lines = mpi_layouts.hsolve_table(rows, verdicts, "one:1x16")
    base, mpi = _cells(lines, "one:1x16"), _cells(lines, "two:1+2x8")
    assert base[2] == "2/3" and base[3].startswith("11.000")   # median of the two valid runs
    assert mpi[2] == "3/3" and mpi[4] == "2.00"                 # 11 / 5.5
    assert mpi[8] == "1.50"                                     # certificate phase


def test_cli_table_reads_the_campaign_files(tmp_path, capsys):
    rows = _bench_rows("c", "one:1x16", 0, 1, [10.0], 11.0, 1.0)
    (tmp_path / "t.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    assert mpi_layouts.main(["table", "--tag", "t", "--out", str(tmp_path), "--md", str(tmp_path / "t.md")]) == 0
    assert "one:1x16" in (tmp_path / "t.md").read_text()

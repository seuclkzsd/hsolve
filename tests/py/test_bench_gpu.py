# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 seuclkzsd and the hsolve contributors
"""tools/bench/gpu_factor_ab.py, gpu_e2e.py and gpu_slot.sh (P10 "gpu"): summaries of synthetic runs,
case specs, and the slot wrapper's argument checks (no GPU, no guard needed)."""
import json
import subprocess
from pathlib import Path

from tools.bench import gpu_e2e, gpu_factor_ab

REPO = Path(__file__).resolve().parents[2]


def fact_line(case, variant, rep, walls, neg=7, gpu=None, label="mumps"):
    facts = [{"job": "analysis", "wall_s": 0.5}]
    facts += [{"job": j, "wall_s": w, "neg": neg, "zero": 0, "valid": True} for j, w in walls.items()]
    return {"case": case, "variant": variant, "rep": rep, "label": label, "factorizations": facts, "gpu": gpu}


def test_factor_summary_speedup_inertia_and_gpu_table():
    g = {"calls": 100, "gpu_gflop": 9000.0, "gpu_share": 0.45, "call_s": 7.5, "predicted_cpu_s": 15.0,
         "h2d_gb": 40.0, "d2h_gb": 13.0, "init_s": 0.27,
         "pipeline_s": {"pack": 5.0, "slot_wait": 1.0, "sync": 0.5, "add": 2.0}}
    lines = [fact_line("c1", "off", r, {"main": 22.0 + r, "a": 20.0}) for r in range(3)]
    lines += [fact_line("c1", "on", r, {"main": 20.0 + r, "a": 18.0}, gpu=g) for r in range(3)]
    md = gpu_factor_ab.summarize(lines)
    rows = {tuple(c.strip() for c in ln.split("|")[1:5]): ln for ln in md.splitlines() if ln.startswith("| c1")}
    main_on = rows[("c1", "mumps", "main", "on")]
    assert "21.00 [20.00-22.00]" in main_on and f"{23.0 / 21.0:.3f}" in main_on
    assert f"{20.0 / 18.0:.3f}" in rows[("c1", "mumps", "a", "on")]
    assert "DIFFER" not in md
    gpu_row = [ln for ln in md.splitlines() if ln.startswith("| c1 | mumps | on | 3 |")]
    assert gpu_row and "| 9000 |" in gpu_row[0] and "0.45" in gpu_row[0] and "5.00 / 1.00 / 0.50 / 2.00" in gpu_row[0]


def test_factor_summary_flags_different_inertia():
    lines = [fact_line("c1", "off", 0, {"main": 1.0}, neg=7), fact_line("c1", "on", 0, {"main": 1.0}, neg=8)]
    assert "DIFFER" in gpu_factor_ab.summarize(lines)


def test_case_specs():
    assert gpu_factor_ab.parse_case("x:1.5:2.5") == ("x", 1.5, 2.5)
    name, lo, hi = gpu_factor_ab.parse_case("syn-mem27-100")
    assert name == "syn-mem27-100" and lo < 0 < hi
    assert gpu_factor_ab.parse_case("other") == ("other", None, None)


def e2e_line(case, variant, rep, t, valid=True, count=12, eigs=(1.0, 2.0), gpu=None):
    return {"case": case, "variant": variant, "rep": rep, "solver_s": t, "valid": valid, "eigenvalues": list(eigs),
            "certificate": {"count_inertia": count}, "gpu": gpu or {}}


def test_e2e_summary():
    g = {"factorizations_offloaded": 3, "factorizations": 3, "gpu_gflop": 9000.0, "gpu_share": 0.45, "call_s": 7.0,
         "predicted_cpu_s": 14.0}
    lines = [e2e_line("c", "off", r, 90.0 + r) for r in range(3)]
    lines += [e2e_line("c", "auto", r, 80.0 + r, eigs=(1.0, 2.0 + 1e-14), gpu=g) for r in range(3)]
    md = gpu_e2e.summarize(lines)
    auto = [ln for ln in md.splitlines() if ln.startswith("| c | auto")][0]
    assert "3/3" in auto and "81.00 [80.00-82.00]" in auto and f"{91.0 / 81.0:.3f}" in auto
    assert "| 12 |" in auto and "3/3" in auto and "9000 (0.45)" in auto and "7.0 / 14.0" in auto
    # an invalid run withholds the speedup
    lines.append(e2e_line("c", "auto", 3, 70.0, valid=False))
    auto = [ln for ln in gpu_e2e.summarize(lines).splitlines() if ln.startswith("| c | auto")][0]
    assert "3/4" in auto and "| - |" in auto


def test_e2e_phase_table():
    def line(variant, rep, total, factor, cert, util=None, valid=True):
        e = e2e_line("c", variant, rep, total, valid=valid)
        e["times"] = {"time_total_s": total, "time_factor_s": factor, "time_certificate_s": cert}
        e["peak_rss_gib"] = 10.0 if variant == "off" else 10.5
        if util is not None:
            e["smi"] = {"samples": 100, "util_mean": util, "mem_max_mib": 1500.0}
        return e

    lines = [line("off", r, 100.0 + r, 20.0, 60.0 + r, util=0.0) for r in range(3)]
    lines += [line("auto", r, 90.0 + r, 18.0, 52.0 + r, util=10.0) for r in range(3)]
    for i, e in enumerate(lines):
        e["sibling_busy"] = 0.001 * i
    md = gpu_e2e.phase_table(lines)
    auto = [ln for ln in md.splitlines() if ln.startswith("| c | auto")][0]
    cells = [x.strip() for x in auto.split("|")[1:-1]]
    # solver 91, factorization phases 18 + 53 = 71 (off: 20 + 61 = 81), rest 20, util 10% of 91 s,
    # the auto runs' siblings at most 0.5% busy
    assert cells[2:] == ["3/3", "91.00", f"{101.0 / 91.0:.3f}", "71.00", f"{81.0 / 71.0:.3f}", "20.00", "10.50",
                         "10.0", "9.1", "0.5"]
    off = [ln for ln in md.splitlines() if ln.startswith("| c | off")][0]
    assert "| 3/3 | 101.00 | - | 81.00 | - |" in off and off.endswith("| 0.2 |")
    # an invalid run withholds both ratios (its sibling load still counts); runs without samples
    # show no utilization and no load
    bad = line("auto", 3, 70.0, 10.0, 40.0, valid=False)
    bad["sibling_busy"] = 0.25
    auto = [ln for ln in gpu_e2e.phase_table(lines + [bad]).splitlines() if ln.startswith("| c | auto")][0]
    assert "| 3/4 | 91.00 | - | 71.00 | - |" in auto and auto.endswith("| 25.0 |")
    assert gpu_e2e.phase_table([line("off", 0, 5.0, 1.0, 2.0)]).splitlines()[-1].endswith("| - | - | - |")


def test_neighbour_load_counts_only_the_siblings():
    # cores 0-1 with siblings 2-3 (from sysfs on a real machine; here the reader is faked)
    ticks = [{0: (100, 0), 1: (100, 0), 2: (100, 100), 3: (100, 100)},
             {0: (200, 0), 1: (200, 0), 2: (200, 190), 3: (200, 170)}]
    load = gpu_e2e.NeighbourLoad("0-1", read=lambda: ticks.pop(0))
    load.cpus = [2, 3]
    with load:
        pass
    assert abs(load.result() - 0.2) < 1e-12  # (10 + 30) busy of 200 ticks
    empty = gpu_e2e.NeighbourLoad("0", read=dict)
    empty.cpus = []
    with empty:
        pass
    assert empty.result() is None


def test_parse_smi():
    r = gpu_e2e.parse_smi("10, 300\n30, 1300\n[N/A], 5\nnot a sample\n")
    assert r == {"samples": 2, "util_mean": 20.0, "mem_max_mib": 1300.0}
    assert gpu_e2e.parse_smi("") == {}


def test_smi_sampler_without_nvidia_smi(monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    with gpu_e2e.SmiSampler("7", 100) as s:
        pass
    assert s.result() == {}


def test_gpu_slot_rejects_bad_arguments():
    script = REPO / "tools/bench/gpu_slot.sh"
    r = subprocess.run(["bash", str(script), "7", "60"], capture_output=True, text=True)
    assert r.returncode == 2
    r = subprocess.run(["bash", str(script), "7", "60", "--lock-wait", "5", "true"], capture_output=True, text=True)
    assert r.returncode == 2 and "missing --" in r.stderr


def test_dgemm_table(tmp_path):
    from tools.bench import gpu_dgemm_table
    lines = [{"what": "gemm", "m": 10, "n": 20, "k": 30, "ta": "N", "tb": "N", "mode": "cpu", "s": 0.002,
              "gflops": 6.0},
             {"what": "gemm", "m": 10, "n": 20, "k": 30, "ta": "N", "tb": "N", "mode": "gpu", "s": 0.001,
              "gflops": 12.0, "speedup": 2.0, "model_speedup": 1.5},
             {"what": "devgemm", "m": 1, "n": 2, "k": 3, "s": 0.5, "gflops": 7.0},
             {"what": "copy", "mb": 16, "h2d_pinned": 12800.0}]
    f = tmp_path / "x.jsonl"
    f.write_text("\n".join(json.dumps(x) for x in lines) + "\nnot json\n")
    rows = gpu_dgemm_table.load([str(f)])
    md = gpu_dgemm_table.gemm_table([r for r in rows if r["what"] == "gemm"])
    assert "| 10 x 20 x 30 | 2.0 ms (6 GF/s) | 1.0 ms (2.00x) | 1.50x |" in md
    assert "12.8" in gpu_dgemm_table.copy_table([r for r in rows if r["what"] == "copy"])
    assert gpu_dgemm_table.main([str(f)]) == 0

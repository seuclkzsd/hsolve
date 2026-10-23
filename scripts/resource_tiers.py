#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 seuclkzsd and the hsolve contributors
"""Resource needs of hsolve by problem size: the measurements behind docs/INSTALL.md's tier table.

Two problem families at n ~ 1e4, 1e5 and 1e6, generated deterministically by tools/gen:
  yee-pec-box-<size>  3-D empty PEC cavity, Yee/FIT curl-curl, generalized definite (GHEP), the 10-11
                      eigenvalues nearest a shift between resonances; the 3-D factorization is the
                      expensive case (fill-in grows like n^(4/3))
  wg-square-<size>    2-D 10 mm square PEC waveguide at 50 GHz, Lee-Sun-Cendes edge/node elements,
                      B indefinite (GHIEP), the 18 propagating modes nearest -0.5 mm^-2

    scripts/resource_tiers.py generate --root DIR [--sizes 1e4,1e5,1e6]
    scripts/resource_tiers.py run --root DIR --out RAW [--cases a,b] [--threads 16,4] [--mem-gb 32]
                                  [--reps 3] [--hsolve PATH] [--first-core N]
    scripts/resource_tiers.py table RAW... --md OUT.md --json OUT.json [--summary-md OUT2.md]

`run` starts every (case, threads, memory cap, repetition) once - in this order, repetitions
outermost - with the case's config.json (target, tol) and nothing else: each under its own
tools/run/guard.py with the RSS cap --mem-gb (hsolve plans its memory budget from it,
docs/DESIGN.md §3.6), pinned to T CPUs, one per physical core (no hyperthread siblings): the first
ones of the measurement slot HS_MEASURE_CORES where the node defines one (cluster nodes: 16-31,
which needs guard.py --exclusive around the whole `run`), else of the CPUs this process may run
on - from --first-core / HS_TIER_FIRST_CORE when given. It records the guard summary (wall time,
peak RSS of the process tree) next to the result directory RAW/<case>/t<T>-m<GB>-r<rep>/. Runs with
a summary are skipped (resume). Timings need the measurement slot (guard.py --exclusive around the
whole `run`). `table` gives per (case, threads, cap): median solve time [min-max] (report
time_total_s, the solve after loading), median wall time of the process, peak RSS (max over the
repetitions), the memory mode chosen and whether every run succeeded with a passed certificate.

The tiers describe the default general path (shift-invert Krylov from the start): every report must
give candidate_source = "iterative" (docs/FORMATS.md §3). A report from the structure fast path
(structure_candidates = auto, off by default since 1.0) stops `run` after it is logged, and `table`
refuses raw data with such a report or without the field.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.run.guard import parse_cpulist  # noqa: E402  (standard library only)

GUARD = ROOT / "tools" / "run" / "guard.py"
# (cells, lengths) of the Yee cavities; 1e4 and 1e5 are tools/gen/yee.py's presets of the same names.
YEE = {"1e4": ((20, 16, 12), (1.0, 0.7, 0.45)), "1e5": ((44, 34, 26), (1.0, 0.75, 0.55)),
       "1e6": ((92, 71, 54), (1.0, 0.75, 0.55))}
# Waveguide grids (cells per side, union-jack triangles) of tools/gen/waveguide.py; 1e5 and 1e6 are the
# grids of the data campaign's wg-square-1e5 / wg-square-1e6.
WAVEGUIDE = {"1e4": 50, "1e5": 158, "1e6": 500}
# report candidate_source of the general path; the structure fast path writes separable_* instead.
GENERAL_PATH = "iterative"


def generate(root: Path, sizes: list[str]) -> None:
    from tools.gen import waveguide, yee  # numpy / scipy: only needed here

    for size in sizes:
        cells, lengths = YEE[size]
        path = yee.make_homogeneous_case(f"yee-pec-box-{size}", yee.YeeGrid(cells, lengths), "generalized", root)
        print(f"{path}: Yee cavity {cells}", flush=True)
        nx = WAVEGUIDE[size]
        rc = waveguide.main(["--family", "waveguide", "--a", "10", "--b", "10", "--freq", "50", "--nx", str(nx),
                             "--ny", str(nx), "--name", f"wg-square-{size}", "--root", str(root)])
        if rc:
            raise SystemExit(f"resource_tiers: waveguide generator failed for {size} ({rc})")


def find_hsolve(explicit: str | None) -> Path:
    for cand in (explicit, ROOT / "bin" / "hsolve", ROOT / "build" / "release" / "hsolve"):
        if cand and Path(cand).is_file():
            return Path(cand).resolve()
    raise SystemExit("resource_tiers: no hsolve executable (--hsolve PATH)")


def cpulist(cpus: list[int]) -> str:
    """[16, 17, 18, 20] -> '16-18,20' (guard.py --cores)."""
    parts, start = [], None
    for i, c in enumerate(cpus):
        if start is None:
            start = c
        if i + 1 == len(cpus) or cpus[i + 1] != c + 1:
            parts.append(str(c) if c == start else f"{start}-{c}")
            start = None
    return ",".join(parts)


def one_per_core(cpus: list[int], topology: Path = Path("/sys/devices/system/cpu")) -> list[int]:
    """cpus without hyperthread siblings: the first of each physical core's CPUs, in order."""
    seen: set[int] = set()
    out = []
    for c in cpus:
        try:
            core = min(parse_cpulist((topology / f"cpu{c}" / "topology" / "thread_siblings_list").read_text()))
        except (OSError, ValueError):
            core = c
        if core not in seen:
            seen.add(core)
            out.append(c)
    return out


def core_pool(environ: dict[str, str] | None = None, affinity: set[int] | None = None) -> list[int]:
    """CPUs the runs may be pinned to, in order: the measurement slot HS_MEASURE_CORES where the
    node defines one, else the CPUs this process may run on."""
    env = os.environ if environ is None else environ
    slot = env.get("HS_MEASURE_CORES", "")
    return parse_cpulist(slot) if slot else sorted(os.sched_getaffinity(0) if affinity is None else affinity)


def pick_cores(pool: list[int], threads: int, first: int | None) -> str:
    """The first `threads` CPUs of pool from CPU `first` on (None: the pool's first) as a cpulist."""
    if first is not None and first not in pool:
        raise SystemExit(f"resource_tiers: first core {first} is not among the usable CPUs {cpulist(pool)}")
    cpus = [c for c in pool if first is None or c >= first][:threads]
    if len(cpus) < threads:
        raise SystemExit(f"resource_tiers: {threads} threads need {threads} physical cores; the usable CPUs "
                         f"{cpulist(pool)}{'' if first is None else f' from {first} on'} are {len(cpus)} "
                         "(--threads, --first-core / HS_TIER_FIRST_CORE)")
    return cpulist(cpus)


def run(a: argparse.Namespace) -> int:
    in_slot = os.environ.get("HS_SLOT_HELD") is not None
    if not in_slot:
        print("resource_tiers: not inside the measurement slot - these times are not measurements", flush=True)
    pool = one_per_core(core_pool())
    cores = {t: pick_cores(pool, t, a.first_core) for t in (int(x) for x in a.threads.split(","))}
    allowed = os.sched_getaffinity(0)
    for spec in cores.values():
        if not set(parse_cpulist(spec)) <= allowed:
            raise SystemExit(f"resource_tiers: cores {spec} are not available to this process" +
                             ("" if in_slot else " - the measurement slot HS_MEASURE_CORES needs guard.py --exclusive "
                                                 "around `run`"))
    hsolve = find_hsolve(a.hsolve)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    host = socket.gethostname().split(".")[0]
    version = subprocess.run([str(hsolve), "--version"], capture_output=True, text=True).stdout.splitlines()[:1]
    cases = a.cases.split(",")
    with open(out / "runs.jsonl", "a") as log:
        for rep in range(a.reps):
            for name in cases:
                case = Path(a.root) / "cases" / name
                for threads in (int(t) for t in a.threads.split(",")):
                    for mem in (float(m) for m in a.mem_gb.split(",")):
                        run_id = f"t{threads}-m{mem:g}-r{rep}"
                        res, gsum = out / name / run_id, out / name / f"guard-{run_id}.json"
                        if gsum.exists():
                            continue
                        res.mkdir(parents=True, exist_ok=True)
                        cmd = [str(hsolve), "--A", str(case / "A.npz")]
                        if (case / "B.npz").exists():
                            cmd += ["--B", str(case / "B.npz")]
                        cmd += ["--config", str(case / "config.json"), "--threads", str(threads), "--out", str(res), "-q"]
                        g = [sys.executable, str(GUARD), "--skip-busy-check", "--cores", cores[threads],
                             "--threads", str(threads),
                             "--mem-gb", f"{mem:g}", "--timeout", str(a.timeout), "--summary", str(gsum), "--"]
                        p = subprocess.run(g + cmd, capture_output=True, text=True)
                        (out / name / f"stderr-{run_id}.txt").write_text(p.stderr)
                        s = json.loads(gsum.read_text()) if gsum.exists() else {"returncode": p.returncode}
                        rec: dict[str, Any] = {"case": name, "threads": threads, "mem_gb": mem, "rep": rep, "host": host,
                                               "version": version[0] if version else "", "rc": s.get("returncode"),
                                               "killed": s.get("killed"), "wall_s": s.get("wall_s"),
                                               "peak_rss_gib": s.get("peak_rss_gib")}
                        try:
                            rec.update(report_fields(json.loads((res / "report.json").read_text())))
                        except (OSError, ValueError) as err:
                            rec["error"] = f"{type(err).__name__}: {err}"
                        for big in res.glob("eigenvectors*"):
                            big.unlink()  # not needed here; up to GBs at 1e6
                        log.write(json.dumps(rec) + "\n")
                        log.flush()
                        print(f"{name:20s} {run_id:14s} rc={rec['rc']} t={rec.get('time_total_s')} "
                              f"wall={rec.get('wall_s')} peak={rec.get('peak_rss_gib')} GiB", flush=True)
                        off_path = not_general_path(rec)
                        if off_path:
                            raise SystemExit(f"resource_tiers: {off_path}")
    return 0


def report_fields(rep: dict[str, Any]) -> dict[str, Any]:
    fo, fs, cert = rep.get("factor_options") or {}, rep.get("factor_stats") or {}, rep.get("certificate") or {}
    return {"success": rep.get("success"), "time_total_s": rep.get("time_total_s"), "problem": rep.get("problem"),
            "n": rep.get("n"), "nnz_a": rep.get("nnz_a"), "nnz_b": rep.get("nnz_b"), "pairs": len(rep.get("pairs") or []),
            "candidate_source": rep.get("candidate_source"),
            "budget_gb": (rep.get("memory") or {}).get("budget_gb"), "out_of_core": bool(fo.get("out_of_core")),
            "ooc_switches": fs.get("ooc_switches"), "factorizations": fs.get("factorizations"),
            "flops": (fs.get("estimate") or {}).get("flops"), "certificate": cert.get("method"),
            "certificate_passed": bool(cert.get("passed")) if cert.get("performed") else None}


def not_general_path(rec: dict[str, Any]) -> str | None:
    """Why a run record is no measurement of the general path - its report gives another
    candidate_source than "iterative", or none (raw data from before the field was recorded) - else
    None. A run without a report (the solver refused, e.g. out_of_memory_budget) has nothing to check."""
    if "error" in rec:
        return None
    src = rec.get("candidate_source")
    if src == GENERAL_PATH:
        return None
    return (f"{rec.get('case')} t{rec.get('threads')}-m{rec.get('mem_gb', 0):g}-r{rec.get('rep')}: report "
            f"candidate_source = {json.dumps(src)}, not \"{GENERAL_PATH}\" - the tiers measure the default general "
            "path (structure_candidates off)")


def summarize(raws: list[Path]) -> list[dict[str, Any]]:
    groups: dict[tuple, list[dict[str, Any]]] = {}
    for raw in raws:
        for line in (raw / "runs.jsonl").read_text().splitlines():
            r = json.loads(line)
            off_path = not_general_path(r)
            if off_path:
                raise SystemExit(f"resource_tiers: {raw}: {off_path}")
            if r.get("rc") != 0:  # the solver's error kind, e.g. out_of_memory_budget
                err = raw / r["case"] / f"stderr-t{r['threads']}-m{r['mem_gb']:g}-r{r['rep']}.txt"
                m = re.search(r"hsolve: error \[(\w+)\]", err.read_text()) if err.is_file() else None
                r["error_kind"] = m.group(1) if m else f"exit {r.get('rc')}"
            groups.setdefault((r["case"], r["threads"], r["mem_gb"]), []).append(r)
    rows = []
    for (case, threads, mem), runs in groups.items():
        ok = [r for r in runs if r.get("rc") == 0 and not r.get("killed") and r.get("success")]
        t = [r["time_total_s"] for r in ok]
        w = [r["wall_s"] for r in ok]
        first = (ok or runs)[0]
        ooc = {("out-of-core" if r.get("out_of_core") or (r.get("ooc_switches") or 0) > 0 else "in-core") for r in ok}
        rows.append({
            "case": case, "n": first.get("n"), "problem": first.get("problem"), "pairs": first.get("pairs"),
            "nnz": (first.get("nnz_a") or 0) + (first.get("nnz_b") or 0), "threads": threads, "mem_gb": mem,
            "host": first.get("host"), "version": first.get("version"), "reps": len(runs), "ok": len(ok),
            "time_median_s": statistics.median(t) if t else None, "time_min_s": min(t) if t else None,
            "time_max_s": max(t) if t else None, "wall_median_s": statistics.median(w) if w else None,
            "peak_rss_gib": max((r.get("peak_rss_gib") or 0) for r in runs),
            "memory_mode": "/".join(sorted(ooc)) or "-",
            "certificate": first.get("certificate"),
            # "iterative" where a run gave a report (summarize checked them all), None where none did
            "candidate_source": GENERAL_PATH if any("error" not in r for r in runs) else None,
            # passed: every run succeeded with a passed certificate; none: every run succeeded, none
            # performed one (e.g. B indefinite); failed: anything else
            "certified": ("failed" if len(ok) < len(runs) else
                          "none" if all(r.get("certificate_passed") is None for r in ok) else
                          "passed" if all(r.get("certificate_passed") for r in ok) else "failed"),
            "errors": sorted({r["error_kind"] for r in runs if "error_kind" in r})})
    family = {"yee": 0, "wg-": 1}
    def size(case: str) -> float:
        try:
            return float(case.rsplit("-", 1)[1])
        except (IndexError, ValueError):
            return 0.0

    rows.sort(key=lambda r: (family.get(r["case"][:3], 2), size(r["case"]), -r["mem_gb"], -r["threads"]))
    return rows


def table(a: argparse.Namespace) -> int:
    rows = summarize([Path(p) for p in a.raw])
    f = lambda x, d=2: "-" if x is None else f"{x:.{d}f}"  # noqa: E731
    lines = ["| case | n | problem | pairs | threads | RAM cap GiB | solve s [min-max] | wall s | peak RSS GiB | "
             "memory | certificate | runs ok |", "|---|---:|---|---:|---:|---:|---|---:|---:|---|---|---|"]
    for r in rows:
        times = ("-" if r["time_median_s"] is None else
                 f"{f(r['time_median_s'])} [{f(r['time_min_s'])}-{f(r['time_max_s'])}]")
        cert = ("-" if r["certified"] == "none" or not r["certificate"] else
                f"{r['certificate']} {'passed' if r['certified'] == 'passed' else 'NOT passed'}")
        lines.append(f"| {r['case']} | {r['n'] or '-'} | {r['problem'] or '-'} | {r['pairs'] or '-'} | {r['threads']} | "
                     f"{r['mem_gb']:g} | "
                     f"{times} | {f(r['wall_median_s'])} | "
                     f"{f(r['peak_rss_gib'])} | {r['memory_mode']} | {cert} | {r['ok']}/{r['reps']}"
                     f"{' (' + ', '.join(r['errors']) + ')' if r['errors'] else ''} |")
    hosts = sorted({r["host"] for r in rows})
    versions = sorted({r["version"] for r in rows})
    lines += ["", f"Hosts: {', '.join(hosts)}; build: {'; '.join(versions)}. Solve = report time_total_s (after the "
              "matrices are loaded), median over the runs; wall = whole process incl. loading the .npz files; peak RSS "
              "= tools/run/guard.py's peak of the process tree, max over the runs. Every report gives "
              f"candidate_source = {GENERAL_PATH} (the general path; the structure fast path is off by default)."]
    Path(a.md).write_text("\n".join(lines) + "\n")
    Path(a.json).write_text(json.dumps(rows, indent=2) + "\n")
    if a.summary_md:
        Path(a.summary_md).write_text(summary(rows))
    print("\n".join(lines))
    return 0


FAMILY_ZH = {"yee-pec-box": "三维 PEC 谐振腔，GHEP，最近 σ 的 {k} 个",
             "wg-square": "二维方波导 50 GHz，GHIEP（B 不定），{k} 个传播模"}


def certified_all(rows: list[dict[str, Any]]) -> str:
    """One certificate state of several summary rows (a case at each thread count): 'passed' only
    if every row passed, 'none' if no row performed one, else 'failed'."""
    states = {r["certified"] for r in rows}
    return "passed" if states == {"passed"} else "none" if states == {"none"} else "failed"


def summary(rows: list[dict[str, Any]]) -> str:
    """docs/INSTALL.md's tier tables (Chinese): one row per case at the full cap, then the capped runs."""
    def fmt_t(x: float | None) -> str:
        return "-" if x is None else (f"{x:.2f} s" if x < 10 else f"{x:.0f} s")

    def fmt_m(x: float | None) -> str:
        return "-" if x is None else (f"{x * 1024:.0f} MiB" if x < 1 else f"{x:.1f} GiB")

    full = max(r["mem_gb"] for r in rows)
    by_case: dict[str, dict[int, dict[str, Any]]] = {}
    for r in rows:
        if r["mem_gb"] == full:
            by_case.setdefault(r["case"], {})[r["threads"]] = r
    out = ["| 问题 | n | 非零元 | 峰值内存 | 求解时间，16 线程 | 求解时间，4 线程 | 惯性证书 |",
           "|---|---:|---:|---:|---:|---:|---|"]
    cert_zh = {"passed": "通过", "none": "不适用（B 不定）"}
    for case, per in by_case.items():
        any_r = next(iter(per.values()))
        fam = case.rsplit("-", 1)[0]
        label = FAMILY_ZH.get(fam, case).format(k=any_r["pairs"])
        ok = all(r["ok"] == r["reps"] for r in per.values())
        out.append(f"| {label}（`{case}`）{'' if ok else '（有失败的运行）'} | {any_r['n']:,} | {any_r['nnz']:,} | "
                   f"{fmt_m(max(r['peak_rss_gib'] for r in per.values()))} | "
                   f"{fmt_t((per.get(16) or {}).get('time_median_s'))} | {fmt_t((per.get(4) or {}).get('time_median_s'))} | "
                   f"{cert_zh.get(certified_all(list(per.values())), '未通过')} |")
    capped = [r for r in rows if r["mem_gb"] < full]
    if capped:
        out += ["", "| 问题 | 内存上限 | 线程 | 分解方式 | 峰值内存 | 求解时间 |", "|---|---:|---:|---|---:|---:|"]
        for r in capped:
            mode = {"in-core": "内存内", "out-of-core": "外存"}.get(r["memory_mode"], r["memory_mode"])
            if r["ok"] < r["reps"]:  # e.g. out_of_memory_budget: refused after the analysis
                mode = "拒绝运行（" + "、".join(f"`{e}`" for e in r["errors"]) + "）"
            out.append(f"| `{r['case']}` | {r['mem_gb']:g} GiB | {r['threads']} | {mode} | {fmt_m(r['peak_rss_gib'])} | "
                       f"{fmt_t(r['time_median_s'])} |")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__.split("\n", 1)[1])
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--root", type=Path, required=True)
    g.add_argument("--sizes", default="1e4,1e5,1e6")
    r = sub.add_parser("run")
    r.add_argument("--root", type=Path, required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--cases", default=",".join(f"{fam}-{s}" for s in YEE for fam in ("yee-pec-box", "wg-square")))
    r.add_argument("--threads", default="16")
    r.add_argument("--mem-gb", default="32", help="RSS caps in GiB, comma-separated")
    r.add_argument("--reps", type=int, default=3)
    r.add_argument("--hsolve")
    first = os.environ.get("HS_TIER_FIRST_CORE")
    r.add_argument("--first-core", type=int, default=int(first) if first else None,
                   help="first CPU of the pinned ones (default: HS_TIER_FIRST_CORE, else the first CPU of the "
                        "measurement slot HS_MEASURE_CORES where set, else of this process's CPUs)")
    r.add_argument("--timeout", type=int, default=1200)
    t = sub.add_parser("table")
    t.add_argument("raw", nargs="+")
    t.add_argument("--md", required=True)
    t.add_argument("--json", required=True)
    t.add_argument("--summary-md", help="also the compact Chinese tables of docs/INSTALL.md")
    a = ap.parse_args(argv)
    if a.cmd == "generate":
        generate(a.root, a.sizes.split(","))
        return 0
    return run(a) if a.cmd == "run" else table(a)


if __name__ == "__main__":
    raise SystemExit(main())

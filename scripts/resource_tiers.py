#!/usr/bin/env python3
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
    scripts/resource_tiers.py table RAW... --md OUT.md --json OUT.json

`run` starts every (case, threads, memory cap, repetition) once - in this order, repetitions
outermost - with the case's config.json (target, tol) and nothing else: each under its own
tools/run/guard.py, pinned to the first T cores from --first-core, with the RSS cap --mem-gb (hsolve
plans its memory budget from it, docs/DESIGN.md §3.6), and records the guard summary (wall time,
peak RSS of the process tree) next to the result directory RAW/<case>/t<T>-m<GB>-r<rep>/. Runs with
a summary are skipped (resume). Timings need the measurement slot (guard.py --exclusive around the
whole `run`). `table` gives per (case, threads, cap): median solve time [min-max] (report
time_total_s, the solve after loading), median wall time of the process, peak RSS (max over the
repetitions), the memory mode chosen and whether every run succeeded with a passed certificate.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "tools" / "run" / "guard.py"
# (cells, lengths) of the Yee cavities; 1e4 and 1e5 are tools/gen/yee.py's presets of the same names.
YEE = {"1e4": ((20, 16, 12), (1.0, 0.7, 0.45)), "1e5": ((44, 34, 26), (1.0, 0.75, 0.55)),
       "1e6": ((92, 71, 54), (1.0, 0.75, 0.55))}
# Waveguide grids (cells per side, union-jack triangles) of tools/gen/waveguide.py; 1e5 and 1e6 are the
# grids of the data campaign's wg-square-1e5 / wg-square-1e6.
WAVEGUIDE = {"1e4": 50, "1e5": 158, "1e6": 500}


def generate(root: Path, sizes: list[str]) -> None:
    sys.path.insert(0, str(ROOT))
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


def run(a: argparse.Namespace) -> int:
    if os.environ.get("HS_SLOT_HELD") is None:
        print("resource_tiers: not inside the measurement slot - these times are not measurements", flush=True)
    hsolve = find_hsolve(a.hsolve)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    host = socket.gethostname().split(".")[0]
    version = subprocess.run([str(hsolve), "--A", "unused.npz", "--version"], capture_output=True,
                             text=True).stdout.splitlines()[:1]
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
                        cores = f"{a.first_core}-{a.first_core + threads - 1}"
                        cmd = [str(hsolve), "--A", str(case / "A.npz")]
                        if (case / "B.npz").exists():
                            cmd += ["--B", str(case / "B.npz")]
                        cmd += ["--config", str(case / "config.json"), "--threads", str(threads), "--out", str(res), "-q"]
                        g = [sys.executable, str(GUARD), "--skip-busy-check", "--cores", cores, "--threads", str(threads),
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
    return 0


def report_fields(rep: dict[str, Any]) -> dict[str, Any]:
    fo, fs, cert = rep.get("factor_options") or {}, rep.get("factor_stats") or {}, rep.get("certificate") or {}
    return {"success": rep.get("success"), "time_total_s": rep.get("time_total_s"), "problem": rep.get("problem"),
            "n": rep.get("n"), "nnz_a": rep.get("nnz_a"), "nnz_b": rep.get("nnz_b"), "pairs": len(rep.get("pairs") or []),
            "budget_gb": (rep.get("memory") or {}).get("budget_gb"), "out_of_core": bool(fo.get("out_of_core")),
            "ooc_switches": fs.get("ooc_switches"), "factorizations": fs.get("factorizations"),
            "flops": (fs.get("estimate") or {}).get("flops"), "certificate": cert.get("method"),
            "certificate_passed": bool(cert.get("passed")) if cert.get("performed") else None}


def summarize(raws: list[Path]) -> list[dict[str, Any]]:
    groups: dict[tuple, list[dict[str, Any]]] = {}
    for raw in raws:
        for line in (raw / "runs.jsonl").read_text().splitlines():
            r = json.loads(line)
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
            "certified": bool(ok) and len(ok) == len(runs) and all(r.get("certificate_passed") for r in ok)})
    family = {"yee": 0, "wg-": 1}
    rows.sort(key=lambda r: (family.get(r["case"][:3], 2), r["n"] or 0, -r["mem_gb"], -r["threads"]))
    return rows


def table(a: argparse.Namespace) -> int:
    rows = summarize([Path(p) for p in a.raw])
    f = lambda x, d=2: "-" if x is None else f"{x:.{d}f}"  # noqa: E731
    lines = ["| case | n | problem | pairs | threads | RAM cap GiB | solve s [min-max] | wall s | peak RSS GiB | "
             "memory | certificate | runs ok |", "|---|---:|---|---:|---:|---:|---|---:|---:|---|---|---|"]
    for r in rows:
        cert = f"{r['certificate']} {'passed' if r['certified'] else 'NOT passed'}" if r["certificate"] else "-"
        lines.append(f"| {r['case']} | {r['n']} | {r['problem']} | {r['pairs']} | {r['threads']} | {r['mem_gb']:g} | "
                     f"{f(r['time_median_s'])} [{f(r['time_min_s'])}-{f(r['time_max_s'])}] | {f(r['wall_median_s'])} | "
                     f"{f(r['peak_rss_gib'])} | {r['memory_mode']} | {cert} | {r['ok']}/{r['reps']} |")
    hosts = sorted({r["host"] for r in rows})
    versions = sorted({r["version"] for r in rows})
    lines += ["", f"Hosts: {', '.join(hosts)}; build: {'; '.join(versions)}. Solve = report time_total_s (after the "
              "matrices are loaded), median over the runs; wall = whole process incl. loading the .npz files; peak RSS "
              "= tools/run/guard.py's peak of the process tree, max over the runs."]
    Path(a.md).write_text("\n".join(lines) + "\n")
    Path(a.json).write_text(json.dumps(rows, indent=2) + "\n")
    print("\n".join(lines))
    return 0


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
    r.add_argument("--first-core", type=int, default=int(os.environ.get("HS_TIER_FIRST_CORE", "16")),
                   help="first core of the pinned range (default 16: the cluster's measurement slot)")
    r.add_argument("--timeout", type=int, default=1200)
    t = sub.add_parser("table")
    t.add_argument("raw", nargs="+")
    t.add_argument("--md", required=True)
    t.add_argument("--json", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "generate":
        generate(a.root, a.sizes.split(","))
        return 0
    return run(a) if a.cmd == "run" else table(a)


if __name__ == "__main__":
    raise SystemExit(main())

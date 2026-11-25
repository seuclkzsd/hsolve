#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 seuclkzsd and the hsolve contributors
"""Whole hsolve runs with the GPU offload off / on (P10 "gpu", results/p10_gpu.md).

Every run is tools/bench/compare.py's hsolve run (run_once: its own nested guard on the given cores
and RSS cap, the case's default configuration, tools/eval evaluation at the case tolerance - valid =
exit 0, success claimed, evaluation passed) with the environment variable HS_GPU set to the
variant (off / auto / on; the hsolve executable's BLAS hook reads it). Variants run interleaved, the
order reversed every other repetition. Recorded per run: solver time (report time_total_s), the
phases, the certificate (count, passed), the eigenvalues and the report's gpu object. Runs are
appended to <out-dir>/<tag>.jsonl, so the repetitions can be split over several slot calls; the
summary (<tag>.md, printed) covers every run in the file: the run table (summarize) and the phase
table (phase_table: the factorization phases - analysis + main factorization and the certificate's
counts - against the rest, and the GPU's utilization).

  python3 tools/bench/gpu_e2e.py --tag NAME [--reps 1] [--variants off,on] [--cores 16-31]
      [--mem-gb 32] [--timeout 1800] [--root DIR] [--out-dir DIR] [--smi-gpu IDX [--smi-ms 500]]
      [--summary-only] CASE ...

--smi-gpu IDX samples nvidia-smi's utilization.gpu (the share of each sample period in which a kernel
ran) and memory.used of GPU IDX (nvidia-smi's own index, e.g. 7; CUDA_VISIBLE_DEVICES does not apply
to it) every --smi-ms milliseconds while each run lasts, the off runs included; the run line gets
"smi": {samples, util_mean, mem_max_mib}.

Run it in the measurement slot with exactly one GPU visible (the nested guards share the lock):
  tools/bench/gpu_slot.sh 7 2700 -- python3 tools/bench/gpu_e2e.py --tag p10-e2e-1e6 --reps 2 \\
      --root ~/p7_p7-membudget/data --mem-gb 32 syn-mem27-100 yee-pec-box-1e6
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from tools import case  # noqa: E402
from tools.bench import compare  # noqa: E402
from tools.run import guard  # noqa: E402

GPU_KEYS = ("mode", "available", "reason", "device", "init_s", "factorizations", "factorizations_offloaded",
            "calls", "gpu_gflop", "estimated_gflop", "gpu_share", "call_s", "predicted_cpu_s", "h2d_gb", "d2h_gb",
            "errors", "pipeline_s")


class SmiSampler:
    """nvidia-smi's utilization.gpu and memory.used of one GPU, sampled every `ms` milliseconds
    between __enter__ and __exit__ (one sampler per run). nvidia-smi missing or failing leaves
    result() empty: the sample is a by-product, never a condition of the run."""

    def __init__(self, gpu: str, ms: int):
        self.cmd = ["nvidia-smi", "-i", str(gpu), "--query-gpu=utilization.gpu,memory.used",
                    "--format=csv,noheader,nounits", f"-lms={int(ms)}"]
        self.proc: subprocess.Popen | None = None
        self.text = ""

    def __enter__(self) -> "SmiSampler":
        try:
            self.proc = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        except OSError:
            self.proc = None
        return self

    def __exit__(self, *exc) -> None:
        if self.proc is None:
            return
        self.proc.terminate()
        try:
            self.text, _ = self.proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.text, _ = self.proc.communicate()

    def result(self) -> dict:
        return parse_smi(self.text)


class NeighbourLoad:
    """Mean utilization (0-1) of the hyperthread siblings of the run's cores between __enter__ and
    __exit__, from /proc/stat. The runs are pinned to the cores themselves and the slot's guard only
    checks for foreign load when it starts, so work on a sibling during a run is someone else's -
    and slows the run (guard.with_siblings). None when the cores have no siblings."""

    def __init__(self, cores: str, read=guard.cpu_times):
        own = guard.parse_cpulist(cores)
        self.cpus = [c for c in guard.with_siblings(own) if c not in set(own)]
        self.read = read
        self.a: dict = {}
        self.b: dict = {}

    def __enter__(self) -> "NeighbourLoad":
        self.a = self.read()
        return self

    def __exit__(self, *exc) -> None:
        self.b = self.read()

    def result(self) -> float | None:
        cpus = [c for c in self.cpus if c in self.a and c in self.b]
        total = sum(self.b[c][0] - self.a[c][0] for c in cpus)
        idle = sum(self.b[c][1] - self.a[c][1] for c in cpus)
        return 1.0 - idle / total if total > 0 else None


def parse_smi(text: str) -> dict:
    """{samples, util_mean (%), mem_max_mib} from nvidia-smi CSV lines "util, mem" ({} if none)."""
    util, mem = [], []
    for line in text.splitlines():
        parts = [x.strip() for x in line.split(",")]
        if len(parts) != 2:
            continue
        try:
            u, m = float(parts[0]), float(parts[1])
        except ValueError:
            continue
        util.append(u)
        mem.append(m)
    if not util:
        return {}
    return {"samples": len(util), "util_mean": statistics.fmean(util), "mem_max_mib": max(mem)}


def run_variant(variant: str, c, tgt, out: Path, args, judge) -> dict:
    """One evaluated hsolve run with HS_GPU=variant."""
    old = os.environ.get("HS_GPU")
    os.environ["HS_GPU"] = variant
    try:
        e = compare.run_once("hsolve", c, tgt, out, args, None, judge)
    finally:
        if old is None:
            os.environ.pop("HS_GPU", None)
        else:
            os.environ["HS_GPU"] = old
    rep_path = out / "report.json"
    if rep_path.exists():
        rep = json.loads(rep_path.read_text())
        g = rep.get("gpu") or {}
        cert = rep.get("certificate") or {}
        e["gpu"] = {k: g.get(k) for k in GPU_KEYS if k in g}
        e["certificate"] = {k: cert.get(k) for k in ("method", "performed", "passed", "count_inertia",
                                                       "count_found", "lower", "upper")}
        e["times"] = {k: rep.get(k) for k in ("time_total_s", "time_factor_s", "time_iterate_s",
                                               "time_certificate_s", "time_verify_s")}
    return e


def summarize(lines: list[dict]) -> str:
    out = ["| case | variant | valid | solver s median [min-max] | speedup vs off | certificate count | "
           "GPU factorizations | GPU GFlop (share) | GPU call s / CPU-model s | max eig. diff vs off |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    cases = sorted({r["case"] for r in lines})
    for name in cases:
        rows = [r for r in lines if r["case"] == name]
        variants = sorted({r["variant"] for r in rows}, key=lambda v: (v != "off", v))
        base = [r for r in rows if r["variant"] == "off" and r.get("valid")]
        base_t = statistics.median([r["solver_s"] for r in base]) if base else None
        base_eigs = np.asarray(base[0]["eigenvalues"]) if base else None
        for v in variants:
            rs = [r for r in rows if r["variant"] == v]
            good = [r for r in rs if r.get("valid")]
            ts = [r["solver_s"] for r in good]
            t = statistics.median(ts) if ts else None
            sp = f"{base_t / t:.3f}" if (t and base_t and v != "off" and len(good) == len(rs)) else "-"
            counts = sorted({(r.get("certificate") or {}).get("count_inertia") for r in rs}, key=str)
            g = [r.get("gpu") or {} for r in rs]
            nf = sorted({(x.get("factorizations_offloaded"), x.get("factorizations")) for x in g if x}, key=str)
            gf = [x.get("gpu_gflop") for x in g if x.get("gpu_gflop") is not None]
            sh = [x.get("gpu_share") for x in g if x.get("gpu_share") is not None]
            cs = [x.get("call_s") for x in g if x.get("call_s") is not None]
            ps = [x.get("predicted_cpu_s") for x in g if x.get("predicted_cpu_s") is not None]
            diff = "-"
            if base_eigs is not None and v != "off" and good:
                d = max(float(np.max(np.abs(np.sort(np.asarray(r["eigenvalues"])) - np.sort(base_eigs))
                                     / (np.abs(base_eigs).max() + 1e-300))) for r in good
                        if len(r["eigenvalues"]) == len(base_eigs))
                diff = f"{d:.1e}"
            out.append(
                f"| {name} | {v} | {len(good)}/{len(rs)} | "
                + (f"{t:.2f} [{min(ts):.2f}-{max(ts):.2f}]" if t else "-")
                + f" | {sp} | {', '.join(str(x) for x in counts)} | "
                + (", ".join(f"{a}/{b}" for a, b in nf) if nf else "-") + " | "
                + (f"{statistics.median(gf):.0f} ({statistics.median(sh):.2f})" if gf else "-") + " | "
                + (f"{statistics.median(cs):.1f} / {statistics.median(ps):.1f}" if cs else "-")
                + f" | {diff} |")
    return "\n".join(out)


def _median(xs: list) -> float | None:
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def _fmt(x: float | None, spec: str = ".2f") -> str:
    return "-" if x is None else format(x, spec)


def phase_table(lines: list[dict]) -> str:
    """Per case and variant, medians over the valid runs: solver time, the factorization phases
    (report time_factor_s + time_certificate_s: analysis, main factorization and the certificate's
    inertia counts - every factorization the GPU can take), the rest (iteration, verification,
    set-up), the ratios off / variant of the whole run and of the factorization phases (only when
    every run of both variants is valid), peak RSS, the GPU's sampled utilization (--smi-gpu) with
    the GPU-busy seconds it implies (utilization x solver time), and the largest foreign load on the
    cores' hyperthread siblings over all runs (NeighbourLoad; "-" for records without it)."""
    out = ["| case | variant | valid | solver s | vs off | factorization phases s (factor + certificate) | "
           "vs off | rest s (iterate + other) | peak GiB | GPU util. % (mean of samples) | GPU-busy s est. | "
           "sibling CPUs busy %, max of the runs |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for name in sorted({r["case"] for r in lines}):
        rows = [r for r in lines if r["case"] == name]
        variants = sorted({r["variant"] for r in rows}, key=lambda v: (v != "off", v))

        def stats(v: str) -> dict:
            rs = [r for r in rows if r["variant"] == v]
            good = [r for r in rs if r.get("valid")]
            t = [r.get("times") or {} for r in good]
            fact = [(x.get("time_factor_s") or 0.0) + (x.get("time_certificate_s") or 0.0) for x in t]
            return {"n": len(rs), "good": len(good), "solver": _median([r.get("solver_s") for r in good]),
                    "fact": _median(fact), "rest": _median([r["solver_s"] - f for r, f in zip(good, fact)]),
                    "peak": _median([r.get("peak_rss_gib") for r in good]),
                    "util": _median([(r.get("smi") or {}).get("util_mean") for r in good]),
                    "load": max((r["sibling_busy"] for r in rs if r.get("sibling_busy") is not None), default=None)}

        base = stats("off") if "off" in variants else None
        for v in variants:
            s = stats(v)
            whole = fact = None
            if v != "off" and base and base["good"] == base["n"] and s["good"] == s["n"] and s["n"]:
                whole = base["solver"] / s["solver"] if s["solver"] else None
                fact = base["fact"] / s["fact"] if s["fact"] else None
            busy = s["util"] / 100.0 * s["solver"] if s["util"] is not None and s["solver"] else None
            out.append(f"| {name} | {v} | {s['good']}/{s['n']} | {_fmt(s['solver'])} | {_fmt(whole, '.3f')} | "
                       f"{_fmt(s['fact'])} | {_fmt(fact, '.3f')} | {_fmt(s['rest'])} | {_fmt(s['peak'])} | "
                       f"{_fmt(s['util'], '.1f')} | {_fmt(busy, '.1f')} | "
                       f"{_fmt(None if s['load'] is None else 100.0 * s['load'], '.1f')} |")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cases", nargs="*")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--variants", default="off,on")
    ap.add_argument("--cores", default=os.environ.get("HS_MEASURE_CORES", "16-31"))
    ap.add_argument("--mem-gb", type=float, default=32.0)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--root", default=str(case.DEFAULT_ROOT))
    ap.add_argument("--out-dir", type=Path, default=REPO / "results/raw/p10gpu")
    ap.add_argument("--smi-gpu", default=None, help="sample this GPU's utilization with nvidia-smi")
    ap.add_argument("--smi-ms", type=int, default=500)
    ap.add_argument("--summary-only", action="store_true")
    args = ap.parse_args(argv)
    jsonl = args.out_dir / f"{args.tag}.jsonl"
    if not args.summary_only:
        from tools.eval import common, evaluate
        common.require_guard("gpu_e2e")
        variants = args.variants.split(",")
        run_args = SimpleNamespace(cores=args.cores, mem_gb=args.mem_gb, timeout=args.timeout, exclusive=False,
                                   keep_vectors=False, root=args.root)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        for name in args.cases:
            c = case.load_case(name, root=args.root)
            tgt = dict(c.config["target"])
            norms = evaluate.estimate_norms(c.A, c.B)
            judge = compare.make_judge(c, tgt, norms)
            done = sum(1 for x in (jsonl.read_text().splitlines() if jsonl.exists() else [])
                       if json.loads(x)["case"] == name)
            first_rep = done // max(1, len(variants))
            for rep in range(first_rep, first_rep + args.reps):
                order = variants if rep % 2 == 0 else variants[::-1]
                for v in order:
                    out = REPO / "results/raw" / args.tag / name / f"{v}-r{rep}"
                    t0 = time.time()
                    with NeighbourLoad(args.cores) as load:
                        if args.smi_gpu is None:
                            e = run_variant(v, c, tgt, out, run_args, judge)
                        else:
                            with SmiSampler(args.smi_gpu, args.smi_ms) as smi:
                                e = run_variant(v, c, tgt, out, run_args, judge)
                            e["smi"] = smi.result()
                    e["sibling_busy"] = load.result()
                    e.update(case=name, variant=v, rep=rep, started=t0)
                    with jsonl.open("a") as f:
                        f.write(json.dumps(e) + "\n")
                    g = e.get("gpu") or {}
                    print(f"{name} rep {rep} {v}: solver={e.get('solver_s')} valid={e.get('valid')} "
                          f"count={(e.get('certificate') or {}).get('count_inertia')} gpu_gflop={g.get('gpu_gflop')} "
                          f"sibling_busy={e.get('sibling_busy')} "
                          f"why={'; '.join(e.get('why') or [])[:200]}", flush=True)
    lines = [json.loads(x) for x in jsonl.read_text().splitlines() if x.strip()] if jsonl.exists() else []
    md = summarize(lines) + "\n\n" + phase_table(lines)
    (args.out_dir / f"{args.tag}.md").write_text(md + "\n")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
